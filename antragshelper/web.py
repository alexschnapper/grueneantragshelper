"""Lokale Web-Oberfläche (FastAPI + Jinja2)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import dashboard, stand, views
from .client import SourceError
from .config import settings
from .links import Links
from .service import MAX_ACTIVITY_PAGES, Antragshelper

_HERE = Path(__file__).parent

app = FastAPI(title="Grüne Antragshelper")
app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")
templates = Jinja2Templates(directory=_HERE / "templates")
helper = Antragshelper(settings)
href = Links()


def _render(request: Request, name: str, status_code: int = 200, **context) -> HTMLResponse:
    context.update(settings=settings, href=href, static=False, footer=views.footer_server(helper.client.log))
    return templates.TemplateResponse(request, name, context, status_code=status_code)


@app.get("/", response_class=HTMLResponse)
def overview(request: Request):
    try:
        watched = helper.watchlist()
        trends = {i.url: helper.hochrechnung(i.detail) for i in helper.needs_support(watched)}
        context = views.overview(helper.index(), watched, trends)
    except SourceError as e:
        return _render(request, "error.html", 502, message=str(e))
    return _render(request, "index.html", **context)


@app.get("/suche")
def search(request: Request, q: str = ""):
    if not q.strip():
        return RedirectResponse("/", status_code=303)
    try:
        url, _ = helper.resolve(q)
    except SourceError as e:
        return _render(request, "error.html", 400, message=str(e))
    if url is None:
        return _render(
            request,
            "error.html",
            404,
            message=f"Kein veröffentlichter (Änderungs-)Antrag mit dem Kürzel „{q}“ gefunden. "
            "Anträge in der Sammelphase haben noch kein Kürzel – bitte den Direktlink einfügen.",
        )
    return RedirectResponse(href("auswertung", url=url), status_code=303)


@app.get("/auswertung", response_class=HTMLResponse)
def evaluation(request: Request, url: str):
    try:
        _, entry = helper.resolve(url)
        min_total = helper.index().min_total
        detail = helper.detail(url)
        published, collecting = helper.amendments_of(url) if detail.kind == "motion" else ([], [])
    except SourceError as e:
        return _render(request, "error.html", 502, message=str(e))
    return _render(
        request,
        "detail.html",
        detail=detail,
        entry=entry,
        published_amendments=published,
        collecting_amendments=collecting,
        history=helper.store.history(url),
        watched=helper.store.is_watched(url),
        without_quorum=views.is_without_quorum(detail, entry, min_total),
        min_total=min_total,
        **views.trend_context(helper, detail),
    )


@app.post("/beobachten")
def watch(url: str = Form(...), title: str = Form(""), remove: bool = Form(False)):
    if remove:
        helper.store.unwatch(url)
    elif helper.client.is_own_url(url):
        helper.store.watch(url, title or url)
    return RedirectResponse(f"/auswertung?url={quote(url, safe='')}", status_code=303)


@app.get("/liste", response_class=HTMLResponse)
def listing(request: Request, art: str = "", top: str = "", stand: str = "", text: str = ""):
    try:
        index = helper.index()
    except SourceError as e:
        return _render(request, "error.html", 502, message=str(e))
    without_quorum = dashboard.without_quorum_urls(helper.store.published_stats(), index.min_total)
    return _render(request, "list.html", **views.listing(index, art, top, stand, text, without_quorum))


@app.get("/aktivitaet", response_class=HTMLResponse)
def activity(request: Request, seiten: int = 2, typ: str = "", text: str = ""):
    seiten = max(1, min(seiten, MAX_ACTIVITY_PAGES))
    try:
        entries = helper.activity(seiten)
    except SourceError as e:
        return _render(request, "error.html", 502, message=str(e))
    return _render(request, "activity.html", **views.activity(entries, seiten, typ, text))


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_view(request: Request):
    try:
        index = helper.index()
        context = views.dashboard_page(helper, index, helper.activity(MAX_ACTIVITY_PAGES), helper.watchlist(), href)
    except SourceError as e:
        return _render(request, "error.html", 502, message=str(e))
    return _render(request, "dashboard.html", **context)


@app.post("/dashboard/aktualisieren")
def dashboard_refresh():
    try:
        helper.start_stats_refresh()
    except SourceError:
        pass
    return RedirectResponse("/dashboard#quorum", status_code=303)


@app.get("/transparenz", response_class=HTMLResponse)
def transparency(request: Request):
    requests = stand.request_rows(helper.client.log)
    return _render(request, "transparenz.html",
                   **views.transparency([], requests, datetime.now().astimezone(), static=False))
