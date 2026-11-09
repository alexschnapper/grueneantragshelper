"""Serverseitig erzeugte SVG-Diagramme (ohne externe Bibliotheken).

Farben kommen über CSS-Klassen (.s1/.s2, .ref) aus style.css, damit Hell/Dunkel greift.
Jede Markierung trägt ein <title> als Hover-Tooltip.
"""
from __future__ import annotations

import math
from datetime import datetime
from html import escape
from typing import Callable, List, Optional, Sequence, Tuple

from markupsafe import Markup

from .dashboard import QuorumPoint

W, H = 640, 360
PAD_L, PAD_R, PAD_T, PAD_B = 48, 16, 16, 44


def _nice_max(value: float, ticks: int = 5) -> Tuple[float, float]:
    if value <= 0:
        return 1, 1
    raw = value / ticks
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    return math.ceil(value / step) * step, step


def _frame(x_max: float, y_max: float, x_step: float, y_step: float, x_label: str, y_label: str,
           x_fmt=lambda v: f"{v:g}") -> List[str]:
    sx = lambda v: PAD_L + v / x_max * (W - PAD_L - PAD_R)  # noqa: E731
    sy = lambda v: H - PAD_B - v / y_max * (H - PAD_T - PAD_B)  # noqa: E731
    out = []
    y = 0.0
    while y <= y_max + 1e-9:
        out.append(f'<line class="grid" x1="{PAD_L}" x2="{W - PAD_R}" y1="{sy(y):.1f}" y2="{sy(y):.1f}"/>'
                   f'<text class="tick" x="{PAD_L - 6}" y="{sy(y) + 4:.1f}" text-anchor="end">{y:g}</text>')
        y += y_step
    x = 0.0
    while x <= x_max + 1e-9:
        out.append(f'<text class="tick" x="{sx(x):.1f}" y="{H - PAD_B + 16}" text-anchor="middle">{escape(x_fmt(x))}</text>')
        x += x_step
    out.append(f'<line class="axis" x1="{PAD_L}" x2="{W - PAD_R}" y1="{H - PAD_B}" y2="{H - PAD_B}"/>')
    out.append(f'<text class="axis-label" x="{(PAD_L + W - PAD_R) / 2}" y="{H - 6}" text-anchor="middle">{escape(x_label)}</text>')
    out.append(f'<text class="axis-label" x="12" y="{(PAD_T + H - PAD_B) / 2}" text-anchor="middle" '
               f'transform="rotate(-90 12 {(PAD_T + H - PAD_B) / 2})">{escape(y_label)}</text>')
    return out


def _svg(parts: List[str], label: str) -> Markup:
    return Markup(f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{escape(label)}">'
                  + "".join(parts) + "</svg>")


def quorum_scatter(points: Sequence[QuorumPoint], min_total: int, min_women: int,
                   href: Callable[..., str]) -> Markup:
    """x = Mitantragsteller*innen, y = Frauen (geschätzt); Linien = Quorum."""
    x_max, x_step = _nice_max(max([p.supporters for p in points] + [min_total]) * 1.05)
    y_max, y_step = _nice_max(max([p.women for p in points] + [min_women]) * 1.1)
    sx = lambda v: PAD_L + v / x_max * (W - PAD_L - PAD_R)  # noqa: E731
    sy = lambda v: H - PAD_B - v / y_max * (H - PAD_T - PAD_B)  # noqa: E731
    parts = _frame(x_max, y_max, x_step, y_step, "Mitantragsteller*innen", "Frauen (geschätzt)")
    parts.append(f'<rect class="ok-zone" x="{sx(min_total):.1f}" y="{PAD_T}" '
                 f'width="{W - PAD_R - sx(min_total):.1f}" height="{sy(min_women) - PAD_T:.1f}"/>')
    parts.append(f'<line class="ref" x1="{sx(min_total):.1f}" x2="{sx(min_total):.1f}" y1="{PAD_T}" y2="{H - PAD_B}"/>'
                 f'<text class="ref-label" x="{sx(min_total) + 4:.1f}" y="{PAD_T + 12}">{min_total} gesamt</text>')
    parts.append(f'<line class="ref" x1="{PAD_L}" x2="{W - PAD_R}" y1="{sy(min_women):.1f}" y2="{sy(min_women):.1f}"/>'
                 f'<text class="ref-label" x="{W - PAD_R - 4}" y="{sy(min_women) - 6:.1f}" text-anchor="end">{min_women} Frauen</text>')
    for p in points:
        cls = "s1" if p.kind == "motion" else "s2"
        tip = (f"{p.prefix}: {p.supporters} Mitantragsteller*innen, ~{p.women} Frauen ({p.women_share} %)"
               f" · Puffer {p.buffer_total:+d} gesamt / {p.buffer_women:+d} Frauen")
        parts.append(f'<a href="{escape(href("auswertung", url=p.url), quote=True)}"><circle class="dot {cls}" '
                     f'cx="{sx(p.supporters):.1f}" cy="{sy(p.women):.1f}" r="5"><title>{escape(tip)}</title></circle></a>')
    return _svg(parts, "Streudiagramm: Mitantragsteller*innen und Frauen je Antrag mit Quorum-Linien")


def progress_lines(history: Sequence, min_total: Optional[int], min_women: Optional[int]) -> Optional[Markup]:
    """Verlauf eines beobachteten Antrags (Snapshots, älteste zuerst); None bei < 2 Punkten."""
    rows = [r for r in history if r["current_total"] is not None]
    if len(rows) < 2:
        return None
    times = [datetime.fromisoformat(r["fetched_at"]) for r in rows]
    t0, t1 = times[0], times[-1]
    span = max((t1 - t0).total_seconds(), 1)
    y_max, y_step = _nice_max(max([r["current_total"] for r in rows] + [min_total or 0]) * 1.1)
    sx = lambda t: PAD_L + (t - t0).total_seconds() / span * (W - PAD_L - PAD_R)  # noqa: E731
    sy = lambda v: H - PAD_B - v / y_max * (H - PAD_T - PAD_B)  # noqa: E731
    parts = _frame(1, y_max, 2, y_step, f"{t0:%d.%m. %H:%M} – {t1:%d.%m. %H:%M}", "Personen", x_fmt=lambda v: "")
    for ref, label in ((min_total, "nötig gesamt"), (min_women, "nötig Frauen")):
        if ref is not None:
            parts.append(f'<line class="ref" x1="{PAD_L}" x2="{W - PAD_R}" y1="{sy(ref):.1f}" y2="{sy(ref):.1f}"/>'
                         f'<text class="ref-label" x="{W - PAD_R - 4}" y="{sy(ref) - 6:.1f}" text-anchor="end">{ref} {label}</text>')
    for key, cls, name in (("current_total", "s1", "gesamt"), ("current_women", "s2", "Frauen")):
        pts = [(sx(t), sy(r[key])) for t, r in zip(times, rows) if r[key] is not None]
        if not pts:
            continue
        parts.append(f'<polyline class="line {cls}" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}"/>')
        for (x, y), t, r in zip(pts, times, rows):
            parts.append(f'<circle class="dot {cls}" cx="{x:.1f}" cy="{y:.1f}" r="4">'
                         f'<title>{t:%d.%m. %H:%M}: {r[key]} {name}</title></circle>')
        x, y = pts[-1]
        parts.append(f'<text class="direct-label" x="{min(x + 6, W - PAD_R - 40):.1f}" y="{y - 8:.1f}">{name}</text>')
    return _svg(parts, "Verlauf der Unterstützer*innen und Frauen über die Zeit")
