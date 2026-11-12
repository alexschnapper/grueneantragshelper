import html
from pathlib import Path

import httpx
import pytest

from antragshelper import build, vorschlag
from antragshelper.__main__ import _vorschlag
from antragshelper.config import Settings

KONFERENZ = "https://antraege.gruene.de/52bdk"
NUR_52BDK = "Nur Links in Zusammenhang mit der 52BDK"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("link", [
    f"{KONFERENZ}/zum-besseren-neues-wachstum-fur-unser-land-7749/26006",
    f"{KONFERENZ}/aus-der-durre-lernen-56963",
    f"  {KONFERENZ}/antrag-1/2  ",  # Leerraum am Rand ist egal
])
def test_gueltige_links(link):
    assert vorschlag.pruefe(link, KONFERENZ, "52BDK") is None


@pytest.mark.parametrize("link", [
    "https://example.org/52bdk/antrag-1",
    "https://antraege.gruene.de/53bdk/antrag-1/2",
    "http://antraege.gruene.de/52bdk/antrag-1",
    "https://antraege.gruene.de.evil.example/52bdk/antrag-1",
    "HTTPS://evil.example/x",
])
def test_andere_seiten(link):
    assert vorschlag.pruefe(link, KONFERENZ, "52BDK") == NUR_52BDK


@pytest.mark.parametrize("eingabe", [
    "", "VR-01", "🌻", f"{KONFERENZ}/antrag-🌻/1", f"{KONFERENZ}/antrag-1/2'; DROP TABLE watchlist;--",
    f"{KONFERENZ}/' OR 1=1 --", f"{KONFERENZ}/<script>alert(1)</script>", f"{KONFERENZ}/antrag 1/2",
    f"{KONFERENZ}/Antrag-1", f"{KONFERENZ}/", f"{KONFERENZ}/antrag-1/2/", f"{KONFERENZ}/antrag-1/2#supporters",
    f"{KONFERENZ}/antrag-1/2?x=1", f"{KONFERENZ}/../admin", f"{KONFERENZ}/a\n{KONFERENZ}/b",
    f"{KONFERENZ}/" + "a" * 400,
])
def test_ungueltige_eingaben(eingabe):
    assert vorschlag.pruefe(eingabe, KONFERENZ, "52BDK") == "Nicht gültig"


def test_link_aus_issue_formular():
    body = f"### Direktlink\n\n{KONFERENZ}/antrag-1/2\n"
    assert vorschlag.link_aus_issue(body) == f"{KONFERENZ}/antrag-1/2"
    assert vorschlag.link_aus_issue("### Direktlink\n\n_No response_") is None
    assert vorschlag.link_aus_issue("irgendwas") is None


def _run(tmp_path, monkeypatch, body):
    watch = tmp_path / "beobachtet.txt"
    if not watch.exists():
        watch.write_text("# Kopf\n", encoding="utf-8")
    out = tmp_path / "out.txt"
    out.write_text("", encoding="utf-8")
    monkeypatch.setenv("ISSUE_BODY", body)
    monkeypatch.setenv("ISSUE_NUMBER", "42")
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert _vorschlag(watch) == 0
    return dict(line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines()), watch.read_text(encoding="utf-8")


def test_cli_traegt_gueltigen_link_ein(tmp_path, monkeypatch):
    link = f"{KONFERENZ}/antrag-1/2"
    outputs, datei = _run(tmp_path, monkeypatch, f"### Direktlink\n\n{link}")
    assert outputs["ergebnis"] == "neu" and outputs["link"] == link
    assert "# Vorschlag aus Issue #42" in datei and datei.rstrip().endswith(link)
    # Zweiter Vorschlag desselben Links: nichts doppelt
    outputs, datei2 = _run(tmp_path, monkeypatch, f"### Direktlink\n\n{link}")
    assert outputs["ergebnis"] == "vorhanden" and datei2 == datei


def test_cli_lehnt_ab_ohne_eingabe_zurueckzugeben(tmp_path, monkeypatch):
    outputs, datei = _run(tmp_path, monkeypatch, "### Direktlink\n\nhttps://evil.example/<b>böse</b>")
    assert outputs["ergebnis"] == "abgelehnt" and outputs["link"] == ""
    assert outputs["meldung"].startswith(f"❌ {NUR_52BDK}.")
    assert "evil" not in outputs["meldung"] and datei == "# Kopf\n"


def test_formular_im_statischen_export_nutzt_dasselbe_muster(tmp_path, monkeypatch):
    pages = {
        f"{KONFERENZ}": (FIXTURES / "home.html").read_text(encoding="utf-8"),
        f"{KONFERENZ}/activitylog?page=0": (FIXTURES / "activitylog.html").read_text(encoding="utf-8"),
    }
    monkeypatch.setattr(httpx.Client, "get", lambda self, url, **kw: httpx.Response(
        200, text=pages.get(url, "<html></html>"), request=httpx.Request("GET", url)))
    out = tmp_path / "site"
    build.build_site(out, Settings(db_path=tmp_path / "x.sqlite3"))
    index = (out / "index.html").read_text(encoding="utf-8")
    assert f'data-muster="{html.escape(vorschlag.muster(KONFERENZ).pattern)}"' in index
    assert 'data-label="52BDK"' in index and "issues/new?template=antrag-vorschlagen.yml" in index


def test_wege_ohne_github_nur_wenn_eingetragen(tmp_path, monkeypatch):
    pages = {
        f"{KONFERENZ}": (FIXTURES / "home.html").read_text(encoding="utf-8"),
        f"{KONFERENZ}/activitylog?page=0": (FIXTURES / "activitylog.html").read_text(encoding="utf-8"),
    }
    monkeypatch.setattr(httpx.Client, "get", lambda self, url, **kw: httpx.Response(
        200, text=pages.get(url, "<html></html>"), request=httpx.Request("GET", url)))
    build.build_site(tmp_path / "ohne", Settings(db_path=tmp_path / "x.sqlite3", vorschlag_mail="",
                                                vorschlag_threema="", vorschlag_signal=""))
    ohne = (tmp_path / "ohne" / "index.html").read_text(encoding="utf-8")
    assert 'value="github"' in ohne and 'value="mail"' not in ohne and 'value="threema"' not in ohne

    settings = Settings(db_path=tmp_path / "y.sqlite3", vorschlag_mail="antraege@example.org",
                        vorschlag_threema="ABCD1234", vorschlag_signal="https://signal.me/#eu/beispiel")
    build.build_site(tmp_path / "mit", settings)
    mit = (tmp_path / "mit" / "index.html").read_text(encoding="utf-8")
    assert 'value="mail" data-adresse="antraege@example.org"' in mit
    # Icon-Adresse direkt am Element, relativ zur Seite (nicht über eine CSS-Variable)
    assert "mask-image: url('static/icons/threema.svg?v=" in mit and "--icon" not in mit
    assert 'value="threema" data-adresse="ABCD1234"' in mit
    assert 'value="signal" data-adresse="https://signal.me/#eu/beispiel"' in mit


def test_eingetragene_kontakte():
    s = Settings()
    assert s.vorschlag_threema == "UBK44SB7"
    assert s.vorschlag_mail.endswith("@mozmail.com")  # Alias, nicht die private Adresse
    # Signal als Benutzernamen-Link, nie als Telefonnummer (signal.me/#p/+49…)
    assert s.vorschlag_signal.startswith("https://signal.me/#eu/") and "#p/" not in s.vorschlag_signal


def test_icons_liegen_bei_und_sind_harmlos():
    icons = Path(__file__).parent.parent / "antragshelper" / "static" / "icons"
    for name in ("github", "signal", "threema"):
        svg = (icons / f"{name}.svg").read_text(encoding="utf-8")
        assert svg.startswith("<svg") and "<script" not in svg and "href" not in svg
    assert "CC0" in (icons / "LICENSE.md").read_text(encoding="utf-8")
