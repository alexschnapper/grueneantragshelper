"""Kennzahlen für das Dashboard – reine Berechnung, kein Abruf."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from statistics import median
from typing import Dict, List, Optional, Sequence, Tuple

from .models import ActivityEntry, ConsultationIndex, agenda_label


@dataclass
class BarRow:
    label: str
    values: List[int]  # je Serie, gestapelt
    title: str = ""
    link: Optional[Tuple[str, Dict[str, str]]] = None  # Argumente für href() im Template

    @property
    def total(self) -> int:
        return sum(self.values)


@dataclass
class QuorumPoint:
    """Ein veröffentlichter Mitglieder-(Änderungs-)Antrag; Frauenzahl aus gerundetem % geschätzt."""

    prefix: str
    kind: str
    url: str
    supporters: int
    women_share: int
    min_total: int
    min_women: int

    @property
    def persons(self) -> int:
        return self.supporters + 1  # inkl. Antragsteller*in, auf die sich der Frauenanteil bezieht

    @property
    def women(self) -> int:
        return round(self.women_share * self.persons / 100)

    @property
    def buffer_total(self) -> int:
        return self.supporters - self.min_total

    @property
    def buffer_women(self) -> int:
        return self.women - self.min_women

    @property
    def buffer(self) -> int:
        return min(self.buffer_total, self.buffer_women)

    @property
    def meets(self) -> bool:
        return self.buffer_total >= 0 and self.buffer_women >= 0


@dataclass
class Dashboard:
    counts: Dict[str, int] = field(default_factory=dict)
    per_agenda_motions: List[BarRow] = field(default_factory=list)
    per_agenda_amendments: List[BarRow] = field(default_factory=list)
    women_histogram: List[BarRow] = field(default_factory=list)
    women_median: Optional[float] = None
    women_parity: Dict[str, str] = field(default_factory=dict)
    most_amended: List[BarRow] = field(default_factory=list)
    activity_days: List[BarRow] = field(default_factory=list)
    quorum_points: List[QuorumPoint] = field(default_factory=list)

    @property
    def supporters_median(self) -> Optional[float]:
        return median(p.supporters for p in self.quorum_points) if self.quorum_points else None


def _per_agenda(index: ConsultationIndex, kind: str, art: str) -> List[BarRow]:
    rows = []
    for item in index.agenda_items:
        entries = [e for e in index.entries if e.kind == kind and e.agenda_item == item]
        if not entries:
            continue
        withdrawn = sum(e.withdrawn for e in entries)
        label = agenda_label(item).replace("im ", "").replace("in „", "„")
        rows.append(BarRow(label, [len(entries) - withdrawn, withdrawn], item, ("liste", {"art": art, "top": item})))
    return rows


def _women_histogram(index: ConsultationIndex) -> List[BarRow]:
    rows = []
    for lower in range(0, 100, 10):
        upper = 100 if lower == 90 else lower + 9
        values = [
            sum(1 for e in index.entries if e.kind == kind and not e.withdrawn
                and e.women_share is not None and lower <= e.women_share <= upper)
            for kind in ("motion", "amendment")
        ]
        rows.append(BarRow(f"{lower}", values, f"Frauenanteil {lower}–{upper} %"))
    return rows


def _most_amended(index: ConsultationIndex, limit: int = 10) -> List[BarRow]:
    rows = []
    for group in index.group_amendments(index.amendments):
        if group.motion is None:
            continue
        rows.append(BarRow(
            group.motion.prefix, [group.active_count, group.withdrawn_count], group.label,
            ("auswertung", {"url": group.motion.url}),
        ))
    return sorted(rows, key=lambda r: -r.total)[:limit]


def _activity_days(entries: Sequence[ActivityEntry], today: date) -> List[BarRow]:
    per_day: Dict[date, List[int]] = {}
    for e in entries:
        day = e.day(today)
        if day is not None:
            per_day.setdefault(day, [0, 0])[1 if e.is_amendment else 0] += 1
    if not per_day:
        return []
    rows, day = [], min(per_day)
    while day <= max(per_day):
        rows.append(BarRow(day.strftime("%d.%m."), per_day.get(day, [0, 0]), day.strftime("%d.%m.%Y")))
        day += timedelta(days=1)
    return rows


def build(
    index: ConsultationIndex,
    activity: Sequence[ActivityEntry],
    published_stats: Sequence[sqlite3.Row],
    today: Optional[date] = None,
) -> Dashboard:
    today = today or date.today()
    active = [e for e in index.entries if not e.withdrawn]
    shares = [e.women_share for e in active if e.women_share is not None]
    dash = Dashboard(
        counts={
            "motions": len(index.motions),
            "amendments": len(index.amendments),
            "withdrawn": len(index.entries) - len(active),
            "motions_body": sum(1 for e in index.motions if e.submitter == "Gremium"),
            "motions_members": sum(1 for e in index.motions if e.submitter == "Mitglieder"),
            "amendments_body": sum(1 for e in index.amendments if e.submitter == "Gremium"),
            "amendments_members": sum(1 for e in index.amendments if e.submitter == "Mitglieder"),
        },
        per_agenda_motions=_per_agenda(index, "motion", "antraege"),
        per_agenda_amendments=_per_agenda(index, "amendment", "aenderungsantraege"),
        women_histogram=_women_histogram(index),
        women_median=median(shares) if shares else None,
        most_amended=_most_amended(index),
        activity_days=_activity_days(activity, today),
    )
    for kind, label in (("motion", "Anträge"), ("amendment", "Änderungsanträge")):
        ks = [e.women_share for e in active if e.kind == kind and e.women_share is not None]
        dash.women_parity[label] = f"{sum(s >= 50 for s in ks)} von {len(ks)}"

    if index.min_total is not None and index.min_women is not None:
        dash.quorum_points = sorted(
            (
                QuorumPoint(r["prefix"], r["kind"], r["url"], r["supporter_count"], r["women_share"],
                            index.min_total, index.min_women)
                for r in published_stats
                if r["supporter_count"] is not None and r["women_share"] is not None
            ),
            key=lambda p: p.buffer,
        )
    return dash
