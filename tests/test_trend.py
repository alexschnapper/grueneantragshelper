from datetime import datetime, timedelta
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from antragshelper import trend, views
from antragshelper.config import Fristen, Settings
from antragshelper.links import Links
from antragshelper.models import Detail, Quorum
from antragshelper.service import Antragshelper
from antragshelper.trend import GELB, GRUEN, ROT, Hochrechnung, Stand

JETZT = datetime(2026, 11, 9, 12, 0)
URL = "https://antraege.gruene.de/52bdk/chancen-antrag-2/999"


def vor(stunden: float) -> datetime:
    return JETZT - timedelta(hours=stunden)


def test_tempo_im_rollierenden_fenster():
    # Stand vor 30 h gilt bis zum nächsten Stand, also auch zu Beginn des 24-h-Fensters
    verlauf = [Stand(vor(30), 10, 4), Stand(vor(12), 20, 8)]
    t = trend.tempo(verlauf, Stand(JETZT, 34, 14))
    assert t.stunden == 24 and not t.seit_beginn
    assert t.gesamt == pytest.approx(1.0)
    assert t.frauen == pytest.approx(10 / 24)


def test_tempo_faellt_auf_gesamtverlauf_zurueck():
    t = trend.tempo([Stand(vor(6), 40, 10)], Stand(JETZT, 52, 19))
    assert t.seit_beginn and t.stunden == 6
    assert t.gesamt == pytest.approx(2.0)
    assert t.frauen == pytest.approx(1.5)


@pytest.mark.parametrize("verlauf", [[], [Stand(vor(0.5), 50, 18)], [Stand(JETZT + timedelta(hours=2), 50, 18)]])
def test_zu_wenige_datenpunkte(verlauf):
    aktuell = Stand(JETZT, 52, 19)
    assert trend.tempo(verlauf, aktuell) is None
    t = trend.hochrechnen(verlauf, aktuell, 91, 46, JETZT + timedelta(hours=10))
    assert t.tempo is None and t.frauen.prognose is None
    assert t.frauen.ampel is None and t.empfehlung is None
    # Die nötige Rate hängt nicht vom Verlauf ab
    assert t.frauen.noetige_rate == pytest.approx(2.7)


def test_kein_zuwachs_im_fenster():
    t = trend.hochrechnen([Stand(vor(12), 52, 19)], Stand(JETZT, 52, 19), 91, 46, JETZT + timedelta(hours=20))
    f = t.frauen
    assert f.tempo == 0 and f.prognose == 19
    assert f.fehlen_zur_frist == 27 and f.ampel == ROT
    assert f.noetige_rate == pytest.approx(1.35)
    assert t.empfehlung == ("Bei aktuellem Sammeltempo (0,0 Frauen/h) fehlen zum Fristende voraussichtlich "
                            "27 Frauen. Ab jetzt sind mindestens 1,4 Frauen/h nötig. Auch insgesamt fehlen "
                            "voraussichtlich 39 Personen. Sofortige Mobilisierung über Frauen-Verteiler.")


def test_quorum_bereits_erreicht():
    t = trend.hochrechnen([Stand(vor(5), 91, 46)], Stand(JETZT, 95, 50), 91, 46, JETZT + timedelta(hours=3))
    assert t.gesamt.bedarf == 0 and t.frauen.bedarf == 0
    assert t.frauen.ampel == GRUEN and t.frauen.noetige_rate == 0
    assert t.empfehlung is None
    assert trend.mobilisierung("Titel", URL, "motion", t) is None


def test_frist_fast_abgelaufen():
    h = Hochrechnung(46, 40, 1.0, 0.01)
    assert h.noetige_rate == pytest.approx(600)
    assert h.prognose == pytest.approx(40.01)
    assert h.ampel == ROT


def test_frist_abgelaufen_mit_fehlenden_stimmen():
    t = trend.hochrechnen([], Stand(JETZT, 80, 40), 91, 46, vor(1))
    assert t.frauen.ampel == ROT and t.frauen.noetige_rate is None
    assert t.empfehlung == "Die Frist ist abgelaufen, es fehlen noch 6 Frauen."


@pytest.mark.parametrize("tempo, ampel", [(6.0, GRUEN), (5.9, GELB), (4.0, GELB), (3.9, ROT)])
def test_ampel_grenzen(tempo, ampel):
    # Prognose = 50 + tempo × 10 h gegenüber Quorum 100: 110 % / 109 % / 90 % / 89 %
    assert Hochrechnung(100, 50, tempo, 10).ampel == ampel


def test_knapp_ohne_fehlende_prognose():
    t = trend.hochrechnen([Stand(vor(10), 30, 30)], Stand(JETZT, 40, 40), 91, 46, JETZT + timedelta(hours=7))
    assert t.frauen.ampel == GELB and t.frauen.fehlen_zur_frist == 0
    assert "nur knapp erreicht (47 von 46)" in t.empfehlung


def test_ohne_frauenquorum_zaehlt_gesamt():
    t = trend.hochrechnen([Stand(vor(10), 50)], Stand(JETZT, 60), 91, None, JETZT + timedelta(hours=10))
    assert t.frauen is None and t.massgeblich is t.gesamt
    assert t.gesamt.prognose == pytest.approx(70) and t.gesamt.ampel == ROT
    assert "Personen/h" in t.empfehlung


def test_ohne_frist_keine_prognose():
    t = trend.hochrechnen([Stand(vor(10), 40, 10)], Stand(JETZT, 52, 19), 91, 46, None)
    assert t.tempo is not None and t.frauen.prognose is None
    assert t.frauen.ampel is None and t.frauen.noetige_rate is None


def test_mobilisierung():
    t = trend.hochrechnen([], Stand(JETZT, 52, 19), 91, 46, datetime(2026, 11, 20, 23, 59))
    text = trend.mobilisierung("Änderungsantrag zu VR-01: Mehr Bahn", URL, "amendment", t)
    assert text == ("Unser Änderungsantrag zu VR-01 („Mehr Bahn“) braucht noch Rückenwind: Es fehlen bis 20.11.2026, "
                    "23:59 Uhr noch 27 Mitantragstellerinnen, um das Frauenquorum zu sichern (insgesamt fehlen "
                    f"noch 39 Mitantragsteller*innen). Hier kannst du mitzeichnen: {URL}")


def _helper(tmp_path, monkeypatch):
    fristen = Fristen(datetime(2026, 11, 20, 23, 59), datetime(2026, 11, 9, 22, 0))
    helper = Antragshelper(Settings(db_path=tmp_path / "db.sqlite3", fristen=fristen))
    for zeit, gesamt, frauen in [(vor(30), 30, 10), (vor(12), 40, 14), (JETZT, 52, 19)]:
        helper.store._write(
            "INSERT INTO snapshots (url, fetched_at, status, min_total, min_women, current_total,"
            " current_women, reached) VALUES (?, ?, 'Sammeln', 91, 46, ?, ?, 0)",
            (URL, zeit.isoformat(), gesamt, frauen),
        )
    return helper


def test_service_rechnet_aus_gespeicherten_staenden(tmp_path, monkeypatch):
    helper = _helper(tmp_path, monkeypatch)
    detail = Detail(url=URL, title="Änderungsantrag zu VR-02", kind="amendment", quorum=Quorum(91, 46, 52, 19))
    t = helper.hochrechnung(detail, JETZT)
    assert t.frist == datetime(2026, 11, 9, 22, 0)  # eigene Frist für Änderungsanträge
    assert t.tempo.gesamt == pytest.approx(22 / 24) and t.tempo.frauen == pytest.approx(9 / 24)
    assert t.frauen.ampel == ROT
    assert helper.hochrechnung(Detail(url=URL, title="", kind="motion", quorum=Quorum(91, reached=True))) is None


def test_auswertungsseite_zeigt_ampel_und_text(tmp_path, monkeypatch):
    helper = _helper(tmp_path, monkeypatch)
    detail = Detail(url=URL, title="Änderungsantrag zu VR-02", kind="amendment", quorum=Quorum(91, 46, 52, 19))
    monkeypatch.setattr(helper, "hochrechnung", lambda d: Antragshelper.hochrechnung(helper, d, JETZT))
    templates = Path(views.__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(templates), autoescape=select_autoescape())
    html = env.get_template("detail.html").render(
        settings=helper.settings, href=Links(), static=False, footer=None, detail=detail, entry=None,
        published_amendments=[], collecting_amendments=[], history=[], watched=True,
        **views.trend_context(helper, detail),
    )
    assert "Rot · Scheitern droht" in html
    assert "Ab jetzt sind mindestens 2,7 Frauen/h nötig." in html
    assert 'data-copy="mobilisierung"' in html and "kopieren.js" in html
    assert 'data-copy="aufruf-frauen"' in html and "bis heute 22:00 Uhr nur noch 27 Mitantragstellerinnen" in html
    assert "Muster" not in html


def test_beobachtungsliste_zeigt_trendspalte(tmp_path, monkeypatch):
    from antragshelper.models import ConsultationIndex
    from antragshelper.service import WatchedItem

    helper = _helper(tmp_path, monkeypatch)
    detail = Detail(url=URL, title="Änderungsantrag zu VR-02", kind="amendment", quorum=Quorum(91, 46, 52, 19))
    item = WatchedItem(URL, detail.title, detail)
    templates = Path(views.__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(templates), autoescape=select_autoescape())
    context = views.overview(ConsultationIndex(), [item], {URL: helper.hochrechnung(detail, JETZT)})
    html = env.get_template("index.html").render(settings=helper.settings, href=Links(), static=False,
                                                 footer=None, **context)
    assert "Trend bis zur Frist" in html and "Rot · Scheitern droht" in html
    # Statischer Export: ohne Verlauf keine Trendspalte
    html = env.get_template("index.html").render(settings=helper.settings, href=Links(), static=True, built_at=JETZT,
                                                 footer=None, **views.overview(ConsultationIndex(), [item]))
    assert "Trend bis zur Frist" not in html


def test_fristen_je_konferenz():
    bdk = Settings(consultation="52bdk")
    assert bdk.frist_fuer("motion") == datetime(2026, 10, 9, 11, 59)
    assert bdk.frist_fuer("amendment") == datetime(2026, 11, 13, 11, 59)
    # Unbekannte Konferenz: keine Frist, also keine Prognose (statt einer falschen)
    assert Settings(consultation="ldk-irgendwo").frist_fuer("motion") is None
    # Ohne eigene ÄA-Frist gilt die Antragsfrist
    assert Fristen(antraege=JETZT).fuer("amendment") == JETZT


def test_kurzer_verlauf_nur_vorlaeufig():
    # 4 Stunden Abend-Tempo nicht über 3½ Tage hochrechnen: Prognose ja, Ampel nein
    t = trend.hochrechnen([Stand(vor(4), 56, 22)], Stand(JETZT, 63, 28), 91, 46, JETZT + timedelta(hours=86))
    assert t.frauen.prognose == pytest.approx(157) and not t.frauen.belastbar
    assert t.frauen.ampel is None and t.empfehlung is None
    # Kurz vor der Frist reicht so viel Verlauf, wie noch Zeit bleibt
    t = trend.hochrechnen([Stand(vor(4), 56, 22)], Stand(JETZT, 63, 28), 91, 46, JETZT + timedelta(hours=3))
    assert t.frauen.belastbar and t.frauen.ampel == ROT  # 28 + 1,5 × 3 = 32,5 von 46


@pytest.mark.parametrize("titel, kind, anfang", [
    ("Mehr Bahn", "motion", "Unser Antrag „Mehr Bahn“ braucht"),
    ("Änderungsantrag zu VR-01: Mehr Bahn", "amendment", "Unser Änderungsantrag zu VR-01 („Mehr Bahn“) braucht"),
    ("Mehr Bahn", "amendment", "Unser Änderungsantrag „Mehr Bahn“ braucht"),
])
def test_mobilisierung_titel(titel, kind, anfang):
    t = trend.hochrechnen([], Stand(JETZT, 52, 19), 91, 46, None)
    assert trend.mobilisierung(titel, URL, kind, t).startswith(anfang)


def test_vorlaeufige_prognose_wird_nicht_angezeigt(tmp_path):
    helper = Antragshelper(Settings(db_path=tmp_path / "db.sqlite3",
                                    fristen=Fristen(aenderungsantraege=JETZT + timedelta(hours=86))))
    helper.store._write(
        "INSERT INTO snapshots (url, fetched_at, status, min_total, min_women, current_total,"
        " current_women, reached) VALUES (?, ?, 'Sammeln', 91, 46, 56, 22, 0)", (URL, vor(4).isoformat()))
    detail = Detail(url=URL, title="Änderungsantrag zu VR-01: Mehr Bahn", kind="amendment",
                    quorum=Quorum(91, 46, 63, 28))
    t = helper.hochrechnung(detail, JETZT)
    templates = Path(views.__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(templates), autoescape=select_autoescape())
    html = env.get_template("detail.html").render(
        settings=helper.settings, href=Links(), static=False, footer=None, detail=detail, entry=None,
        published_amendments=[], collecting_amendments=[], history=[], watched=True,
        trend=t, mobilisierung=None, zahl=trend.zahl, restzeit_text=trend.restzeit_text,
    )
    assert "vorläufig · zu wenig Verlauf" in html
    assert "– / 46" in html and "157 / 46" not in html


def test_frauen_fehlen_obwohl_gesamt_erreichbar():
    # 18 h bis Fristende, 0,4 Frauen/h und 1 Person/h seit 20 h
    t = trend.hochrechnen([Stand(vor(20), 60, 17)], Stand(JETZT, 80, 25), 91, 46, JETZT + timedelta(hours=18))
    assert t.ampel == ROT and not t.gesamt.verfehlt
    assert t.empfehlung == ("Bei aktuellem Sammeltempo (0,4 Frauen/h) fehlen zum Fristende voraussichtlich 14 Frauen, "
                            "obwohl das Gesamtquorum rechnerisch erreichbar ist. Ab jetzt sind mindestens 1,2 Frauen/h "
                            "nötig. Sofortige Mobilisierung über Frauen-Verteiler.")


def test_rot_wenn_gesamttempo_nicht_reicht():
    # Frauenquorum erreicht, aber insgesamt 70 + 0,5 × 18 = 79 von 91
    t = trend.hochrechnen([Stand(vor(20), 60, 50)], Stand(JETZT, 70, 50), 91, 46, JETZT + timedelta(hours=18))
    assert t.frauen.ampel == GRUEN and t.gesamt.verfehlt and t.ampel == ROT
    assert t.empfehlung == ("Bei aktuellem Sammeltempo (0,5 Personen/h) fehlen zum Fristende voraussichtlich "
                            "12 Personen. Ab jetzt sind mindestens 1,2 Personen/h nötig. Sofortige Mobilisierung nötig.")


def test_gelb_empfiehlt_gezielte_ansprache():
    # Frauen 40 + 0,5 × 10 = 45 von 46 (98 %), gesamt 60 + 1 × 10 = 70 von 50
    t = trend.hochrechnen([Stand(vor(12), 48, 34)], Stand(JETZT, 60, 40), 50, 46, JETZT + timedelta(hours=10))
    assert t.ampel == GELB
    assert t.empfehlung.endswith("Gezielte Ansprache vorbereiten.")


def test_vorlaeufig_ist_auch_gesamt_nicht_verfehlt():
    t = trend.hochrechnen([Stand(vor(4), 56, 22)], Stand(JETZT, 63, 28), 91, 46, JETZT + timedelta(hours=86))
    assert not t.gesamt.verfehlt and t.ampel is None


@pytest.mark.parametrize("frist, text", [
    (datetime(2026, 11, 9, 18, 0), "heute 18:00 Uhr"),
    (datetime(2026, 11, 10, 11, 59), "morgen 11:59 Uhr"),
    (datetime(2026, 11, 13, 11, 59), "Freitag 11:59 Uhr"),
    (datetime(2026, 11, 20, 11, 59), "20.11.2026, 11:59 Uhr"),
])
def test_frist_relativ(frist, text):
    assert trend.frist_relativ(frist, JETZT) == text  # JETZT ist Montag, 09.11.2026


def test_aufruf_an_frauennetzwerke():
    t = trend.hochrechnen([], Stand(JETZT, 85, 38), 91, 46, datetime(2026, 11, 10, 11, 59))
    assert trend.aufruf_frauen("Änderungsantrag zu VR-01: Mehr Bahn", URL, "amendment", t) == (
        "Inhaltlich steht unser Änderungsantrag zu VR-01 („Mehr Bahn“) – uns fehlen bis morgen 11:59 Uhr "
        f"nur noch 8 Mitantragstellerinnen: {URL}")
    t = trend.hochrechnen([], Stand(JETZT, 90, 45), 91, 46, JETZT + timedelta(hours=2))
    assert trend.aufruf_frauen("Mehr Bahn", URL, "motion", t) == (
        f"Inhaltlich steht unser Antrag „Mehr Bahn“ – uns fehlen bis heute 14:00 Uhr nur noch 1 Mitantragstellerin: {URL}")


@pytest.mark.parametrize("stand, min_frauen, frist", [
    (Stand(JETZT, 60, 46), 46, JETZT + timedelta(hours=5)),   # Frauenquorum erreicht
    (Stand(JETZT, 60), None, JETZT + timedelta(hours=5)),     # kein Frauenquorum
    (Stand(JETZT, 60, 30), 46, None),                          # keine Frist
    (Stand(JETZT, 60, 30), 46, vor(1)),                        # Frist abgelaufen
])
def test_kein_aufruf_an_frauennetzwerke(stand, min_frauen, frist):
    t = trend.hochrechnen([], stand, 91, min_frauen, frist)
    assert trend.aufruf_frauen("Mehr Bahn", URL, "motion", t) is None


def test_warnstufen():
    # Rot wie die Ampel, mit Lagebild
    t = trend.hochrechnen([Stand(vor(20), 60, 17)], Stand(JETZT, 68, 28), 91, 46, JETZT + timedelta(hours=40))
    assert t.warnstufe == ROT
    assert t.warnung == ("Achtung: Gesamtfortschritt bei 74 %, Frauenquorum bei 60 % – noch 18 Frauen nötig "
                         "(insgesamt 23), Frist 11.11.2026, 04:00 Uhr.")
    # Vorläufige Prognose: erst ab 48 Stunden vor Fristende eine Warnung
    kurz = [Stand(vor(4), 56, 22)]
    assert trend.hochrechnen(kurz, Stand(JETZT, 63, 28), 91, 46, JETZT + timedelta(hours=60)).warnstufe is None
    assert trend.hochrechnen(kurz, Stand(JETZT, 63, 28), 91, 46, JETZT + timedelta(hours=40)).warnstufe == trend.FRIST
    # Grün auf Kurs oder Quorum erreicht: keine Warnung, auch kurz vor Fristende
    gruen = trend.hochrechnen([Stand(vor(20), 20, 10)], Stand(JETZT, 80, 40), 91, 46, JETZT + timedelta(hours=10))
    assert gruen.ampel == GRUEN and gruen.warnstufe is None and gruen.warnung is None
    erreicht = trend.hochrechnen([], Stand(JETZT, 95, 50), 91, 46, JETZT + timedelta(hours=10))
    assert erreicht.warnstufe is None
