"""Template-Kontexte, gemeinsam genutzt von Web-Server (web.py) und statischem Export (build.py)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import AbstractSet, Callable, List, Optional, Sequence

from . import charts, dashboard, stand, trend, zeitplan
from .client import FetchRecord
from .links import sharepic_page
from .models import (ActivityEntry, ConsultationIndex, Detail, IndexEntry, active_first, agenda_label,
                     group_activity)
from .service import MAX_ACTIVITY_PAGES, STATS_DELAY_SECONDS, Antragshelper, WatchedItem

KINDS = {"antraege": "motion", "aenderungsantraege": "amendment"}


def is_without_quorum(detail: Detail, entry: Optional[IndexEntry], min_total: Optional[int]) -> bool:
    """Veröffentlichter Mitglieder-Antrag mit weniger Mitantragsteller*innen als das Quorum."""
    return (
        entry is not None and entry.submitter == "Mitglieder" and detail.quorum is None
        and detail.supporter_count is not None and min_total is not None
        and detail.supporter_count < min_total
    )
STATES = {"aktiv": False, "zurueckgezogen": True}


def overview(index: ConsultationIndex, watched: List[WatchedItem], trends: Optional[dict] = None) -> dict:
    """`trends`: URL -> Trend der beobachteten Anträge in der Sammelphase (Frühwarnungen daraus)."""
    trends = trends or {}
    needs_support = Antragshelper.needs_support(watched)
    return {
        "index": index,
        "per_agenda": index.by_agenda_item(),
        "needs_support": needs_support,
        "watched": watched,
        "trends": trends,
        "warnings": [(i, trends[i.url]) for i in needs_support if trends.get(i.url) and trends[i.url].warnung],
    }


def trend_context(helper: Antragshelper, detail: Detail) -> dict:
    """Hochrechnung, Verlaufsdiagramm und Mobilisierungs-Text für die Auswertungsseite."""
    t = helper.hochrechnung(detail)
    q = detail.quorum
    verlauf = (charts.progress_lines(list(reversed(helper.store.history(detail.url))), q.min_total, q.min_women)
               if detail.collecting else None)
    return {
        "trend": t,
        "verlauf_chart": verlauf,  # None bei weniger als zwei gespeicherten Ständen
        "mobilisierung": trend.mobilisierung(detail.title, detail.url, detail.kind, t) if t else None,
        "aufruf_frauen": trend.aufruf_frauen(detail.title, detail.url, detail.kind, t) if t else None,
        "zahl": trend.zahl,
        "restzeit_text": trend.restzeit_text,
        "sharepic_name": sharepic_page(detail.url, "")[len("sharepic/"):-1],
    }


def listing(index: ConsultationIndex, art: str = "", top: str = "", stand: str = "", text: str = "",
            without_quorum: AbstractSet[str] = frozenset()) -> dict:
    entries = index.filter(kind=KINDS.get(art), agenda_item=top, withdrawn=STATES.get(stand), text=text)
    heading = {"antraege": "Anträge", "aenderungsantraege": "Änderungsanträge"}.get(art, "Anträge und Änderungsanträge")
    if top:
        heading += " " + agenda_label(top)
    motions = active_first([e for e in entries if e.kind == "motion"])
    return {
        "heading": heading,
        "total": len(entries),
        "motions": [e for e in motions if not e.withdrawn],
        "withdrawn_motions": [e for e in motions if e.withdrawn],
        "amendment_groups": index.group_amendments([e for e in entries if e.kind == "amendment"]),
        "agenda_items": index.agenda_items,
        "without_quorum": without_quorum,
        "f": {"art": art, "top": top, "stand": stand, "text": text},
    }


def activity(entries: Sequence[ActivityEntry], seiten: int, typ: str = "", text: str = "") -> dict:
    needle = text.strip().lower()
    entries = [
        e for e in entries
        if (typ != "antrag" or not e.is_amendment)
        and (typ != "aenderungsantrag" or e.is_amendment)
        and (not needle or needle in e.motion.lower() or needle in e.action.lower())
    ]
    return {
        "groups": group_activity(entries),
        "total": len(entries),
        "max_pages": MAX_ACTIVITY_PAGES,
        "f": {"seiten": seiten, "typ": typ, "text": text},
    }


def dashboard_page(
    helper: Antragshelper,
    index: ConsultationIndex,
    activity_entries: Sequence[ActivityEntry],
    watched: List[WatchedItem],
    href: Callable[..., str],
) -> dict:
    dash = dashboard.build(index, activity_entries, helper.store.published_stats())
    scatter = (
        charts.quorum_scatter(dash.with_quorum, index.min_total, index.min_women, href)
        if dash.with_quorum else None
    )
    progress = []
    for item in helper.needs_support(watched):
        q = item.detail.quorum
        chart = charts.progress_lines(list(reversed(helper.store.history(item.url))), q.min_total, q.min_women)
        progress.append((item, chart))
    return {
        "index": index,
        "dash": dash,
        "scatter": scatter,
        "progress": progress,
        "refresh": helper.refresh_state,
        "refresh_available_at": helper.stats_refresh_available_at(),
        "stats_updated": helper.store.published_stats_updated(),
    }


def _parse_runs(all_runs: Sequence[dict], tz) -> List[dict]:
    """Läufe (neueste zuerst) mit `when` als datetime in `tz`."""
    parsed = []
    for run in reversed(list(all_runs)):
        try:
            when = datetime.fromisoformat(run["zeit"]).astimezone(tz)
        except (KeyError, TypeError, ValueError):
            continue
        parsed.append({**run, "when": when})
    return parsed


def transparency(all_runs: Sequence[dict], requests: Sequence[dict], now: datetime, static: bool) -> dict:
    runs = _parse_runs(all_runs, now.tzinfo)
    rows = [{**r, "when": datetime.fromisoformat(r["zeit"]).astimezone(now.tzinfo)} for r in requests]
    return {
        "runs": runs,
        "requests": sorted(rows, key=lambda r: r["when"], reverse=True),
        "last_24h": sum(r["gesamt"] for r in runs if now - r["when"] <= timedelta(hours=24)),
        "last_7d": sum(r["gesamt"] for r in runs if now - r["when"] <= timedelta(days=7)),
        "next_check": zeitplan.next_check(now) if static else None,
        "next_nightly": zeitplan.next_nightly(now) if static else None,
        "check_minute": zeitplan.CHECK_MINUTE,
        "nightly_utc": "%02d:%02d" % zeitplan.NIGHTLY_UTC,
        "stats_max_age_days": stand.STATS_MAX_AGE.days,
        "stats_delay": STATS_DELAY_SECONDS,
    }


def footer_static(run: dict, now: datetime) -> dict:
    """Footer der statischen Seite: letzter Lauf und nächste geplante Prüfung."""
    return {
        "last_run": _parse_runs([run], now.tzinfo)[0],
        "next_check": zeitplan.next_check(now),
        "check_minute": zeitplan.CHECK_MINUTE,
    }


def footer_server(log: Sequence[FetchRecord]) -> dict:
    """Footer der lokalen App: letzter tatsächlicher Abruf in dieser Sitzung."""
    return {"last_fetch": log[-1] if log else None, "session_count": len(log)}
