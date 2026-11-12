"""Sharepic (SVG, 1080 × 1350) zum Mitzeichnen eines Antrags in der Sammelphase.

Enthält Titel, fehlende Personen/Frauen, Stand und Frist, einen QR-Code zum Original auf
antraege.gruene.de und den Hinweis auf KI und den Antragshelper. Keine Namen. Schriften sind
Systemschriften, damit der Browser das SVG ohne Nachladen in ein PNG umwandeln kann.
"""
from __future__ import annotations

import re
import textwrap
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import segno
from jinja2 import Environment, FileSystemLoader

from .models import Detail
from .trend import frist_text

BREITE, HOEHE = 1080, 1350
NUTZBREITE = 960
SITE_URL = "https://alexschnapper.github.io/grueneantragshelper/"

_env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=True)


def textlaenge(text: str, groesse: int, max_breite: int = NUTZBREITE) -> Optional[int]:
    """Stauchen per `textLength`, falls der Text geschätzt breiter als `max_breite` wird (sonst None)."""
    faktor = 0.62 if text.isupper() else 0.52
    return max_breite if len(text) * groesse * faktor > max_breite else None


def zeilen(text: str, breite: int, max_zeilen: int) -> List[str]:
    lines = textwrap.wrap(text, breite)
    if len(lines) > max_zeilen:
        lines = lines[:max_zeilen]
        lines[-1] = lines[-1].rstrip(" ,–-") + " …"
    return lines


def qr_pfad(url: str) -> "tuple[str, int]":
    """QR-Code als ein SVG-Pfad (Module 1 × 1) und seine Kantenlänge in Modulen."""
    matrix = list(segno.make(url, error="m").matrix_iter(border=0))
    teile = [f"M{x} {y}h1v1h-1z" for y, row in enumerate(matrix) for x, dark in enumerate(row) if dark]
    return "".join(teile), len(matrix)


def kopf(detail: Detail) -> "tuple[str, str]":
    """('ÄNDERUNGSANTRAG ZU VR-01', 'Aus der Dürre …') bzw. ('ANTRAG', Titel)."""
    m = re.match(r"Änderungsantrag (zu \S+): (.+)$", detail.title)
    if m:
        return f"ÄNDERUNGSANTRAG {m.group(1).upper()}", m.group(2)
    return ("ÄNDERUNGSANTRAG" if detail.kind == "amendment" else "ANTRAG"), detail.title


def svg(detail: Detail, stand_zeit: datetime, frist: Optional[datetime] = None) -> str:
    q = detail.quorum
    if q is None or q.reached:
        raise ValueError("Sharepic nur für Anträge in der Sammelphase")
    art, titel = kopf(detail)
    titelzeilen = zeilen(titel, 34, 3)
    qr, module = qr_pfad(detail.url)
    spalten = [("personen", q.missing_total, "Personen fehlen", f"{q.current_total} von {q.min_total} sind dabei",
                q.progress_total)]
    if q.min_women is not None:
        spalten.append(("frauen", q.missing_women, "Frauen fehlen", f"{q.current_women} von {q.min_women} Frauen sind dabei",
                        q.progress_women or 0.0))
    # Karten: eine breite in der Mitte oder zwei nebeneinander (x, Breite)
    lagen = [(240, 600)] if len(spalten) == 1 else [(60, 460), (560, 460)]
    spalten = [s + lage for s, lage in zip(spalten, lagen)]
    stand = f"Stand {stand_zeit.strftime('%d.%m.%Y, %H:%M Uhr')}"
    if frist:
        stand += f" · Antragsschluss {frist_text(frist)}"
    return _env.get_template("sharepic.svg").render(
        breite=BREITE, hoehe=HOEHE, art=art, art_breite=min(NUTZBREITE, len(art) * 20 + 80),
        titelzeilen=[(z, textlaenge(z, 48)) for z in titelzeilen],
        spalten=spalten, stand=stand, stand_laenge=textlaenge(stand, 22, 680),
        qr=qr, qr_module=module, site_url=SITE_URL,
    )
