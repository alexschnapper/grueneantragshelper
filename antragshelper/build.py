"""Statischer Export für GitHub Pages: `python -m antragshelper build --out _site`.

Erzeugt aus denselben Templates HTML-Seiten ohne Server. Abrufe: Startseite (1),
Aktivitäts-Protokoll (bis 5) und optional die Einzelseiten der Mitglieder-Anträge
(`--details`, gedrosselt) sowie Direktlinks aus einer Beobachtungsdatei.
"""
from __future__ import annotations

import dataclasses
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import dashboard, stand, trend, views
from .config import Settings
from .links import Links, detail_page, list_page
from .models import ConsultationIndex, Detail, IndexEntry, normalize_prefix
from .service import MAX_ACTIVITY_PAGES, Antragshelper, WatchedItem

_HERE = Path(__file__).parent

try:
    from zoneinfo import ZoneInfo

    _TZ = ZoneInfo("Europe/Berlin")
except Exception:  # pragma: no cover - ohne Zeitzonendaten lokale Zeit
    _TZ = None


def read_watch_file(path: Path) -> List[str]:
    """Eine URL pro Zeile; Leerzeilen und #-Kommentare werden ignoriert."""
    lines = (line.split("#", 1)[0].strip() for line in path.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line]


def detail_from_index(entry: IndexEntry, index: ConsultationIndex, supporter_count: Optional[int]) -> Detail:
    """Rahmendaten eines veröffentlichten Eintrags allein aus der Startseite (kein Einzelabruf)."""
    parent = next((m for m in index.motions if m.url == entry.parent_url), None)
    if parent is not None:
        title = f"{entry.prefix}: Änderungsantrag zu {parent.prefix}: {parent.title}"
    else:
        title = f"{entry.prefix}: {entry.title}"
    return Detail(
        url=entry.url,
        title=title,
        kind=entry.kind,
        status=entry.status,
        women_share=entry.women_share,
        supporter_count=supporter_count,
        parent_title=parent.title if parent else None,
        parent_url=parent.url if parent else None,
    )


def warning_entries(watched: List[WatchedItem], trends: Dict[str, Optional[trend.Trend]],
                    warnungen: Dict[str, Dict], site_url: str) -> List[Dict]:
    """Einträge für den Feed `warnungen.xml`: je beobachtetem Antrag mit Warnstufe einer.

    Die ID enthält Stufe und Beginn, damit Feed-Reader bei einer neuen Warnung erneut melden.
    """
    entries = []
    for item in watched:
        t, w = trends.get(item.url), warnungen.get(item.url)
        if t is None or w is None:
            continue
        entries.append({
            "id": f"{item.url}#warnung-{w['stufe']}-{w['seit']}",
            "titel": f"{trend.WARNSTUFEN[w['stufe']]}: {item.detail.title}",
            "link": f"{site_url}/{detail_page(item.url)}",
            "seit": w["seit"],
            "text": " ".join(filter(None, [t.warnung, t.empfehlung])),
        })
    return entries


def build_site(out: Path, settings: Settings, details: bool = False, watch_urls: Optional[List[str]] = None,
               previous: Optional[Dict] = None, anlass: str = "Lokaler Build", check_requests: int = 0) -> int:
    """Schreibt die Seite nach `out` und gibt die Zahl der erzeugten HTML-Seiten zurück.

    Mit `previous` (früherer `stand.json`) werden nur neue oder veraltete Mitglieder-Anträge abgerufen.
    `anlass` und `check_requests` (Abrufe der vorgeschalteten Prüfung) landen im Laufprotokoll.
    """
    started = datetime.now(_TZ)
    with tempfile.TemporaryDirectory() as tmp:
        helper = Antragshelper(dataclasses.replace(settings, db_path=Path(tmp) / "build.sqlite3"))
        index = helper.index()
        activity_entries = helper.activity(MAX_ACTIVITY_PAGES)
        if details:
            members = [e for e in index.entries if e.submitter == "Mitglieder" and not e.withdrawn]
            reusable = stand.reusable_stats(previous)
            for entry in members:
                if entry.url in reusable:
                    row = reusable[entry.url]
                    helper.store.import_published_stat(entry, row["supporter_count"], row["women_share"], row["fetched_at"])
            helper._refresh_stats([e for e in members if e.url not in reusable])  # synchron, 1 Seite pro Sekunde
        watch_urls = [url for url in watch_urls or [] if helper.client.is_own_url(url)]
        stand.import_history(helper, previous, watch_urls)  # Verlauf früherer Läufe, ohne Abruf
        for url in watch_urls:
            helper.store.watch(url, url)
        watched = helper.watchlist()
        fp = stand.fingerprint(helper, watch_urls)  # nutzt den Cache, keine zusätzlichen Abrufe
        stats = {r["url"]: r["supporter_count"] for r in helper.store.published_stats()}
        trends = {i.url: helper.hochrechnung(i.detail) for i in helper.needs_support(watched)}

        built_at = datetime.now(_TZ)
        warnungen = stand.warnings_since(previous, {u: t.warnstufe for u, t in trends.items() if t}, built_at)
        # Ab hier keine Abrufe mehr: Laufprotokoll für Transparenzseite und Footer
        record = stand.run_record(anlass, started, built_at, helper.client.log, check_requests)
        all_runs = stand.runs(previous, record)
        requests = stand.request_rows(helper.client.log, _TZ)
        footer = views.footer_static(record, built_at)

        known = {e.url for e in index.entries} | {w.url for w in watched if w.detail}
        env = Environment(loader=FileSystemLoader(_HERE / "templates"), autoescape=select_autoescape())
        pages = 0

        def render(template: str, path: str, **context) -> None:
            nonlocal pages
            root = "../" * path.count("/")
            context.update(settings=settings, static=True, href=Links(True, root, known), built_at=built_at,
                           footer=footer)
            target = out / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(env.get_template(template).render(**context), encoding="utf-8")
            pages += 1

        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)

        render("index.html", "index.html", **views.overview(index, watched, trends))
        render("warnungen.xml", "warnungen.xml", updated=built_at.isoformat(timespec="seconds"),
               eintraege=warning_entries(watched, trends, warnungen, settings.site_url))
        render("dashboard.html", "dashboard.html",
               **views.dashboard_page(helper, index, activity_entries, watched, Links(True, "", known)))
        render("activity.html", "aktivitaet.html", **views.activity(activity_entries, MAX_ACTIVITY_PAGES))
        render("transparenz.html", "transparenz.html", **views.transparency(all_runs, requests, built_at, static=True))

        combos = [(art, top, state)
                  for art in ("", "antraege", "aenderungsantraege")
                  for top in [""] + index.agenda_items
                  for state in ("", "aktiv", "zurueckgezogen")]
        list_pages: Dict[str, str] = {"|".join(c): "../" + list_page(*c) for c in combos}
        without_quorum = dashboard.without_quorum_urls(helper.store.published_stats(), index.min_total)
        for art, top, state in combos:
            render("list.html", list_page(art, top, state),
                   list_pages=list_pages, **views.listing(index, art, top, state, without_quorum=without_quorum))

        watched_by_parent = {}
        for item in watched:
            watched_by_parent.setdefault(item.url.rsplit("/", 1)[0], []).append(item)
        for entry in index.entries:
            detail = detail_from_index(entry, index, stats.get(entry.url))
            render("detail.html", detail_page(entry.url), detail=detail, entry=entry,
                   published_amendments=[a for a in index.amendments if a.parent_url == entry.url],
                   collecting_amendments=watched_by_parent.get(entry.url, []),
                   history=[], watched=False, min_total=index.min_total,
                   without_quorum=views.is_without_quorum(detail, entry, index.min_total))
        for item in watched:
            if item.detail and item.url not in {e.url for e in index.entries}:
                render("detail.html", detail_page(item.url), detail=item.detail, entry=None,
                       published_amendments=[], collecting_amendments=[], history=[], watched=False,
                       **views.trend_context(helper, item.detail))

        shutil.copytree(_HERE / "static", out / "static")
        search_index = {
            "prefixes": {normalize_prefix(e.prefix): detail_page(e.url) for e in index.entries},
            "urls": {url: detail_page(url) for url in known},
        }
        (out / "static" / "suchindex.json").write_text(json.dumps(search_index, ensure_ascii=False), encoding="utf-8")
        (out / "static" / "stand.json").write_text(
            stand.dump(fp, helper, built_at, all_runs, requests, stand.history(helper, watch_urls), warnungen),
            encoding="utf-8")
        (out / ".nojekyll").write_text("", encoding="utf-8")
        return pages
