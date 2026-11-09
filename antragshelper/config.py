from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    base_url: str = field(default_factory=lambda: os.environ.get("ANTRAGSHELPER_BASE_URL", "https://antraege.gruene.de").rstrip("/"))
    consultation: str = field(default_factory=lambda: os.environ.get("ANTRAGSHELPER_CONSULTATION", "52bdk"))
    db_path: Path = field(default_factory=lambda: Path(os.environ.get("ANTRAGSHELPER_DB", "data/antragshelper.sqlite3")))
    repo_url: str = "https://github.com/alexschnapper/grueneantragshelper"
    user_agent: str = "grueneantragshelper/0.1 (+https://github.com/alexschnapper/grueneantragshelper)"
    # Cache-Dauer in Sekunden, damit Neuladen keine Last auf antraege.gruene.de erzeugt
    ttl_index: int = 300
    ttl_detail: int = 120

    @property
    def consultation_url(self) -> str:
        return f"{self.base_url}/{self.consultation}"


settings = Settings()
