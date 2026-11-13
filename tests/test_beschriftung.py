"""Kleine Darstellungsfehler: Leerzeichen vor Satzzeichen und überlappende Diagrammbeschriftungen."""
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from antragshelper import charts
from antragshelper.models import Quorum

TEMPLATES = Path(__file__).parent.parent / "antragshelper" / "templates"


def _summary(q: Quorum) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    html = env.from_string('{% from "_quorum.html" import summary %}Noch {{ summary(q) }}.').render(q=q)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html))


def test_summary_ohne_leerzeichen_vor_punkt():
    assert _summary(Quorum(91, 46, 35, 12)) == "Noch 56 fehlen, davon mindestens 34 Frauen."
    assert _summary(Quorum(20, None, 7)) == "Noch 13 fehlen."
    assert _summary(Quorum(91, reached=True)) == "Noch Quorum erreicht (mindestens 91)."


def _verlauf(punkte):
    return [{"fetched_at": f"2026-11-{11 + i // 24:02d}T{i % 24:02d}:00:00", "current_total": g, "current_women": f}
            for i, (g, f) in zip(range(0, 48, 12), punkte)]


def _ref_labels(svg: str):
    return {m.group(4): (float(m.group(1)), m.group(3), float(m.group(2)))
            for m in re.finditer(r'<text class="ref-label" x="([\d.]+)" y="([\d.]+)" text-anchor="(\w+)">(\d+) nötig', svg)}


def _direct_labels(svg: str):
    return [(float(x), float(y)) for x, y in re.findall(r'<text class="direct-label" x="([\d.]+)" y="([\d.]+)"', svg)]


def test_namen_der_linien_rechtsbuendig():
    svg = str(charts.progress_lines(_verlauf([(70, 30), (80, 32), (88, 34), (96, 38)]), 91, 46))
    assert svg.count('class="direct-label"') == 2
    assert all(f'x="{charts.W - charts.PAD_R}"' in t and 'text-anchor="end"' in t
               for t in re.findall(r'<text class="direct-label"[^>]*>', svg))


def test_quorum_beschriftung_weicht_den_linien_aus():
    # Wie in der Demo: gesamt endet knapp über 91 – rechts wäre „91 nötig gesamt“ verdeckt
    svg = str(charts.progress_lines(_verlauf([(70, 30), (80, 32), (88, 34), (96, 38)]), 91, 46))
    labels = _ref_labels(svg)
    x91, anchor91, y91 = labels["91"]
    assert anchor91 == "start"  # nach links ausgewichen
    for x, y in _direct_labels(svg):
        assert abs(y - y91) >= charts.LABEL_ABSTAND or abs(x - x91) > 200


def test_quorum_beschriftung_bleibt_rechts_wenn_platz():
    svg = str(charts.progress_lines(_verlauf([(5, 2), (10, 4), (15, 6), (20, 8)]), 91, 46))
    assert {anchor for _, anchor, _ in _ref_labels(svg).values()} == {"end"}
