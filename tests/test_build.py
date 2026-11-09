import json
import re
from pathlib import Path

import httpx

from antragshelper import build
from antragshelper.config import Settings
from antragshelper.links import Links, detail_page, list_page

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://antraege.gruene.de"


def test_links_server_and_static():
    server = Links()
    assert server("auswertung", url=f"{BASE}/52bdk/a-1/2") == "/auswertung?url=https%3A%2F%2Fantraege.gruene.de%2F52bdk%2Fa-1%2F2"
    assert server("liste", art="antraege", top="", stand="") == "/liste?art=antraege"

    static = Links(static=True, root="../", known={f"{BASE}/52bdk/a-1/2"})
    assert static("auswertung", url=f"{BASE}/52bdk/a-1/2") == "../antrag/a-1--2.html"
    assert static("auswertung", url=f"{BASE}/52bdk/unbekannt") == f"{BASE}/52bdk/unbekannt"
    assert static("liste") == "../liste/alle_alle_alle.html"
    assert detail_page(f"{BASE}/52bdk/a-1") == "antrag/a-1.html"
    assert list_page("antraege", "TOP 02 - Ä", "aktiv").startswith("liste/antraege_top-02-ae-")


def test_build_site_offline(tmp_path, monkeypatch):
    pages = {
        f"{BASE}/52bdk": (FIXTURES / "home.html").read_text(encoding="utf-8"),
        f"{BASE}/52bdk/activitylog?page=0": (FIXTURES / "activitylog.html").read_text(encoding="utf-8"),
    }
    requested = []

    def fake_get(self, url, **kwargs):
        # Unterhalb des AntragsgruenClient, damit Cache und Abrufprotokoll echt mitlaufen
        requested.append(url)
        return httpx.Response(200, text=pages.get(url, "<html></html>"), request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    out = tmp_path / "site"
    count = build.build_site(out, Settings(db_path=tmp_path / "unused.sqlite3"))

    assert count > 10
    assert (out / ".nojekyll").exists()
    index = json.loads((out / "static" / "suchindex.json").read_text(encoding="utf-8"))
    assert index["prefixes"]["VR-02-284"] == "antrag/chancen-antrag-2--201.html"
    # Nur Startseite und Aktivitäts-Protokoll, keine Einzelseiten ohne --details
    assert all("activitylog" in u or u.endswith("/52bdk") for u in requested)

    for html_file in out.rglob("*.html"):
        text = html_file.read_text(encoding="utf-8")
        assert "Muster" not in text  # keine Namen aus den Fixtures
        assert "Inoffizielles Projekt" in text
        for href in re.findall(r'href="([^"#]+)"', text):
            if not href.startswith("http"):
                assert (html_file.parent / href).resolve().exists(), (html_file, href)
