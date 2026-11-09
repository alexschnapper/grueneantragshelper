"""Stand der veröffentlichten Seite (`static/stand.json`) für sparsame Aktualisierung.

Die GitHub-Action prüft stündlich nur einen Fingerabdruck (Seite 1 des Aktivitäts-
Protokolls + beobachtete Direktlinks) und baut nur bei Änderungen neu. Die Feeds
taugen dafür nicht: Sie sind nach Anlegedatum sortiert, spät veröffentlichte
Anträge fehlen in den 20 neuesten Einträgen.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import httpx

from .client import FetchRecord
from .parsers import parse_activitylog
from .service import Antragshelper

VERSION = 1
# So lange gelten abgerufene Mitantragsteller*innen-Zahlen, bevor sie neu geholt werden
STATS_MAX_AGE = timedelta(days=7)
# So viele Läufe bleiben für die Transparenzseite in stand.json erhalten
MAX_RUNS = 200
CHECK_PURPOSE = "Prüfung auf Änderungen (vorheriger Schritt)"


def fingerprint(helper: Antragshelper, watch_urls: List[str]) -> Dict:
    """Ändert sich, sobald etwas veröffentlicht wird oder sich ein beobachteter Stand ändert."""
    url = f"{helper.settings.consultation_url}/activitylog?page=0"
    entries = parse_activitylog(
        helper.client.get(url, helper.settings.ttl_index, "Prüfung auf Änderungen (Aktivitäts-Protokoll)"),
        helper.settings.base_url,
    )
    activity = hashlib.sha256(
        json.dumps([[e.url, e.action] for e in entries], ensure_ascii=False).encode()
    ).hexdigest()
    watched = {}
    for watch_url in watch_urls:
        q = helper.detail(watch_url, "Prüfung auf Änderungen (beobachteter Antrag)").quorum
        watched[watch_url] = [q.current_total, q.current_women, q.reached] if q else None
    return {"aktivitaet": activity, "beobachtet": watched}


def load(source: Optional[str]) -> Optional[Dict]:
    """Lädt einen früheren Stand aus Datei oder URL (z. B. der GitHub-Pages-Seite)."""
    if not source:
        return None
    try:
        if source.startswith(("http://", "https://")):
            response = httpx.get(source, timeout=20.0, follow_redirects=True)
            response.raise_for_status()
            data = response.json()
        else:
            data = json.loads(Path(source).read_text(encoding="utf-8"))
    except (httpx.HTTPError, OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("version") == VERSION else None


def reusable_stats(previous: Optional[Dict], now: Optional[datetime] = None) -> Dict[str, Dict]:
    """Zahlen aus dem früheren Stand, die noch jung genug sind."""
    now = now or datetime.now()
    stats = {}
    for url, row in ((previous or {}).get("stats") or {}).items():
        try:
            fetched = datetime.fromisoformat(row["fetched_at"])
        except (KeyError, TypeError, ValueError):
            continue
        if now - fetched < STATS_MAX_AGE:
            stats[url] = row
    return stats


def request_rows(log: List[FetchRecord], tz=None) -> List[Dict]:
    """Abrufprotokoll als einfache Zeilen (Pfad statt voller URL, Zeit in `tz`)."""
    return [
        {
            "zeit": r.when.astimezone(tz).isoformat(timespec="seconds"),
            "zweck": r.purpose,
            "pfad": urlparse(r.url).path + (f"?{urlparse(r.url).query}" if urlparse(r.url).query else ""),
            "url": r.url,
            "status": r.status,
            "bytes": r.size,
            "ms": r.duration_ms,
        }
        for r in log
    ]


def run_record(anlass: str, started: datetime, finished: datetime, log: List[FetchRecord],
               check_requests: int = 0) -> Dict:
    """Ein Lauf für die Transparenzseite: Anlass, Abrufe je Zweck, Datenmenge, Dauer."""
    per_purpose = Counter(r.purpose for r in log)
    if check_requests:
        per_purpose[CHECK_PURPOSE] += check_requests
    return {
        "zeit": started.isoformat(timespec="seconds"),
        "anlass": anlass,
        "abrufe": dict(per_purpose),
        "gesamt": sum(per_purpose.values()),
        "bytes": sum(r.size for r in log),
        "dauer_s": round((finished - started).total_seconds(), 1),
    }


def runs(previous: Optional[Dict], current: Dict) -> List[Dict]:
    """Bisherige Läufe aus dem früheren Stand plus der aktuelle (älteste zuerst)."""
    earlier = [r for r in ((previous or {}).get("laeufe") or []) if isinstance(r, dict)]
    return (earlier + [current])[-MAX_RUNS:]


def dump(fp: Dict, helper: Antragshelper, built_at: datetime, all_runs: List[Dict],
         requests: List[Dict]) -> str:
    stats = {
        r["url"]: {"supporter_count": r["supporter_count"], "women_share": r["women_share"], "fetched_at": r["fetched_at"]}
        for r in helper.store.published_stats()
    }
    return json.dumps(
        {
            "version": VERSION,
            "built_at": built_at.isoformat(timespec="seconds"),
            "fingerprint": fp,
            "stats": stats,
            "laeufe": all_runs,
            "abrufe_letzter_lauf": requests,
        },
        ensure_ascii=False,
    )
