"""Statische Seite aus den Testdaten für die Browser-Tests – ohne einen einzigen Abruf bei antraege.gruene.de.

Zwei Änderungsanträge in der Sammelphase: einer mit 20 Stunden Verlauf (Ampel Rot), einer ohne Verlauf
(„Prognose ab …“). Externe Ziele (GitHub, Threema …) werden im Browser abgefangen, nichts verlässt den Rechner.
"""
import functools
import threading
from datetime import datetime, timedelta
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

pytest.importorskip("playwright")

from antragshelper import build  # noqa: E402
from antragshelper.config import Fristen, Settings  # noqa: E402

FIXTURES = Path(__file__).parent.parent / "fixtures"
BASE = "https://antraege.gruene.de"
MIT_VERLAUF = f"{BASE}/52bdk/wasser-antrag-1/999"
OHNE_VERLAUF = f"{BASE}/52bdk/wasser-antrag-1/998"


class _Leise(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def site(tmp_path_factory):
    collecting = (FIXTURES / "amendment_collecting.html").read_text(encoding="utf-8")
    pages = {
        f"{BASE}/52bdk": (FIXTURES / "home.html").read_text(encoding="utf-8"),
        f"{BASE}/52bdk/activitylog?page=0": (FIXTURES / "activitylog.html").read_text(encoding="utf-8"),
        MIT_VERLAUF: collecting,
        OHNE_VERLAUF: collecting,
    }
    original_get = httpx.Client.get
    httpx.Client.get = lambda self, url, **kw: httpx.Response(
        200, text=pages.get(url, "<html></html>"), request=httpx.Request("GET", url))
    try:
        jetzt = datetime.now().replace(microsecond=0)
        frist = jetzt + timedelta(hours=30)
        vorher = {"verlauf": {MIT_VERLAUF: [{
            "fetched_at": (jetzt - timedelta(hours=20)).isoformat(), "status": "Antragsteller*innen sammeln",
            "min_total": 91, "min_women": 46, "current_total": 40, "current_women": 12, "reached": 0}]}}
        tmp = tmp_path_factory.mktemp("ui")
        settings = Settings(db_path=tmp / "x.sqlite3", fristen=Fristen(frist, frist),
                            vorschlag_mail="antraege@example.org")
        build.build_site(tmp / "site", settings, watch_urls=[MIT_VERLAUF, OHNE_VERLAUF], previous=vorher)
    finally:
        httpx.Client.get = original_get

    server = ThreadingHTTPServer(("localhost", 0), functools.partial(_Leise, directory=str(tmp / "site")))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://localhost:{server.server_address[1]}/"
    server.shutdown()


@pytest.fixture
def seite(context, site):
    """Neue Seite; externe Adressen werden mit einer leeren Antwort abgefangen, Fehler gesammelt."""
    def route(r):
        if r.request.url.startswith(site):
            r.continue_()
        else:
            r.fulfill(status=200, content_type="text/html", body="<html><body>extern</body></html>")

    context.route("**/*", route)
    page = context.new_page()
    page.fehler = []
    page.on("console", lambda m: page.fehler.append(f"console: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: page.fehler.append(f"pageerror: {e}"))
    page.on("response", lambda r: page.fehler.append(f"{r.status} {r.url}")
            if r.url.startswith(site) and r.status >= 400 else None)
    return page
