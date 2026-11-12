"""HTML-/RSS-Parser für Antragsgrün-Seiten.

Selektoren und Texte stammen aus den Antragsgrün-Templates
(views/consultation, views/motion/view.php, views/amendment/view.php,
messages/de/motion.php). Personennamen werden nirgends ausgelesen.
"""
from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urljoin
from xml.etree import ElementTree

from bs4 import BeautifulSoup, Tag

from .models import ActivityEntry, ConsultationIndex, Detail, FeedItem, IndexEntry, Quorum

_WOMEN_SHARE = re.compile(r"Frauenanteil:\s*(\d+)\s*%")
_HINT_FEMALE = re.compile(
    r"mindestens\s+(\d+)\s+[^,]+?,\s*davon\s+(\d+)\s+Frauen\s*\(aktueller Stand:\s*(\d+)\s*/\s*(\d+)\)"
)
_HINT_PLAIN = re.compile(r"mindestens\s+(\d+)\s+[^(]+?\(aktueller Stand:\s*(\d+)\)")
_HINT_REACHED = re.compile(r"Mindestzahl[^(]*\((\d+)\)\s*wurde erreicht")
_MORE_SUPPORTERS = re.compile(r"(\d+)\s+weitere")
_CONSULTATION_QUORUM = re.compile(r"gemeinsam mit\s+(\d+)\s+\S+,\s*davon mindestens\s+(\d+)\s+Frauen")


def _text(node: Optional[Tag]) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def _women_share(node: Optional[Tag]) -> Optional[int]:
    m = _WOMEN_SHARE.search(_text(node))
    return int(m.group(1)) if m else None


def _status(node: Optional[Tag]) -> Optional[str]:
    """Text von `span.status` ohne verschachtelten Frauenanteil, z. B. '(Zurückgezogen)' -> 'Zurückgezogen'."""
    span = node.select_one(".status") if node else None
    if span is None:
        return None
    own = "".join(span.find_all(string=True, recursive=False)).strip(" ()")
    return own or None


def _submitter(info: Optional[Tag], women_share: Optional[int]) -> Optional[str]:
    """Gremien-Anträge tragen 'dort beschlossen am', Mitglieder-Anträge einen Frauenanteil."""
    if "beschlossen" in _text(info):
        return "Gremium"
    return "Mitglieder" if women_share is not None else None


def parse_index(html: str, base_url: str) -> ConsultationIndex:
    """Liest alle veröffentlichten Anträge/Änderungsanträge aus der Tagesordnung der Startseite."""
    soup = BeautifulSoup(html, "html.parser")
    index = ConsultationIndex()
    quorum = _CONSULTATION_QUORUM.search(_text(soup.select_one("#stdTextHolder") or soup.body or soup))
    if quorum:
        index.min_total, index.min_women = int(quorum.group(1)), int(quorum.group(2))
    for ul in soup.select("ul.motionListBelowAgenda"):
        heading = ul.find_previous_sibling("h2")
        agenda_item = _text(heading) or "Ohne Tagesordnungspunkt"
        for li in ul.find_all("li", class_="motion", recursive=False):
            link = li.select_one("p.title a[href]")
            if link is None:
                continue
            classes = li.get("class", [])
            is_amendment = any(c.startswith("amendmentRow") for c in classes)
            prefix = _text(link.select_one(".motionPrefix"))
            info = li.find("p", class_="info", recursive=False)
            withdrawn = "withdrawn" in classes
            women_share = _women_share(info)
            index.entries.append(
                IndexEntry(
                    prefix=prefix,
                    title=_text(link.select_one(".motionTitle")),
                    url=urljoin(base_url, link["href"]),
                    kind="amendment" if is_amendment else "motion",
                    agenda_item=agenda_item,
                    withdrawn=withdrawn,
                    women_share=women_share,
                    status=_status(info) or ("Zurückgezogen" if withdrawn else "Eingereicht"),
                    submitter=_submitter(info, women_share),
                )
            )
            for am in li.select("ul.amendments > li.amendment"):
                am_link = am.select_one("a.amendmentTitle[href]")
                if am_link is None:
                    continue
                am_withdrawn = "withdrawn" in am.get("class", [])
                am_info = am.select_one(".info")
                am_women = _women_share(am_info)
                index.entries.append(
                    IndexEntry(
                        prefix=_text(am_link),
                        title=f"Änderungsantrag zu {prefix}",
                        url=urljoin(base_url, am_link["href"]),
                        kind="amendment",
                        agenda_item=agenda_item,
                        withdrawn=am_withdrawn,
                        women_share=am_women,
                        parent_prefix=prefix,
                        parent_url=urljoin(base_url, link["href"]),
                        status=_status(am) or ("Zurückgezogen" if am_withdrawn else "Eingereicht"),
                        submitter=_submitter(am_info, am_women),
                    )
                )
    return index


def parse_quorum(hint_text: str) -> Optional[Quorum]:
    m = _HINT_FEMALE.search(hint_text)
    if m:
        min_total, min_women, cur_total, cur_women = map(int, m.groups())
        return Quorum(min_total, min_women, cur_total, cur_women)
    m = _HINT_PLAIN.search(hint_text)
    if m:
        min_total, cur_total = map(int, m.groups())
        return Quorum(min_total, current_total=cur_total)
    m = _HINT_REACHED.search(hint_text)
    if m:
        return Quorum(int(m.group(1)), reached=True)
    return None


AUSZUG_WOERTER = 15


def kuerzen(text: str, woerter: int = AUSZUG_WOERTER) -> str:
    words = text.split()
    return " ".join(words[:woerter]) + (" …" if len(words) > woerter else "")


def _section_text(section: Tag) -> str:
    """Text eines Abschnitts ohne Überschrift und Zeilennummern."""
    section = BeautifulSoup(str(section), "html.parser")
    for node in section.select("h2, h3, .lineNumber, ul.bookmarks"):
        node.decompose()
    return _text(section)


def _heading_section(soup: BeautifulSoup, heading: str) -> Optional[Tag]:
    for section in soup.select("section.motionTextHolder"):
        h = section.find(["h2", "h3"])
        if h is not None and _text(h).startswith(heading):
            return section
    return None


def _amendment_changes(soup: BeautifulSoup) -> Optional[str]:
    """'Von Zeile 31 bis 33: Streichen „…“ · Einfügen „…“' aus der Ansicht „Nur die Änderungen“."""
    sections = soup.select(".onlyChangedText section.paragraph")
    if not sections:
        return None
    parts = []
    for section in sections:
        summary = _text(section.select_one(".lineSummary")).rstrip(":")
        dels = [f"„{_text(d)}“" for d in section.find_all("del") if _text(d)]
        inss = [f"„{_text(i)}“" for i in section.find_all("ins") if _text(i)]
        change = " · ".join(filter(None, [
            "Streichen " + ", ".join(dels) if dels else "",
            "Einfügen " + ", ".join(inss) if inss else "",
        ])) or _section_text(section).replace(_text(section.select_one(".lineSummary")), "", 1).strip()
        parts.append((summary, change))
    first_summary = parts[0][0]
    rest = " / ".join([parts[0][1]] + [f"{summary}: {change}" for summary, change in parts[1:]])
    return f"{first_summary}: {kuerzen(rest)}" if first_summary else kuerzen(rest)


def _excerpts(soup: BeautifulSoup) -> "tuple[Optional[str], Optional[str]]":
    text = _amendment_changes(soup)
    if text is None:
        section = _heading_section(soup, "Antragstext")
        text = kuerzen(_section_text(section)) if section is not None else None
    reason = soup.select_one("#amendmentExplanation") or _heading_section(soup, "Begründung")
    reason_text = _section_text(reason) if reason is not None else ""
    return text or None, kuerzen(reason_text) if reason_text else None


def parse_detail(html: str, url: str) -> Detail:
    """Liest Rahmendaten und kurze Auszüge aus Antragstext und Begründung (ohne Namen)."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.motionDataTable")
    caption = _text(table.find("caption")) if table else ""
    detail = Detail(
        url=url,
        title=_text(soup.select_one("main h1") or soup.find("h1")),
        kind="amendment" if "Änderungsantrag" in caption else "motion",
    )
    detail.text_auszug, detail.begruendung_auszug = _excerpts(soup)
    if table is None:
        return detail

    status_cell = table.select_one("tr.statusRow td")
    if status_cell is not None:
        for small in status_cell.find_all("small"):
            small.extract()
        detail.status = _text(status_cell)

    parent_link = table.select_one("tr.motionRow td a[href]")
    if parent_link is not None:
        detail.parent_title = _text(parent_link)
        detail.parent_url = urljoin(url, parent_link["href"])

    detail.women_share = _women_share(table.select_one(".womenQuota"))
    more = _MORE_SUPPORTERS.search(_text(table.select_one(".moreSupporters")))
    if more:
        detail.supporter_count = int(more.group(1))

    hint = soup.select_one(".supportCollectionHint")
    if hint is not None:
        detail.quorum = parse_quorum(_text(hint))
    return detail


def parse_activitylog(html: str, base_url: str) -> List[ActivityEntry]:
    """Einträge des Aktivitäts-Protokolls; die handelnde Person wird weggelassen."""
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for item in soup.select("ul.activityLog > a.list-group-item"):
        date = item.select_one(".date")
        entries.append(
            ActivityEntry(
                when=(date.get("title") or _text(date)) if date else "",
                motion=_text(item.select_one(".motion")),
                action=_text(item.select_one(".description strong")),
                url=urljoin(base_url, item.get("href", "")),
            )
        )
    return entries


def parse_feed(xml: str) -> List[FeedItem]:
    """RSS-Feed (nur Titel und Link; Autor*innen und Text werden ignoriert)."""
    root = ElementTree.fromstring(xml.encode("utf-8"))
    return [
        FeedItem(title=(item.findtext("title") or "").strip(), url=(item.findtext("link") or "").strip())
        for item in root.iter("item")
    ]
