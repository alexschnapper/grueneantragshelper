"""SQLite-Speicher für Beobachtungsliste und Zahlenverlauf. Speichert keine Personennamen."""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import Detail, IndexEntry

_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlist (
    url TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    status TEXT,
    min_total INTEGER,
    min_women INTEGER,
    current_total INTEGER,
    current_women INTEGER,
    reached INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS snapshots_url ON snapshots (url, fetched_at);
-- Zahlen veröffentlichter Mitglieder-Anträge für das Dashboard (keine Namen)
CREATE TABLE IF NOT EXISTS published_stats (
    url TEXT PRIMARY KEY,
    prefix TEXT NOT NULL,
    kind TEXT NOT NULL,
    agenda_item TEXT NOT NULL,
    supporter_count INTEGER,
    women_share INTEGER,
    fetched_at TEXT NOT NULL
);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        # Eine Verbindung für Web-Threads und den Dashboard-Abruf, daher mit Lock
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._db.executescript(_SCHEMA)

    def _write(self, sql: str, params: tuple = ()) -> None:
        with self._lock, self._db:
            self._db.execute(sql, params)

    def _read(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, params).fetchall()

    def watch(self, url: str, title: str) -> None:
        self._write(
            "INSERT OR REPLACE INTO watchlist (url, title, added_at) VALUES (?, ?, ?)",
            (url, title, _now()),
        )

    def unwatch(self, url: str) -> None:
        self._write("DELETE FROM watchlist WHERE url = ?", (url,))

    def watched(self) -> List[sqlite3.Row]:
        return self._read("SELECT * FROM watchlist ORDER BY added_at")

    def is_watched(self, url: str) -> bool:
        return bool(self._read("SELECT 1 FROM watchlist WHERE url = ?", (url,)))

    def record(self, detail: Detail) -> None:
        """Speichert einen Stand, aber nur wenn er sich vom letzten unterscheidet."""
        q = detail.quorum
        row = (
            detail.status,
            q.min_total if q else None,
            q.min_women if q else None,
            q.current_total if q else None,
            q.current_women if q else None,
            int(q.reached) if q else 0,
        )
        with self._lock:
            last = self.latest(detail.url)
            if last is not None and tuple(last)[3:] == row:
                return
            self._write(
                "INSERT INTO snapshots (url, fetched_at, status, min_total, min_women,"
                " current_total, current_women, reached) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (detail.url, _now(), *row),
            )

    def latest(self, url: str) -> Optional[sqlite3.Row]:
        rows = self._read("SELECT * FROM snapshots WHERE url = ? ORDER BY id DESC LIMIT 1", (url,))
        return rows[0] if rows else None

    def history(self, url: str) -> List[sqlite3.Row]:
        return self._read("SELECT * FROM snapshots WHERE url = ? ORDER BY id DESC", (url,))

    def save_published_stat(self, entry: IndexEntry, detail: Detail) -> None:
        self._write(
            "INSERT OR REPLACE INTO published_stats (url, prefix, kind, agenda_item,"
            " supporter_count, women_share, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (entry.url, entry.prefix, entry.kind, entry.agenda_item,
             detail.supporter_count, detail.women_share, _now()),
        )

    def import_published_stat(self, entry: IndexEntry, supporter_count: Optional[int],
                              women_share: Optional[int], fetched_at: str) -> None:
        """Übernimmt eine Zahl aus einem früheren Stand (ohne neuen Abruf)."""
        self._write(
            "INSERT OR REPLACE INTO published_stats (url, prefix, kind, agenda_item,"
            " supporter_count, women_share, fetched_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (entry.url, entry.prefix, entry.kind, entry.agenda_item, supporter_count, women_share, fetched_at),
        )

    def published_stats(self) -> List[sqlite3.Row]:
        return self._read("SELECT * FROM published_stats ORDER BY prefix")

    def published_stats_updated(self) -> Optional[datetime]:
        rows = self._read("SELECT MAX(fetched_at) FROM published_stats")
        return datetime.fromisoformat(rows[0][0]) if rows and rows[0][0] else None


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
