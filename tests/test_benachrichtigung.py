import json
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

from antragshelper import benachrichtigung, build
from antragshelper.benachrichtigung import Webhook
from antragshelper.config import Fristen, Settings

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://antraege.gruene.de"
COLLECTING = f"{BASE}/52bdk/wasser-antrag-1/999"


def test_parse():
    hooks = benachrichtigung.parse("""
        # Chatbegrünung
        json https://chat.example.org/hooks/abc
        ntfy https://ntfy.sh/geheimes-thema
    """)
    assert hooks == [Webhook("json", "https://chat.example.org/hooks/abc"), Webhook("ntfy", "https://ntfy.sh/geheimes-thema")]
    assert benachrichtigung.parse("") == []


@pytest.mark.parametrize("zeile", ["telegram https://x.example/geheim", "json http://x.example/geheim", "json"])
def test_parse_fehler_ohne_url_in_meldung(zeile):
    with pytest.raises(ValueError) as e:
        benachrichtigung.parse(zeile)
    assert "geheim" not in str(e.value) and "Zeile 1" in str(e.value)


def test_anfragen_je_art():
    r = benachrichtigung.request(Webhook("json", "https://chat.example.org/hooks/abc"), "Titel", "Text")
    assert r.method == "POST" and json.loads(r.content) == {"text": "Titel\nText"}

    r = benachrichtigung.request(Webhook("discord", "https://discord.example/api/webhooks/1"), "Titel", "Text")
    assert json.loads(r.content) == {"content": "Titel\nText"}

    r = benachrichtigung.request(Webhook("ntfy", "https://ntfy.sh/thema"), "Frühwarnung", "Text")
    assert r.method == "POST" and r.url.params["title"] == "Frühwarnung" and r.content == b"Text"

    r = benachrichtigung.request(Webhook("get", "https://api.callmebot.com/whatsapp.php?phone=49170&apikey=1"), "Ä", "b")
    assert r.method == "GET"
    assert dict(r.url.params) == {"phone": "49170", "apikey": "1", "text": "Ä\nb"}

    r = benachrichtigung.request(
        Webhook("signal-cli", "https://signal.example.org/v2/send?number=%2B49170&recipients=group.abc,%2B49171"), "T", "x")
    assert str(r.url) == "https://signal.example.org/v2/send"
    assert json.loads(r.content) == {"message": "T\nx", "number": "+49170", "recipients": ["group.abc", "+49171"]}


def test_senden_zaehlt_und_bricht_nicht_ab():
    def handler(request):
        return httpx.Response(500 if "kaputt" in str(request.url) else 200)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    hooks = [Webhook("json", "https://ok.example/h"), Webhook("json", "https://kaputt.example/h")]
    assert benachrichtigung.senden(hooks, [("T", "a"), ("T", "b")], "ua", client) == (2, 2)
    assert benachrichtigung.senden([], [("T", "a")], "ua", client) == (0, 0)


@pytest.fixture
def site(monkeypatch):
    pages = {
        f"{BASE}/52bdk": (FIXTURES / "home.html").read_text(encoding="utf-8"),
        f"{BASE}/52bdk/activitylog?page=0": (FIXTURES / "activitylog.html").read_text(encoding="utf-8"),
        COLLECTING: (FIXTURES / "amendment_collecting.html").read_text(encoding="utf-8"),
    }
    sent = []

    def fake_get(self, url, **kwargs):
        return httpx.Response(200, text=pages.get(url, "<html></html>"), request=httpx.Request("GET", url))

    def fake_send(self, request, **kwargs):
        sent.append(request)
        return httpx.Response(200, request=request)

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    monkeypatch.setattr(httpx.Client, "send", fake_send)
    return sent


def _settings(tmp_path, stunden):
    frist = datetime.now().replace(microsecond=0) + timedelta(hours=stunden)
    return Settings(db_path=tmp_path / "x.sqlite3", fristen=Fristen(frist, frist))


def _stand(out):
    return json.loads((out / "static" / "stand.json").read_text(encoding="utf-8"))


def test_build_meldet_nur_neue_warnungen(tmp_path, site):
    hooks = [Webhook("json", "https://chat.example.org/hooks/abc")]
    # Ohne früheren Stand keine Meldung (sonst wäre nach verlorenem Stand jede Warnung „neu“)
    build.build_site(tmp_path / "a", _settings(tmp_path, 30), watch_urls=[COLLECTING], webhooks=hooks)
    assert site == []

    # Vorher noch keine Warnung (Frist weit weg), jetzt 30 Stunden vor Fristende -> eine Meldung
    build.build_site(tmp_path / "b", _settings(tmp_path, 200), watch_urls=[COLLECTING])
    build.build_site(tmp_path / "c", _settings(tmp_path, 30), watch_urls=[COLLECTING], webhooks=hooks,
                     previous=_stand(tmp_path / "b"))
    [request] = site
    text = json.loads(request.content)["text"]
    assert text.startswith("Frühwarnung – Frist läuft ab: Änderungsantrag zu VR-01")
    assert "noch 27 Frauen nötig" in text and "/antrag/wasser-antrag-1--999.html" in text
    assert "Muster" not in text
    assert _stand(tmp_path / "c")["laeufe"][-1]["benachrichtigungen"] == {"gesendet": 1, "fehlgeschlagen": 0}

    # Gleiche Warnstufe im nächsten Lauf: keine erneute Meldung
    build.build_site(tmp_path / "d", _settings(tmp_path, 30), watch_urls=[COLLECTING], webhooks=hooks,
                     previous=_stand(tmp_path / "c"))
    assert len(site) == 1
