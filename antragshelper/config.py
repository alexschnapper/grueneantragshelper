from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


@dataclass(frozen=True)
class Fristen:
    """Antragsschluss einer Konferenz (lokale Zeit). Änderungsanträge haben meist eine spätere Frist."""

    antraege: Optional[datetime] = None
    aenderungsantraege: Optional[datetime] = None

    def fuer(self, kind: str) -> Optional[datetime]:
        if kind == "amendment" and self.aenderungsantraege:
            return self.aenderungsantraege
        return self.antraege


# Fristen je Konferenz-Pfad (`ANTRAGSHELPER_CONSULTATION`) für die Hochrechnung. Sie stehen auf der
# Startseite nur als Freitext und werden deshalb hier gepflegt. Für weitere Parteitage, LDKs oder
# Kreismitgliederversammlungen einen Eintrag ergänzen; ohne Eintrag gibt es keine Prognose.
FRISTEN: Dict[str, Fristen] = {
    # https://antraege.gruene.de/52bdk – Dringlichkeitsanträge (20.11., 03.12.) sind nicht abgebildet
    "52bdk": Fristen(
        antraege=datetime(2026, 10, 9, 11, 59),
        aenderungsantraege=datetime(2026, 11, 13, 11, 59),
    ),
}


@dataclass(frozen=True)
class Settings:
    base_url: str = field(default_factory=lambda: os.environ.get("ANTRAGSHELPER_BASE_URL", "https://antraege.gruene.de").rstrip("/"))
    consultation: str = field(default_factory=lambda: os.environ.get("ANTRAGSHELPER_CONSULTATION", "52bdk"))
    db_path: Path = field(default_factory=lambda: Path(os.environ.get("ANTRAGSHELPER_DB", "data/antragshelper.sqlite3")))
    repo_url: str = "https://github.com/alexschnapper/grueneantragshelper"
    # Adresse der GitHub-Pages-Seite, für absolute Links im Feed `warnungen.xml`
    site_url: str = field(default_factory=lambda: os.environ.get(
        "ANTRAGSHELPER_SITE_URL", "https://alexschnapper.github.io/grueneantragshelper").rstrip("/"))
    user_agent: str = "grueneantragshelper/0.1 (+https://github.com/alexschnapper/grueneantragshelper)"
    # Cache-Dauer in Sekunden, damit Neuladen keine Last auf antraege.gruene.de erzeugt
    ttl_index: int = 300
    ttl_detail: int = 120
    # Abweichende Fristen (z. B. in Tests); sonst gilt der Eintrag aus FRISTEN
    fristen: Optional[Fristen] = None
    # Wege, Anträge ohne GitHub-Konto vorzuschlagen (stehen öffentlich auf der Seite; leer = Button ausgeblendet).
    # Signal nur als Benutzername oder Benutzernamen-Link (https://signal.me/#eu/…), nie mit Telefonnummer.
    vorschlag_mail: str = "xy29m6nsi@mozmail.com"  # Firefox-Relay-Alias, leitet weiter
    vorschlag_threema: str = "UBK44SB7"  # öffentliche Threema-ID
    vorschlag_signal: str = "https://signal.me/#eu/33gqd5m61KSbd74K2v2AwzmPBamjFlQd7oFR54Bq5YyYzTr02dpD2J2oTT2QoCDY"
    # Teilen im Fediverse: voreingestellte Mastodon-Instanz (im Browser änderbar) und angehängte Hashtags
    mastodon_instanz: str = "gruene.social"
    teilen_hashtags: str = "#BDK #52BDK #Grüne #BDK52"

    @property
    def consultation_url(self) -> str:
        return f"{self.base_url}/{self.consultation}"

    def frist_fuer(self, kind: str) -> Optional[datetime]:
        return (self.fristen or FRISTEN.get(self.consultation, Fristen())).fuer(kind)


settings = Settings()
