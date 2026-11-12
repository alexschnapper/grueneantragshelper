"""Anträge in der Sammelphase vorschlagen: Pages-Seite → vorausgefülltes GitHub-Issue → PR auf beobachtet.txt.

Dieselbe Regel prüft im Browser (`static.js`, das Muster kommt aus `muster()`) und im Workflow
`antrag-vorschlagen.yml` (über `python -m antragshelper vorschlag`), denn die Browser-Prüfung lässt sich umgehen.
Erlaubt ist nur ein Direktlink der Konferenz: Pfad aus Kleinbuchstaben, Ziffern und Bindestrichen, optional
`/<Zahl>`. Alles andere (andere Seiten, Emoji, Sonderzeichen, Skript- oder SQL-Schnipsel) wird abgelehnt.
"""
from __future__ import annotations

import re
from typing import Optional

MAX_LAENGE = 300
NICHT_GUELTIG = "Nicht gültig"


def muster(consultation_url: str) -> "re.Pattern[str]":
    return re.compile("^" + re.escape(consultation_url) + r"/[a-z0-9]+(?:-[a-z0-9]+)*(?:/[0-9]+)?$")


def pruefe(text: str, consultation_url: str, label: str) -> Optional[str]:
    """None, wenn der Link gültig ist, sonst die Meldung für die Eingabe."""
    link = text.strip()
    if len(link) <= MAX_LAENGE and muster(consultation_url).match(link):
        return None
    if re.match(r"^https?://", link, re.IGNORECASE) and not link.startswith(consultation_url + "/"):
        return f"Nur Links in Zusammenhang mit der {label}"
    return NICHT_GUELTIG


def link_aus_issue(body: str) -> Optional[str]:
    """Der Wert unter „### Direktlink“ aus einem Issue-Formular (None, wenn er fehlt)."""
    m = re.search(r"^###\s*Direktlink\s*$\s*(.*?)\s*(?:^###|\Z)", body or "", re.MULTILINE | re.DOTALL)
    if not m or not m.group(1) or m.group(1) == "_No response_":
        return None
    return m.group(1).strip()
