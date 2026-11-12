"""Hochrechnung für Anträge in der Sammelphase: Sammeltempo, Prognose zur Frist, Ampel.

Rein rechnerisch und nachvollziehbar, ohne Schätzmodell. Grundlage sind die lokal gespeicherten
Stände (nur Zahlen, keine Namen). Gespeichert wird nur bei Änderungen, ein Stand gilt also bis
zum nächsten – das Tempo ist der Zuwachs zwischen dem Stand zu Beginn des Fensters und jetzt.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Sequence

# Rollierende Fenster für das Sammeltempo; bei kürzerem Verlauf zählt der ganze Verlauf. Gerechnet wird
# vorsichtig mit dem langsameren der beiden Tempi: Sammeln läuft in Schüben (Aufruf, dann Abflachen),
# ein kurzer Schub soll nicht über Tage hochgerechnet werden
FENSTER = timedelta(hours=24)
FENSTER_LANG = timedelta(hours=72)
# Kürzer beobachtet ergibt kein belastbares Tempo
MIN_BEOBACHTUNG = timedelta(hours=1)
# Eine Ampel erst ab so viel Verlauf (oder so viel, wie bis zur Frist bleibt) – sonst wird z. B.
# ein Abend-Tempo über Tage hochgerechnet und die Prognose ist nur vorläufig
BELASTBAR_AB = timedelta(hours=12)
# Prognose im Verhältnis zum Quorum: ab 110 % stabil, ab 90 % knapp, darunter gefährdet
GRUEN_AB = 1.10
GELB_AB = 0.90

# Ab hier warnt die App auch ohne gelbe/rote Ampel, solange noch Personen fehlen; fehlen Frauen,
# früher, weil Frauennetzwerke (LAG, Frauenrat) Zeit zum Weiterleiten brauchen
WARNUNG_VOR_FRIST = timedelta(hours=48)
WARNUNG_VOR_FRIST_FRAUEN = timedelta(hours=72)

GRUEN, GELB, ROT = "gruen", "gelb", "rot"
FRIST = "frist"  # Warnstufe: Frist naht (48 bzw. 72 Stunden), Prognose noch vorläufig
WARNSTUFEN = {ROT: "Rot · Scheitern droht", GELB: "Gelb · gefährdet", FRIST: "Frist läuft ab"}


@dataclass(frozen=True)
class Stand:
    zeit: datetime
    gesamt: int
    frauen: Optional[int] = None


@dataclass(frozen=True)
class Tempo:
    """Zuwachs pro Stunde im Messzeitraum."""

    gesamt: float
    frauen: Optional[float]
    stunden: float
    seit_beginn: bool  # True: Verlauf kürzer als das Fenster, gemessen seit dem ersten Stand


def tempo(verlauf: Sequence[Stand], aktuell: Stand, fenster: timedelta = FENSTER) -> Optional[Tempo]:
    """Sammeltempo bis `aktuell` (None, wenn weniger als `MIN_BEOBACHTUNG` Verlauf vorliegt)."""
    punkte = sorted((s for s in verlauf if s.zeit <= aktuell.zeit), key=lambda s: s.zeit)
    if not punkte:
        return None
    beginn = aktuell.zeit - fenster
    vorher = [s for s in punkte if s.zeit <= beginn]
    if vorher:
        start, seit_beginn = Stand(beginn, vorher[-1].gesamt, vorher[-1].frauen), False
    else:
        start, seit_beginn = punkte[0], True
    dauer = aktuell.zeit - start.zeit
    if dauer < MIN_BEOBACHTUNG:
        return None
    stunden = dauer.total_seconds() / 3600
    frauen = None
    if aktuell.frauen is not None and start.frauen is not None:
        frauen = (aktuell.frauen - start.frauen) / stunden
    return Tempo((aktuell.gesamt - start.gesamt) / stunden, frauen, stunden, seit_beginn)


def vorsichtiges_tempo(verlauf: Sequence[Stand], aktuell: Stand) -> Optional[Tempo]:
    """Das jeweils langsamere Tempo aus 24- und 72-Stunden-Fenster (gesamt und Frauen getrennt)."""
    kurz, lang = tempo(verlauf, aktuell, FENSTER), tempo(verlauf, aktuell, FENSTER_LANG)
    if kurz is None or lang is None:
        return kurz or lang
    frauen = None
    if kurz.frauen is not None and lang.frauen is not None:
        frauen = min(kurz.frauen, lang.frauen)
    return Tempo(min(kurz.gesamt, lang.gesamt), frauen, lang.stunden, lang.seit_beginn)


@dataclass(frozen=True)
class Hochrechnung:
    """Ein Quorum (gesamt oder Frauen) hochgerechnet auf die Frist."""

    minimum: int
    stand: int
    tempo: Optional[float]  # pro Stunde; None = zu wenig Verlauf
    restzeit: Optional[float]  # Stunden bis zur Frist; None = keine Frist bekannt
    belastbar: bool = True  # False: Verlauf zu kurz, Prognose nur vorläufig (keine Ampel)

    @property
    def bedarf(self) -> int:
        return max(0, self.minimum - self.stand)

    @property
    def prognose(self) -> Optional[float]:
        if self.tempo is None or self.restzeit is None:
            return None
        return max(0.0, self.stand + self.tempo * max(0.0, self.restzeit))

    @property
    def fehlen_zur_frist(self) -> Optional[int]:
        """Voraussichtlich fehlende Personen zum Fristende (aufgerundet)."""
        if self.prognose is None:
            return None
        return math.ceil(round(max(0.0, self.minimum - self.prognose), 6))

    @property
    def noetige_rate(self) -> Optional[float]:
        """Personen pro Stunde, die ab jetzt mindestens nötig sind."""
        if self.restzeit is None or self.restzeit <= 0:
            return None
        return self.bedarf / self.restzeit

    @property
    def verfehlt(self) -> bool:
        """Das Quorum wird bei diesem Tempo (belastbar gerechnet) bis zur Frist nicht erreicht."""
        if self.bedarf == 0:
            return False
        if self.restzeit is not None and self.restzeit <= 0:
            return True
        return self.belastbar and self.prognose is not None and self.prognose < self.minimum

    @property
    def ampel(self) -> Optional[str]:
        if self.bedarf == 0:
            return GRUEN
        if self.restzeit is not None and self.restzeit <= 0:
            return ROT
        if self.prognose is None or self.minimum <= 0 or not self.belastbar:
            return None
        anteil = self.prognose / self.minimum
        return GRUEN if anteil >= GRUEN_AB else GELB if anteil >= GELB_AB else ROT


@dataclass(frozen=True)
class Trend:
    frist: Optional[datetime]
    tempo: Optional[Tempo]
    gesamt: Hochrechnung
    frauen: Optional[Hochrechnung]
    ampel_ab: Optional[datetime] = None  # ab wann es eine Ampel gibt, solange der Verlauf zu kurz ist

    @property
    def massgeblich(self) -> Hochrechnung:
        """Das Frauenquorum, falls es eines gibt, sonst das Gesamtquorum."""
        return self.frauen or self.gesamt

    @property
    def ampel(self) -> Optional[str]:
        """Der schlechteste Stand beider Quoren (Rot vor Gelb vor „noch keine Ampel“ vor Grün);
        Rot auch, wenn das Gesamtquorum bei diesem Tempo nicht erreicht wird."""
        if self.gesamt.verfehlt:
            return ROT
        teile = [self.gesamt.ampel] + ([self.frauen.ampel] if self.frauen is not None else [])
        for stufe in (ROT, GELB, None):
            if stufe in teile:
                return stufe
        return GRUEN

    @property
    def warnstufe(self) -> Optional[str]:
        """Rot/Gelb wie die Ampel; FRIST, wenn die Frist naht (72 Stunden, falls Frauen fehlen, sonst 48)
        und die Ampel nicht grün ist."""
        if self.ampel in (GELB, ROT):
            return self.ampel
        frauen_fehlen = self.frauen is not None and self.frauen.bedarf > 0
        if not (self.gesamt.bedarf or frauen_fehlen) or self.ampel == GRUEN:
            return None
        vorlauf = WARNUNG_VOR_FRIST_FRAUEN if frauen_fehlen else WARNUNG_VOR_FRIST
        restzeit = self.gesamt.restzeit
        if restzeit is not None and 0 < restzeit <= vorlauf.total_seconds() / 3600:
            return FRIST
        return None

    @property
    def warnung(self) -> Optional[str]:
        """'Achtung: Gesamtfortschritt bei 75 %, Frauenquorum bei 61 % – noch 18 Frauen nötig, Frist …'."""
        if self.warnstufe is None:
            return None
        g, f = self.gesamt, self.frauen
        lage = f"Gesamtfortschritt bei {_prozent(g)} %"
        if f is not None:
            lage += f", Frauenquorum bei {_prozent(f)} %"
        if f is not None and f.bedarf:
            fehlt = f"noch {f.bedarf} Frauen nötig"
            if g.bedarf > f.bedarf:
                fehlt += f" (insgesamt {g.bedarf})"
        else:
            fehlt = f"noch {g.bedarf} Personen nötig"
        frist = f", Frist {frist_text(self.frist)}" if self.frist else ""
        return f"Achtung: {lage} – {fehlt}{frist}."

    @property
    def empfehlung(self) -> Optional[str]:
        """Klartext mit Handlungsempfehlung bei gelber oder roter Ampel (sonst None)."""
        if self.ampel not in (GELB, ROT):
            return None
        f, g = self.frauen, self.gesamt
        # Das Quorum, an dem es hakt: Frauen, wenn deren Ampel nicht grün ist, sonst gesamt
        h = f if f is not None and f.ampel in (GELB, ROT) else g
        wer = "Frauen" if h is f else "Personen"
        if h.restzeit is not None and h.restzeit <= 0:
            return f"Die Frist ist abgelaufen, es fehlen noch {h.bedarf} {wer}."
        if h.fehlen_zur_frist:
            prognose = f"fehlen zum Fristende voraussichtlich {h.fehlen_zur_frist} {wer}"
            if h is f and not g.fehlen_zur_frist:
                prognose += ", obwohl das Gesamtquorum rechnerisch erreichbar ist"
        else:
            prognose = f"wird das Quorum zum Fristende voraussichtlich nur knapp erreicht ({h.prognose:.0f} von {h.minimum})"
        saetze = [f"Bei aktuellem Sammeltempo ({zahl(h.tempo)} {wer}/h) {prognose}.",
                  f"Ab jetzt sind mindestens {zahl(h.noetige_rate)} {wer}/h nötig."]
        if h is f and g.fehlen_zur_frist:
            saetze.append(f"Auch insgesamt fehlen voraussichtlich {g.fehlen_zur_frist} Personen.")
        if self.ampel == GELB:
            saetze.append("Gezielte Ansprache vorbereiten.")
        elif f is not None and f.ampel == ROT:
            saetze.append("Sofortige Mobilisierung über Frauen-Verteiler.")
        else:
            saetze.append("Sofortige Mobilisierung nötig.")
        return " ".join(saetze)


def hochrechnen(verlauf: Sequence[Stand], aktuell: Stand, min_gesamt: int, min_frauen: Optional[int],
                frist: Optional[datetime]) -> Trend:
    t = vorsichtiges_tempo(verlauf, aktuell)
    restzeit = (frist - aktuell.zeit).total_seconds() / 3600 if frist else None
    noetig = BELASTBAR_AB.total_seconds() / 3600
    if restzeit is not None:
        noetig = min(noetig, max(0.0, restzeit))
    belastbar = t is not None and t.stunden >= noetig
    gesamt = Hochrechnung(min_gesamt, aktuell.gesamt, t.gesamt if t else None, restzeit, belastbar)
    frauen = None
    if min_frauen is not None and aktuell.frauen is not None:
        frauen = Hochrechnung(min_frauen, aktuell.frauen, t.frauen if t else None, restzeit, belastbar)
    return Trend(frist, t, gesamt, frauen, None if belastbar else _ampel_ab(verlauf, aktuell, frist))


def _ampel_ab(verlauf: Sequence[Stand], aktuell: Stand, frist: Optional[datetime]) -> Optional[datetime]:
    """Zeitpunkt, ab dem der Verlauf reicht: 12 Stunden nach dem ersten Stand oder – wenn die Frist
    vorher naht – sobald der Verlauf so lang ist wie die Restzeit (Mitte zwischen erstem Stand und Frist)."""
    erste = min((s.zeit for s in verlauf if s.zeit <= aktuell.zeit), default=aktuell.zeit)
    ab = erste + BELASTBAR_AB
    if frist is not None:
        ab = min(ab, erste + (frist - erste) / 2)
    return max(ab, aktuell.zeit) if frist is None or ab < frist else None


def mobilisierung(titel: str, url: str, kind: str, trend: Trend) -> Optional[str]:
    """Kurzer, ermutigender Text für Messenger oder Mail (None, wenn nichts mehr fehlt)."""
    g, f = trend.gesamt, trend.frauen
    if f is not None and f.bedarf:
        fehlt = f"noch {_mitantragstellerinnen(f.bedarf)}, um das Frauenquorum zu sichern"
        if g.bedarf > f.bedarf:
            fehlt += f" (insgesamt fehlen noch {g.bedarf} Mitantragsteller*innen)"
    elif g.bedarf:
        fehlt = f"noch {g.bedarf} Mitantragsteller*innen, um das Quorum zu erreichen"
    else:
        return None
    bis = f" bis {frist_text(trend.frist)}" if trend.frist and g.restzeit and g.restzeit > 0 else ""
    return f"{_unser(titel, kind)} braucht noch Rückenwind: Es fehlen{bis} {fehlt}. Hier kannst du mitzeichnen: {url}"


def aufruf_frauen(titel: str, url: str, kind: str, trend: Trend) -> Optional[str]:
    """Gezielter Aufruf an Frauennetzwerke: nur die fehlenden Frauen, Frist relativ ('bis morgen 11:59 Uhr').

    None, wenn keine Frauen fehlen oder keine Frist (mehr) offen ist. Die Anrede ergänzt das Team selbst.
    """
    f = trend.frauen
    if f is None or not f.bedarf or trend.frist is None or f.restzeit is None or f.restzeit <= 0:
        return None
    jetzt = trend.frist - timedelta(hours=f.restzeit)
    unser = _unser(titel, kind)
    return (f"Inhaltlich steht {unser[0].lower()}{unser[1:]} – uns fehlen bis {frist_relativ(trend.frist, jetzt)} "
            f"nur noch {_mitantragstellerinnen(f.bedarf)}: {url}")


def _prozent(h: Hochrechnung) -> int:
    return min(100, h.stand * 100 // h.minimum) if h.minimum > 0 else 100


def _mitantragstellerinnen(anzahl: int) -> str:
    return f"{anzahl} Mitantragstellerin" if anzahl == 1 else f"{anzahl} Mitantragstellerinnen"


def _unser(titel: str, kind: str) -> str:
    """'Änderungsantrag zu VR-01: Titel' -> 'Unser Änderungsantrag zu VR-01 („Titel“)'."""
    if kind != "amendment":
        return f"Unser Antrag „{titel}“"
    m = re.match(r"Änderungsantrag (zu \S+): (.+)$", titel)
    return f"Unser Änderungsantrag {m.group(1)} („{m.group(2)}“)" if m else f"Unser Änderungsantrag „{titel}“"


def zahl(wert: Optional[float]) -> str:
    """1.25 -> '1,3' (eine Nachkommastelle, deutsches Komma)."""
    return "–" if wert is None else f"{wert:.1f}".replace(".", ",")


def frist_text(frist: datetime) -> str:
    return frist.strftime("%d.%m.%Y, %H:%M Uhr")


WOCHENTAGE = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")


def frist_relativ(frist: datetime, jetzt: datetime) -> str:
    """'heute 11:59 Uhr', 'morgen 11:59 Uhr', 'Freitag 11:59 Uhr' (diese Woche) oder '13.11.2026, 11:59 Uhr'."""
    tage = (frist.date() - jetzt.date()).days
    uhrzeit = frist.strftime("%H:%M Uhr")
    if tage == 0:
        return f"heute {uhrzeit}"
    if tage == 1:
        return f"morgen {uhrzeit}"
    if 1 < tage < 7:
        return f"{WOCHENTAGE[frist.weekday()]} {uhrzeit}"
    return frist_text(frist)


def restzeit_text(stunden: float) -> str:
    if stunden <= 0:
        return "Frist abgelaufen"
    if stunden >= 48:
        return f"noch {stunden / 24:.0f} Tage bis Fristende"
    if stunden >= 1:
        return f"noch {stunden:.0f} Stunden bis Fristende"
    return f"noch {stunden * 60:.0f} Minuten bis Fristende"
