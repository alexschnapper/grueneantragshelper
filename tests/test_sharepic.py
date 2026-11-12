import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

from antragshelper import build, sharepic
from antragshelper.config import Fristen, Settings
from antragshelper.models import Detail, Quorum

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://antraege.gruene.de"
URL = f"{BASE}/52bdk/wasser-antrag-1/999"
STAND = datetime(2026, 11, 12, 14, 5)


def _detail(**kwargs):
    defaults = dict(url=URL, title="Änderungsantrag zu VR-01: Aus der Dürre lernen – Wasser sichern",
                    kind="amendment", quorum=Quorum(91, 46, 25, 9))
    defaults.update(kwargs)
    return Detail(**defaults)


def _text(svg):
    return " ".join(t.text or "" for t in ET.fromstring(svg).iter("{http://www.w3.org/2000/svg}text"))


def test_sharepic_inhalt():
    svg = sharepic.svg(_detail(), STAND, datetime(2026, 11, 13, 11, 59))
    text = _text(svg)
    assert "ÄNDERUNGSANTRAG ZU VR-01" in text and "Aus der Dürre lernen" in text
    assert "66 Personen fehlen" in text and "37 Frauen fehlen" in text
    assert "25 von 91 sind dabei" in text and "9 von 46 Frauen sind dabei" in text
    assert "Stand 12.11.2026, 14:05 Uhr · Antragsschluss 13.11.2026, 11:59 Uhr" in text
    assert "Jetzt mitzeichnen →" in text and "antraege.gruene.de" in text
    assert "Erstellt mit Unterstützung von KI und dem Grünen Antragshelper" in text
    assert "https://alexschnapper.github.io/grueneantragshelper/" in text
    assert 'width="1080" height="1350"' in svg


def test_sharepic_qr_code_und_escaping():
    svg = sharepic.svg(_detail(title='Mehr <Bahn> & "Bus"', kind="motion"), STAND)
    ET.fromstring(svg)  # gültiges XML trotz Sonderzeichen im Titel
    assert "Mehr &lt;Bahn&gt; &amp;" in svg
    path, module = sharepic.qr_pfad(URL)
    assert module >= 21 and path.count("h1v1h-1z") > 100 and path in svg


def test_sharepic_ohne_frauenquorum_und_ohne_frist():
    text = _text(sharepic.svg(_detail(quorum=Quorum(91, None, 60)), STAND))
    assert "31 Personen fehlen" in text and "Frauen" not in text
    assert "Antragsschluss" not in text


def test_sharepic_nur_in_sammelphase():
    with pytest.raises(ValueError):
        sharepic.svg(_detail(quorum=Quorum(91, reached=True)), STAND)
    with pytest.raises(ValueError):
        sharepic.svg(_detail(quorum=None), STAND)


def test_langer_titel_wird_gekuerzt():
    lines = sharepic.zeilen("Wort " * 60, 36, 3)
    assert len(lines) == 3 and lines[-1].endswith("…")


def test_sharepic_im_statischen_export(tmp_path, monkeypatch):
    pages = {
        f"{BASE}/52bdk": (FIXTURES / "home.html").read_text(encoding="utf-8"),
        f"{BASE}/52bdk/activitylog?page=0": (FIXTURES / "activitylog.html").read_text(encoding="utf-8"),
        URL: (FIXTURES / "amendment_collecting.html").read_text(encoding="utf-8"),
    }
    monkeypatch.setattr(httpx.Client, "get", lambda self, url, **kw: httpx.Response(
        200, text=pages.get(url, "<html></html>"), request=httpx.Request("GET", url)))
    frist = datetime.now() + timedelta(hours=30)
    out = tmp_path / "site"
    build.build_site(out, Settings(db_path=tmp_path / "x.sqlite3", fristen=Fristen(frist, frist)), watch_urls=[URL])

    detail = (out / "antrag" / "wasser-antrag-1--999.html").read_text(encoding="utf-8")
    assert 'href="../sharepic/wasser-antrag-1--999.html">Sharepic erstellen</a>' in detail
    page = (out / "sharepic" / "wasser-antrag-1--999.html").read_text(encoding="utf-8")
    assert 'src="../sharepic/wasser-antrag-1--999.svg"' in page and "sharepic.js" in page
    svg = (out / "sharepic" / "wasser-antrag-1--999.svg").read_text(encoding="utf-8")
    assert "39 Personen fehlen" in _text(svg) and "27 Frauen fehlen" in _text(svg)
    assert "Muster" not in svg and "Muster" not in page
