"""Datenmodelle. Bewusst ohne Personennamen – nur Kürzel, Titel, URLs und Zahlen."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import List, Optional


def normalize_prefix(prefix: str) -> str:
    """'vr 01', 'VR-01', 'WO-RP 01' -> 'VR-01', 'WO-RP-01' (für die Suche)."""
    return re.sub(r"[\s\-–]+", "-", prefix.strip().upper())


@dataclass
class IndexEntry:
    """Ein Eintrag aus der Tagesordnung der Startseite (Antrag oder Änderungsantrag)."""

    prefix: str
    title: str
    url: str
    kind: str  # "motion" | "amendment"
    agenda_item: str
    withdrawn: bool = False
    women_share: Optional[int] = None
    parent_prefix: Optional[str] = None
    parent_url: Optional[str] = None
    # Auf der Startseite steht nur bei Abweichungen ein Status, sonst ist der Eintrag eingereicht
    status: str = "Eingereicht"
    submitter: Optional[str] = None  # "Gremium" | "Mitglieder" | None (unbekannt)


def active_first(entries: List[IndexEntry]) -> List[IndexEntry]:
    """Eingereichte zuerst, zurückgezogene ans Ende (sonst Reihenfolge der Tagesordnung)."""
    return sorted(entries, key=lambda e: e.withdrawn)


def agenda_label(agenda_item: str) -> str:
    """'TOP 02 - Verantwortung …' -> 'im TOP 02'; ohne TOP-Nummer -> 'in „…“'."""
    m = re.match(r"TOP\s*(\d+)", agenda_item)
    return f"im TOP {m.group(1)}" if m else f"in „{agenda_item}“"


@dataclass
class AmendmentGroup:
    """Änderungsanträge zu einem Antrag (bzw. eigenständige ÄA eines Tagesordnungspunkts)."""

    label: str
    motion: Optional[IndexEntry]
    entries: List[IndexEntry] = field(default_factory=list)

    @property
    def withdrawn_count(self) -> int:
        return sum(1 for e in self.entries if e.withdrawn)

    @property
    def active_count(self) -> int:
        return len(self.entries) - self.withdrawn_count


@dataclass
class ConsultationIndex:
    entries: List[IndexEntry] = field(default_factory=list)
    # Quorum für Mitglieder-Anträge laut Startseite (z. B. 91 / 46)
    min_total: Optional[int] = None
    min_women: Optional[int] = None

    @property
    def motions(self) -> List[IndexEntry]:
        return [e for e in self.entries if e.kind == "motion"]

    @property
    def amendments(self) -> List[IndexEntry]:
        return [e for e in self.entries if e.kind == "amendment"]

    def find(self, prefix: str) -> Optional[IndexEntry]:
        key = normalize_prefix(prefix)
        for entry in self.entries:
            if normalize_prefix(entry.prefix) == key:
                return entry
        return None

    @property
    def agenda_items(self) -> List[str]:
        return list(dict.fromkeys(e.agenda_item for e in self.entries))

    def filter(
        self,
        kind: Optional[str] = None,
        agenda_item: Optional[str] = None,
        withdrawn: Optional[bool] = None,
        text: str = "",
    ) -> List[IndexEntry]:
        needle = text.strip().lower()
        return [
            e for e in self.entries
            if (kind is None or e.kind == kind)
            and (not agenda_item or e.agenda_item == agenda_item)
            and (withdrawn is None or e.withdrawn == withdrawn)
            and (not needle or needle in e.prefix.lower() or needle in e.title.lower())
        ]

    def group_amendments(self, amendments: List[IndexEntry]) -> List[AmendmentGroup]:
        """Gruppiert ÄA nach Hauptantrag; Gruppen ohne eingereichte ÄA kommen ans Ende."""
        groups: "dict[str, AmendmentGroup]" = {}
        for e in amendments:
            if e.parent_url:
                key = e.parent_url
                if key not in groups:
                    motion = next((m for m in self.motions if m.url == key), None)
                    title = motion.title if motion else ""
                    groups[key] = AmendmentGroup(f"{e.parent_prefix}: {title}".rstrip(": "), motion)
            else:
                key = f"agenda:{e.agenda_item}"
                if key not in groups:
                    groups[key] = AmendmentGroup(f"{e.agenda_item} – eigenständige Änderungsanträge", None)
            groups[key].entries.append(e)
        for group in groups.values():
            group.entries = active_first(group.entries)
        return sorted(groups.values(), key=lambda g: g.active_count == 0)

    def by_agenda_item(self) -> "dict[str, dict[str, int]]":
        stats: dict = {}
        for e in self.entries:
            row = stats.setdefault(e.agenda_item, {"motions": 0, "amendments": 0, "withdrawn": 0})
            row["motions" if e.kind == "motion" else "amendments"] += 1
            if e.withdrawn:
                row["withdrawn"] += 1
        return stats


@dataclass
class Quorum:
    min_total: int
    min_women: Optional[int] = None
    current_total: Optional[int] = None
    current_women: Optional[int] = None
    reached: bool = False

    @property
    def missing_total(self) -> int:
        if self.reached or self.current_total is None:
            return 0
        return max(0, self.min_total - self.current_total)

    @property
    def missing_women(self) -> int:
        if self.reached or self.min_women is None or self.current_women is None:
            return 0
        return max(0, self.min_women - self.current_women)

    @property
    def open_any_gender(self) -> int:
        """Plätze, die von Personen beliebigen Geschlechts besetzt werden können."""
        return max(0, self.missing_total - self.missing_women)

    @property
    def still_needed(self) -> int:
        """Wie viele Personen mindestens noch unterschreiben müssen."""
        return max(self.missing_total, self.missing_women)

    @property
    def progress_total(self) -> float:
        if self.reached:
            return 1.0
        if not self.min_total or self.current_total is None:
            return 0.0
        return min(1.0, self.current_total / self.min_total)

    @property
    def progress_women(self) -> Optional[float]:
        if self.reached:
            return 1.0
        if not self.min_women or self.current_women is None:
            return None
        return min(1.0, self.current_women / self.min_women)


@dataclass
class Detail:
    """Rahmendaten einer Antrags- oder Änderungsantragsseite."""

    url: str
    title: str
    kind: str  # "motion" | "amendment"
    status: Optional[str] = None
    women_share: Optional[int] = None
    supporter_count: Optional[int] = None
    parent_title: Optional[str] = None
    parent_url: Optional[str] = None
    quorum: Optional[Quorum] = None

    @property
    def collecting(self) -> bool:
        return self.quorum is not None and not self.quorum.reached


@dataclass
class ActivityEntry:
    when: str
    motion: str
    action: str
    url: str

    def day(self, today: Optional[date] = None) -> Optional[date]:
        """'Heute, 12:20' / 'Gestern, 09:00' / '04.11.2026, 16:18' -> Datum."""
        today = today or date.today()
        if self.when.startswith("Heute"):
            return today
        if self.when.startswith("Gestern"):
            return today - timedelta(days=1)
        m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", self.when)
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None

    @property
    def is_amendment(self) -> bool:
        return self.action.startswith("Änderungsantrag")


@dataclass
class ActivityGroup:
    """Alle Aktivitäten zu einem Antrag (z. B. viele veröffentlichte ÄA zu W-04)."""

    motion: str
    entries: List[ActivityEntry] = field(default_factory=list)

    @property
    def latest(self) -> ActivityEntry:
        return self.entries[0]

    @property
    def amendment_count(self) -> int:
        return sum(1 for e in self.entries if e.is_amendment)

    @property
    def motion_url(self) -> str:
        """Änderungsantrags-URLs haben die Form `<antrag-url>/<id>`."""
        e = self.latest
        return e.url.rsplit("/", 1)[0] if e.is_amendment else e.url


def group_activity(entries: List[ActivityEntry]) -> List[ActivityGroup]:
    """Fasst Einträge je Antrag zusammen; Reihenfolge nach jüngstem Eintrag."""
    groups: "dict[str, ActivityGroup]" = {}
    for entry in entries:
        groups.setdefault(entry.motion, ActivityGroup(entry.motion)).entries.append(entry)
    return list(groups.values())


@dataclass
class FeedItem:
    title: str
    url: str
