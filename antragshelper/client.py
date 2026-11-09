"""Schonender HTTP-Zugriff auf antraege.gruene.de mit kleinem In-Memory-Cache und Abrufprotokoll."""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from .config import Settings


class SourceError(Exception):
    pass


@dataclass
class FetchRecord:
    """Ein tatsächlicher Netzwerkabruf (Cache-Treffer werden nicht protokolliert)."""

    when: datetime
    url: str
    purpose: str
    status: Optional[int]
    size: int
    duration_ms: int


class AntragsgruenClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._http = httpx.Client(
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
            timeout=20.0,
        )
        self._cache: Dict[str, Tuple[float, str]] = {}
        self._lock = threading.Lock()
        self._log: Deque[FetchRecord] = deque(maxlen=500)

    def is_own_url(self, url: str) -> bool:
        """Nur URLs der konfigurierten Antragsgrün-Instanz werden abgerufen."""
        return urlparse(url).netloc == urlparse(self.settings.base_url).netloc

    def get(self, url: str, ttl: int, purpose: str = "Abruf") -> str:
        if not self.is_own_url(url):
            raise SourceError(f"Fremde URL wird nicht abgerufen: {url}")
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(url)
            if cached and now - cached[0] < ttl:
                return cached[1]
        started = datetime.now().astimezone()
        response = None
        try:
            response = self._http.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise SourceError(f"Abruf fehlgeschlagen: {url} ({e})") from e
        finally:
            self._log.append(FetchRecord(
                when=started,
                url=url,
                purpose=purpose,
                status=response.status_code if response is not None else None,
                size=len(response.content) if response is not None else 0,
                duration_ms=int((time.monotonic() - now) * 1000),
            ))
        with self._lock:
            self._cache[url] = (now, response.text)
        return response.text

    @property
    def log(self) -> List[FetchRecord]:
        return list(self._log)

    def close(self) -> None:
        self._http.close()
