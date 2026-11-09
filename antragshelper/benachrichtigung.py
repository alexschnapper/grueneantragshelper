"""Benachrichtigungen über neue Frühwarnungen an Messenger-Webhooks (nur beim Build, z. B. GitHub Actions).

Webhook-URLs sind Zugangsdaten: Sie kommen aus der Umgebung (GitHub-Secret `ANTRAGSHELPER_WEBHOOKS`),
stehen nie im Repo und werden nie ausgegeben. Eine Zeile pro Ziel: `<art> <url>`.

Arten:
- `json`: POST {"text": …} – Chatbegrünung/Rocket.Chat, Mattermost, Slack (Incoming Webhook)
- `discord`: POST {"content": …}
- `ntfy`: POST Klartext an ein ntfy-Thema (Push-App auf dem Handy)
- `get`: GET mit angehängtem `text=` – CallMeBot (WhatsApp/Signal an die eigene Nummer), Telegram-Bot
  (`…/sendMessage?chat_id=…`)
- `signal-cli`: POST an signal-cli-rest-api `/v2/send?number=…&recipients=…` (auch Signal-Gruppen)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import httpx

ARTEN = ("json", "discord", "ntfy", "get", "signal-cli")


@dataclass(frozen=True)
class Webhook:
    art: str
    url: str


def parse(text: str) -> List[Webhook]:
    """Liest die Zeilen `<art> <url>`; leere Zeilen und #-Kommentare werden ignoriert."""
    hooks = []
    for nummer, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        art, _, url = line.partition(" ")
        url = url.strip()
        # Fehlermeldung ohne URL, sie ist ein Geheimnis
        if art not in ARTEN or not url.startswith("https://"):
            raise ValueError(f"Webhook in Zeile {nummer}: erwartet „<{'|'.join(ARTEN)}> https://…“")
        hooks.append(Webhook(art, url))
    return hooks


def request(hook: Webhook, titel: str, text: str) -> httpx.Request:
    """Die HTTP-Anfrage für ein Ziel (ohne sie zu senden)."""
    nachricht = f"{titel}\n{text}"
    if hook.art == "json":
        return httpx.Request("POST", hook.url, json={"text": nachricht})
    if hook.art == "discord":
        return httpx.Request("POST", hook.url, json={"content": nachricht})
    if hook.art == "ntfy":
        return httpx.Request("POST", httpx.URL(hook.url).copy_add_param("title", titel), content=text.encode())
    if hook.art == "get":
        return httpx.Request("GET", httpx.URL(hook.url).copy_add_param("text", nachricht))
    url = httpx.URL(hook.url)
    recipients = [r for r in url.params.get("recipients", "").split(",") if r]
    return httpx.Request("POST", url.copy_with(query=None),
                         json={"message": nachricht, "number": url.params.get("number"), "recipients": recipients})


def senden(hooks: Sequence[Webhook], nachrichten: Sequence[Tuple[str, str]], user_agent: str,
           client: httpx.Client = None) -> Tuple[int, int]:
    """Schickt jede Nachricht an jedes Ziel; Fehler brechen nichts ab. Gibt (gesendet, fehlgeschlagen) zurück."""
    if not hooks or not nachrichten:
        return 0, 0
    own = client is None
    client = client or httpx.Client(timeout=15.0, headers={"User-Agent": user_agent})
    ok = failed = 0
    try:
        for titel, text in nachrichten:
            for hook in hooks:
                try:
                    client.send(request(hook, titel, text)).raise_for_status()
                    ok += 1
                except httpx.HTTPError:
                    failed += 1
    finally:
        if own:
            client.close()
    return ok, failed
