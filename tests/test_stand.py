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
