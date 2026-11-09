"""Verbindet Abruf, Parser und Speicher – wird von Web-Oberfläche und CLI genutzt."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from . import trend
from .client import AntragsgruenClient, SourceError
from .config import Settings
from .models import ActivityEntry, ConsultationIndex, Detail, IndexEntry
from .parsers import parse_activitylog, parse_detail, parse_index
from .store import Store


# Obergrenzen, damit antraege.gruene.de nicht unnötig belastet wird
MAX_ACTIVITY_PAGES = 5
STATS_DELAY_SECONDS = 1.0
STATS_MIN_INTERVAL = timedelta(hours=3)


@dataclass
class RefreshState:
    running: bool = False
    done: int = 0
    total: int = 0
    errors: List[str] = field(default_factory=list)


@dataclass
class WatchedItem:
    url: str
    title: str
    detail: Optional[Detail]
    error: Optional[str] = None


class Antragshelper:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AntragsgruenClient(settings)
        self.store = Store(settings.db_path)
        self.refresh_state = RefreshState()

    def index(self) -> ConsultationIndex:
        html = self.client.get(self.settings.consultation_url, self.settings.ttl_index,
                               "Antragsliste und Tagesordnung (Startseite)")
        return parse_index(html, self.settings.base_url)

    def resolve(self, query: str) -> Tuple[Optional[str], Optional[IndexEntry]]:
        """Kürzel oder Link -> URL der Antragsseite (und Index-Eintrag, falls bekannt)."""
        query = query.strip()
        if query.startswith(("http://", "https://")):
            if not self.client.is_own_url(query):
                raise SourceError("Nur Links auf " + self.settings.base_url + " werden ausgewertet.")
            url = query.split("#")[0].rstrip("/")
            return url, next((e for e in self.index().entries if e.url == url), None)
        entry = self.index().find(query)
        return (entry.url, entry) if entry else (None, None)

    def detail(self, url: str, purpose: str = "Auswertung eines Antrags") -> Detail:
        detail = parse_detail(self.client.get(url, self.settings.ttl_detail, purpose), url)
        self.store.record(detail)
        return detail

    def watchlist(self) -> List[WatchedItem]:
        items = []
        for row in self.store.watched():
            try:
                items.append(WatchedItem(row["url"], row["title"],
                                         self.detail(row["url"], "Beobachteter Antrag in der Sammelphase")))
            except SourceError as e:
                items.append(WatchedItem(row["url"], row["title"], None, str(e)))
        return items

    def amendments_of(self, motion_url: str) -> Tuple[List[IndexEntry], List[WatchedItem]]:
        """Veröffentlichte Änderungsanträge (aus dem Index) und beobachtete in der Sammelphase.

        Sammelphase-ÄA sind in Antragsgrün `userInvisible` und tauchen auf keiner öffentlichen
        Seite auf; sie werden über ihre URL (`<antrag-url>/<id>`) dem Antrag zugeordnet.
        """
        published = [
            e for e in self.index().amendments if e.url.startswith(motion_url + "/")
        ]
        published_urls = {e.url for e in published}
        watched = [
            i for i in self.watchlist()
            if i.url.startswith(motion_url + "/") and i.url not in published_urls
        ]
        return published, watched

    def hochrechnung(self, detail: Detail, jetzt: Optional[datetime] = None) -> Optional[trend.Trend]:
        """Trend bis zur Frist aus den gespeicherten Ständen (None außerhalb der Sammelphase)."""
        q = detail.quorum
        if q is None or q.reached or q.current_total is None:
            return None
        verlauf = [
            trend.Stand(datetime.fromisoformat(r["fetched_at"]), r["current_total"], r["current_women"])
            for r in self.store.history(detail.url) if r["current_total"] is not None
        ]
        aktuell = trend.Stand(jetzt or datetime.now().replace(microsecond=0), q.current_total, q.current_women)
        return trend.hochrechnen(verlauf, aktuell, q.min_total, q.min_women, self.settings.frist_fuer(detail.kind))

    @staticmethod
    def needs_support(items: List[WatchedItem]) -> List[WatchedItem]:
        """Beobachtete Anträge in der Sammelphase, die mit den wenigsten Fehlenden zuerst."""
        collecting = [i for i in items if i.detail and i.detail.collecting]
        return sorted(collecting, key=lambda i: i.detail.quorum.still_needed)

    def activity(self, pages: int = 1) -> List[ActivityEntry]:
        """Die neuesten `pages` Seiten des Aktivitäts-Protokolls (je ca. 20 Einträge)."""
        entries: List[ActivityEntry] = []
        for page in range(max(1, min(pages, MAX_ACTIVITY_PAGES))):
            url = f"{self.settings.consultation_url}/activitylog?page={page}"
            found = parse_activitylog(self.client.get(url, self.settings.ttl_index, "Aktivitäts-Protokoll"),
                                      self.settings.base_url)
            if not found:
                break
            entries.extend(found)
        return entries

    def stats_refresh_available_at(self) -> Optional[datetime]:
        """Zeitpunkt, ab dem die Dashboard-Zahlen erneut abgerufen werden dürfen (None = jetzt)."""
        last = self.store.published_stats_updated()
        if last is None or datetime.now() - last >= STATS_MIN_INTERVAL:
            return None
        return last + STATS_MIN_INTERVAL

    def start_stats_refresh(self) -> bool:
        """Ruft die Einzelseiten aller veröffentlichten Mitglieder-Anträge langsam im Hintergrund ab."""
        if self.refresh_state.running or self.stats_refresh_available_at() is not None:
            return False
        entries = [e for e in self.index().entries if e.submitter == "Mitglieder" and not e.withdrawn]
        self.refresh_state = RefreshState(running=True, total=len(entries))
        threading.Thread(target=self._refresh_stats, args=(entries,), daemon=True).start()
        return True

    def _refresh_stats(self, entries: List[IndexEntry]) -> None:
        state = self.refresh_state
        try:
            for entry in entries:
                try:
                    detail = parse_detail(
                        self.client.get(entry.url, self.settings.ttl_detail, "Quorum-Zahlen eines Mitglieder-Antrags"),
                        entry.url,
                    )
                    self.store.save_published_stat(entry, detail)
                except SourceError as e:
                    state.errors.append(str(e))
                state.done += 1
                time.sleep(STATS_DELAY_SECONDS)
        finally:
            state.running = False
