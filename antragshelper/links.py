"""Links für den Server-Modus und den statischen Export (GitHub Pages) aus denselben Templates."""
from __future__ import annotations

import hashlib
import re
from typing import AbstractSet, Optional
from urllib.parse import quote, urlencode, urlparse


def slug(text: str, length: int = 40) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower().replace("ä", "ae").replace("ö", "oe")
                  .replace("ü", "ue").replace("ß", "ss")).strip("-")[:length].strip("-")
    return f"{base}-{hashlib.md5(text.encode()).hexdigest()[:6]}"


def detail_page(url: str) -> str:
    """'https://…/52bdk/antrag-123/25769' -> 'antrag/antrag-123--25769.html'."""
    parts = urlparse(url).path.strip("/").split("/")[1:]
    return "antrag/" + "--".join(parts) + ".html"


def list_page(art: str = "", top: str = "", stand: str = "") -> str:
    return f"liste/{art or 'alle'}_{slug(top) if top else 'alle'}_{stand or 'alle'}.html"


class Links:
    """`href(name, **params)` in Templates.

    Im statischen Modus sind Links relativ zu `root` (z. B. '../' für Unterordner);
    Auswertungen, die nicht exportiert wurden, verlinken direkt auf antraege.gruene.de.
    """

    def __init__(self, static: bool = False, root: str = "", known: Optional[AbstractSet[str]] = None):
        self.static = static
        self.root = root
        self.known = known or set()

    def __call__(self, name: str, **params: str) -> str:
        if not self.static:
            path = {"index": "/", "dashboard": "/dashboard", "aktivitaet": "/aktivitaet",
                    "transparenz": "/transparenz"}.get(name)
            if path:
                return path
            if name == "auswertung":
                return "/auswertung?url=" + quote(params["url"], safe="")
            if name == "liste":
                query = urlencode({k: v for k, v in params.items() if v})
                return "/liste" + ("?" + query if query else "")
            if name == "static":
                return "/static/" + params["path"]
            raise KeyError(name)

        page = {"index": "index.html", "dashboard": "dashboard.html", "aktivitaet": "aktivitaet.html",
                "transparenz": "transparenz.html"}.get(name)
        if page:
            return self.root + page
        if name == "auswertung":
            url = params["url"]
            return self.root + detail_page(url) if url in self.known else url
        if name == "liste":
            return self.root + list_page(params.get("art", ""), params.get("top", ""), params.get("stand", ""))
        if name == "static":
            return self.root + "static/" + params["path"]
        raise KeyError(name)
