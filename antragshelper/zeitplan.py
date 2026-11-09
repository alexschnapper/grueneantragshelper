"""Zeitplan der GitHub-Action – muss zu `.github/workflows/pages.yml` passen (siehe tests/test_zeitplan.py)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

CHECK_MINUTE = 23          # stündliche Prüfung: cron "23 * * * *"
NIGHTLY_UTC = (2, 41)      # nächtlicher Sicherheits-Build: cron "41 2 * * *"


def next_check(now: datetime) -> datetime:
    candidate = now.replace(minute=CHECK_MINUTE, second=0, microsecond=0)
    return candidate if candidate > now else candidate + timedelta(hours=1)


def next_nightly(now: datetime) -> datetime:
    utc = now.astimezone(timezone.utc)
    candidate = utc.replace(hour=NIGHTLY_UTC[0], minute=NIGHTLY_UTC[1], second=0, microsecond=0)
    if candidate <= utc:
        candidate += timedelta(days=1)
    return candidate.astimezone(now.tzinfo)
