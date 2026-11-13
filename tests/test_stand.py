import json
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

from antragshelper import build, stand
from antragshelper.__main__ import _check
from antragshelper.config import Settings

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://antraege.gruene.de"
MEMBER_AMENDMENT = f"{BASE}/52bdk/chancen-antrag-2/201"  # VR-02-284, Frauenanteil 56 % -> Mitglieder


@pytest.fixture
def fake_site(monkeypatch):
    pages = {
        f"{BASE}/52bdk": (FIXTURES / "home.html").read_text(encoding="utf-8"),
        f"{BASE}/52bdk/activitylog?page=0": (FIXTURES / "activitylog.html").read_text(encoding="utf-8"),
        MEMBER_AMENDMENT: (FIXTURES / "amendment_collecting.html").read_text(encoding="utf-8"),
    }
    requested = []

    def fake_get(self, url, **kwargs):
        # Unterhalb des AntragsgruenClient, damit Cache und Abrufprotokoll echt mitlaufen
        requested.append(url)
        return httpx.Response(200, text=pages.get(url, "<html></html>"), request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    monkeypatch.setattr("antragshelper.service.STATS_DELAY_SECONDS", 0)
    return pages, requested


def test_incremental_details(tmp_path, fake_site):
    _, requested = fake_site
    settings = Settings(db_path=tmp_path / "unused.sqlite3")

    build.build_site(tmp_path / "a", settings, details=True)
    assert MEMBER_AMENDMENT in requested
    first = json.loads((tmp_path / "a" / "static" / "stand.json").read_text(encoding="utf-8"))
    assert first["stats"][MEMBER_AMENDMENT]["supporter_count"] == 52
    assert "Muster" not in json.dumps(first)

    requested.clear()
    build.build_site(tmp_path / "b", settings, details=True, previous=first)
    assert MEMBER_AMENDMENT not in requested  # aus dem früheren Stand übernommen
    second = json.loads((tmp_path / "b" / "static" / "stand.json").read_text(encoding="utf-8"))
    assert second["stats"][MEMBER_AMENDMENT] == first["stats"][MEMBER_AMENDMENT]


def test_reusable_stats_expire():
    now = datetime(2026, 11, 9, 12, 0)
    previous = {"stats": {
        "neu": {"fetched_at": (now - timedelta(days=1)).isoformat()},
        "alt": {"fetched_at": (now - timedelta(days=8)).isoformat()},
        "kaputt": {},
    }}
    assert list(stand.reusable_stats(previous, now)) == ["neu"]
    assert stand.reusable_stats(None, now) == {}


def test_check_detects_change(tmp_path, fake_site, monkeypatch, capsys):
    pages, requested = fake_site
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out.txt"))
    build.build_site(tmp_path / "site", Settings(db_path=tmp_path / "x.sqlite3"))
    previous = str(tmp_path / "site" / "static" / "stand.json")

    requested.clear()
    assert _check(previous, None) == 0
    assert "changed=false" in capsys.readouterr().out
    assert requested == [f"{BASE}/52bdk/activitylog?page=0"]  # genau ein Abruf

    pages[f"{BASE}/52bdk/activitylog?page=0"] = pages[f"{BASE}/52bdk/activitylog?page=0"].replace("KI-03-167", "KI-03-168")
    assert _check(previous, None) == 0
    assert "changed=true" in capsys.readouterr().out
    assert (tmp_path / "out.txt").read_text().splitlines() == [
        "changed=false", "anlass=", "abrufe=1",
        "changed=true", "anlass=Stündliche Prüfung: neue Einträge im Aktivitäts-Protokoll", "abrufe=1",
    ]

    assert _check(str(tmp_path / "fehlt.json"), None) == 0
    assert "kein früherer Stand" in capsys.readouterr().out


def test_runs_are_logged(tmp_path, fake_site):
    settings = Settings(db_path=tmp_path / "unused.sqlite3")
    build.build_site(tmp_path / "a", settings, details=True, anlass="Erster Lauf")
    first = json.loads((tmp_path / "a" / "static" / "stand.json").read_text(encoding="utf-8"))
    [run] = first["laeufe"]
    assert run["anlass"] == "Erster Lauf"
    assert run["abrufe"]["Antragsliste und Tagesordnung (Startseite)"] == 1
    assert run["abrufe"]["Quorum-Zahlen eines Mitglieder-Antrags"] == 1
    assert run["gesamt"] == sum(run["abrufe"].values())
    assert {r["zweck"] for r in first["abrufe_letzter_lauf"]} >= {"Aktivitäts-Protokoll"}

    build.build_site(tmp_path / "b", settings, details=True, previous=first,
                     anlass="Stündliche Prüfung: neue Einträge im Aktivitäts-Protokoll", check_requests=1)
    second = json.loads((tmp_path / "b" / "static" / "stand.json").read_text(encoding="utf-8"))
    assert [r["anlass"] for r in second["laeufe"]] == ["Erster Lauf", "Stündliche Prüfung: neue Einträge im Aktivitäts-Protokoll"]
    assert second["laeufe"][-1]["abrufe"][stand.CHECK_PURPOSE] == 1
    assert "Quorum-Zahlen eines Mitglieder-Antrags" not in second["laeufe"][-1]["abrufe"]

    page = (tmp_path / "b" / "transparenz.html").read_text(encoding="utf-8")
    assert "Erster Lauf" in page and "Nächste geplant" in page
    for html_file in (tmp_path / "b").rglob("*.html"):
        assert "Letzter Abruf:" in html_file.read_text(encoding="utf-8"), html_file


def test_without_quorum_marked_in_build(tmp_path, fake_site):
    pages, _ = fake_site
    pages[MEMBER_AMENDMENT] = (FIXTURES / "amendment_no_quorum.html").read_text(encoding="utf-8")
    out = tmp_path / "site"
    build.build_site(out, Settings(db_path=tmp_path / "x.sqlite3"), details=True)
    pages_text = {p.name: p.read_text(encoding="utf-8") for p in out.rglob("*.html")}

    assert "ohne Quorum eingereicht" in pages_text["chancen-antrag-2--201.html"]
    assert "ohne Quorum eingereicht" in pages_text["dashboard.html"]
    assert "ohne Quorum eingereicht" in pages_text["alle_alle_alle.html"]
    assert "ohne Quorum eingereicht" not in pages_text["wasser-antrag-1.html"]


COLLECTING = f"{BASE}/52bdk/wasser-antrag-1/999"


def _warn_settings(tmp_path):
    from antragshelper.config import Fristen

    frist = datetime.now().replace(microsecond=0) + timedelta(hours=30)
    return Settings(db_path=tmp_path / "x.sqlite3", fristen=Fristen(frist, frist))


def test_verlauf_und_warnungen_im_statischen_export(tmp_path, fake_site):
    import xml.etree.ElementTree as ET

    pages, _ = fake_site
    pages[COLLECTING] = (FIXTURES / "amendment_collecting.html").read_text(encoding="utf-8")
    settings = _warn_settings(tmp_path)

    build.build_site(tmp_path / "a", settings, watch_urls=[COLLECTING])
    first = json.loads((tmp_path / "a" / "static" / "stand.json").read_text(encoding="utf-8"))
    [row] = first["verlauf"][COLLECTING]
    assert (row["current_total"], row["current_women"], row["min_women"]) == (52, 19, 46)
    # 30 Stunden bis Fristende, noch kein belastbares Tempo -> Warnstufe "frist"
    assert first["warnungen"][COLLECTING]["stufe"] == "frist"
    assert first["fingerprint"]["beobachtet"][COLLECTING] == [52, 19, False, None, "frist"]
    assert "Muster" not in json.dumps(first)

    feed = (tmp_path / "a" / "warnungen.xml").read_text(encoding="utf-8")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    [entry] = ET.fromstring(feed).findall("a:entry", ns)
    assert entry.find("a:title", ns).text.startswith("Frist läuft ab: Änderungsantrag zu VR-01")
    assert entry.find("a:link", ns).get("href").endswith("/antrag/wasser-antrag-1--999.html")
    assert "noch 27 Frauen nötig" in entry.find("a:summary", ns).text
    assert entry.find("a:summary", ns).text.startswith("Änderung: Von Zeile 12 bis 13:")
    # Auszüge werden angezeigt, aber nicht in stand.json gespeichert
    assert "Starkregen" not in json.dumps(first) and "Kommune" not in json.dumps(first)
    assert "Muster" not in feed

    index = (tmp_path / "a" / "index.html").read_text(encoding="utf-8")
    assert "Frühwarnungen" in index and "warnungen.xml" in index
    detail = (tmp_path / "a" / "antrag" / "wasser-antrag-1--999.html").read_text(encoding="utf-8")
    assert "Trend bis zur Frist" in detail and 'data-copy="aufruf-frauen"' in detail
    assert "Streichen „besser“" in detail and "Begründung:</span> Kommunen brauchen" in detail
    assert "Einfügen „in jeder Kommune konsequent“" in index

    # Zweiter Lauf: Verlauf wird übernommen (gleicher Stand, kein neuer Eintrag), Warnung behält ihren Beginn
    build.build_site(tmp_path / "b", settings, watch_urls=[COLLECTING], previous=first)
    second = json.loads((tmp_path / "b" / "static" / "stand.json").read_text(encoding="utf-8"))
    assert second["verlauf"] == first["verlauf"]
    assert second["warnungen"] == first["warnungen"]


def test_check_baut_neu_wenn_ampel_umspringt(tmp_path, fake_site, monkeypatch, capsys):
    pages, requested = fake_site
    pages[COLLECTING] = (FIXTURES / "amendment_collecting.html").read_text(encoding="utf-8")
    monkeypatch.setattr("antragshelper.__main__.settings", _warn_settings(tmp_path))
    watch_file = tmp_path / "beobachtet.txt"
    watch_file.write_text(COLLECTING + "\n", encoding="utf-8")
    build.build_site(tmp_path / "site", _warn_settings(tmp_path), watch_urls=[COLLECTING])
    stand_file = tmp_path / "site" / "static" / "stand.json"

    requested.clear()
    assert _check(str(stand_file), watch_file) == 0
    assert "changed=false" in capsys.readouterr().out
    assert requested == [f"{BASE}/52bdk/activitylog?page=0", COLLECTING]  # keine zusätzlichen Abrufe

    # 13 Stunden später ohne neue Mitantragsteller*innen: Tempo 0 ist jetzt belastbar -> Rot
    data = json.loads(stand_file.read_text(encoding="utf-8"))
    data["verlauf"][COLLECTING][0]["fetched_at"] = (datetime.now() - timedelta(hours=13)).isoformat(timespec="seconds")
    stand_file.write_text(json.dumps(data), encoding="utf-8")
    assert _check(str(stand_file), watch_file) == 0
    assert "changed=true (Stand oder Trend eines beobachteten Antrags geändert" in capsys.readouterr().out


def test_verlauf_auf_der_antragsseite(tmp_path, fake_site):
    """Anträge in der Sammelphase zeigen den Verlauf als Diagramm – vor dem Mobilisierungs-Text."""
    pages, _ = fake_site
    sammel = f"{BASE}/52bdk/wasser-antrag-1/999"
    ohne = f"{BASE}/52bdk/wasser-antrag-1/998"
    pages[sammel] = pages[ohne] = (FIXTURES / "amendment_collecting.html").read_text(encoding="utf-8")
    jetzt = datetime.now().replace(microsecond=0)
    vorher = {"verlauf": {sammel: [
        {"fetched_at": (jetzt - timedelta(hours=h)).isoformat(), "status": "Antragsteller*innen sammeln",
         "min_total": 91, "min_women": 46, "current_total": g, "current_women": f, "reached": 0}
        for h, g, f in ((20, 30, 10), (10, 40, 14))]}}
    out = tmp_path / "site"
    build.build_site(out, Settings(db_path=tmp_path / "x.sqlite3"), watch_urls=[sammel, ohne], previous=vorher)

    html = (out / "antrag" / "wasser-antrag-1--999.html").read_text(encoding="utf-8")
    assert "<h3>Verlauf</h3>" in html and '<svg class="chart"' in html
    assert html.index("<h3>Verlauf</h3>") < html.index("Mobilisierungs-Text")
    assert html.count('<circle class="dot s1"') == 3  # zwei frühere Stände plus der aktuelle (52 / 19)

    # Ohne früheren Stand gibt es nur einen Punkt – kein Diagramm
    assert "<h3>Verlauf</h3>" not in (out / "antrag" / "wasser-antrag-1--998.html").read_text(encoding="utf-8")
