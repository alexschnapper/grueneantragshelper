"""Browser-Tests (Playwright, Chromium) gegen die statische Seite aus den Testdaten: `pytest -m ui`."""
import struct
from urllib.parse import quote

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.ui

DETAIL_ROT = "antrag/wasser-antrag-1--999.html"
DETAIL_OHNE = "antrag/wasser-antrag-1--998.html"
SEITEN = ["index.html", "dashboard.html", "aktivitaet.html", "transparenz.html", "liste/alle_alle_alle.html",
          DETAIL_ROT, DETAIL_OHNE, "sharepic/wasser-antrag-1--999.html"]


def _fehler(seite):
    return [f for f in seite.fehler if "favicon.ico" not in f]


@pytest.mark.parametrize("pfad", SEITEN)
def test_keine_fehler_und_alles_geladen(seite, site, pfad):
    seite.goto(site + pfad)
    seite.wait_for_load_state("networkidle")
    assert _fehler(seite) == []


def test_icons_werden_wirklich_geladen(seite, site):
    seite.goto(site + "index.html")
    icons = seite.locator("#vorschlagen .icon")
    assert icons.count() == 4  # GitHub, Mail, Threema, Signal
    for i in range(icons.count()):
        icon = icons.nth(i)
        assert icon.bounding_box()["width"] > 0
        # Die Maske muss relativ zur Seite aufgelöst werden und erreichbar sein (früherer Fehler: CSS-Variable)
        status = icon.evaluate("""el => {
            const m = getComputedStyle(el).maskImage || getComputedStyle(el).webkitMaskImage;
            const url = m.slice(m.indexOf('"') + 1, m.lastIndexOf('"'));
            return fetch(url).then(r => r.status + ' ' + url);
        }""")
        assert status.startswith("200 ") and "/static/icons/" in status


@pytest.mark.parametrize("eingabe, meldung", [
    ("🌻", "Nicht gültig"),
    ("VR-01", "Nicht gültig"),
    ("https://antraege.gruene.de/52bdk/x'; DROP TABLE watchlist;--", "Nicht gültig"),
    ("https://antraege.gruene.de/52bdk/<script>alert(1)</script>", "Nicht gültig"),
    ("https://example.org/52bdk/antrag-1", "Nur Links in Zusammenhang mit der 52BDK"),
    ("https://antraege.gruene.de/53bdk/antrag-1/2", "Nur Links in Zusammenhang mit der 52BDK"),
])
def test_vorschlag_lehnt_ab(seite, site, eingabe, meldung):
    seite.goto(site + "index.html")
    seite.fill("#vorschlag-link", eingabe)
    seite.click("button[value=github]")
    assert seite.locator("#vorschlag-meldung").inner_text() == meldung
    assert seite.locator("#vorschlag-link").get_attribute("aria-invalid") == "true"
    assert len(seite.context.pages) == 1  # nichts geöffnet


def test_vorschlag_oeffnet_github_und_threema(seite, site):
    link = "https://antraege.gruene.de/52bdk/antrag-1/2"
    seite.goto(site + "index.html")
    seite.fill("#vorschlag-link", link)
    with seite.context.expect_page() as neu:
        seite.click("button[value=github]")
    assert neu.value.url.startswith("https://github.com/alexschnapper/grueneantragshelper/issues/new?template=")
    assert neu.value.url.endswith("&link=" + quote(link, safe=""))
    assert seite.locator("#vorschlag-meldung").is_hidden()

    with seite.context.expect_page() as neu:
        seite.click("button[value=threema]")
    assert neu.value.url.startswith("https://threema.id/UBK44SB7?text=")


def test_ampel_nur_mit_prognose(seite, site):
    seite.goto(site + DETAIL_ROT)
    assert seite.locator(".ampel.gross .licht.rot.an").is_visible()
    assert "Rot · Scheitern droht" in seite.locator(".ampel-box").inner_text()

    seite.goto(site + DETAIL_OHNE)
    assert seite.locator(".ampel-box .lichter").count() == 0
    assert "Prognose ab ca." in seite.locator(".ampel-box").inner_text()


def test_teilen_nimmt_den_aktuellen_text(seite, site):
    seite.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=site.rstrip("/"))
    seite.goto(site + DETAIL_ROT)
    text = "Selbst angepasster Text für die Ortsgruppe 🌻"
    seite.fill("#mobilisierung", text)
    gruppe = seite.locator(".teilen[data-quelle=mobilisierung]")

    gruppe.locator("[data-teilen=signal]").click()
    expect(seite.locator(".teilen[data-quelle=mobilisierung] + .teilen-hinweis")).to_contain_text("Text kopiert")
    assert seite.evaluate("navigator.clipboard.readText()") == text

    with seite.context.expect_page() as neu:
        gruppe.locator("[data-teilen=threema]").click()
    assert neu.value.url == "https://threema.id/compose?text=" + quote(text, safe="-_.!~*'()")


def test_sharepic_als_png(seite, site):
    seite.goto(site + DETAIL_ROT)
    seite.click("summary:has-text('Sharepic erstellen')")
    seite.wait_for_function("document.getElementById('sharepic').complete && document.getElementById('sharepic').naturalWidth > 0")
    with seite.expect_download() as download:
        seite.click("button[data-png=sharepic]")
    assert download.value.suggested_filename == "sharepic-wasser-antrag-1--999.png"
    daten = open(download.value.path(), "rb").read()
    assert daten[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", daten[16:24]) == (1080, 1350)


@pytest.mark.parametrize("pfad", ["index.html", DETAIL_ROT, "transparenz.html"])
def test_handy_ohne_waagerechtes_scrollen(seite, site, pfad):
    seite.set_viewport_size({"width": 390, "height": 844})
    seite.goto(site + pfad)
    breite = seite.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
    assert breite[0] <= breite[1], f"Seite ist {breite[0]} px breit bei {breite[1]} px Bildschirm"


def test_mastodon_mit_hashtags_und_eigener_instanz(seite, site):
    seite.goto(site + DETAIL_ROT)
    gruppe = seite.locator(".teilen[data-quelle=mobilisierung]")
    hinweis = seite.locator(".teilen[data-quelle=mobilisierung] + .teilen-hinweis")
    seite.fill("#mobilisierung", "Bitte mitzeichnen: https://antraege.gruene.de/52bdk/x/1 #BDK52")
    with seite.context.expect_page() as neu:
        gruppe.locator("[data-teilen=mastodon]").click()
    # #BDK52 steht schon da, #BDK (nur ein Teil davon) fehlt noch
    erwartet = "Bitte mitzeichnen: https://antraege.gruene.de/52bdk/x/1 #BDK52\n\n#BDK #52BDK #Grüne"
    assert neu.value.url == "https://gruene.social/share?text=" + quote(erwartet, safe="-_.!~*'()")

    gruppe.locator("[data-teilen=instanz]").click()
    feld = seite.locator(".instanz-form input")
    assert feld.input_value() == "gruene.social"
    for falsch in ["🌻", "javascript:alert(1)", "localhost", "zwei worte.social"]:
        feld.fill(falsch)
        seite.click(".instanz-form button")
        expect(hinweis).to_have_text("Nicht gültig – nur der Name der Instanz, z. B. gruene.social")
    feld.fill(" https://Mastodon.Social/@jemand ")
    feld.press("Enter")
    expect(hinweis).to_have_text("Mastodon teilt jetzt über mastodon.social.")

    seite.reload()  # die Wahl merkt sich der Browser
    with seite.context.expect_page() as neu:
        seite.locator(".teilen[data-quelle=mobilisierung] [data-teilen=mastodon]").click()
    assert neu.value.url.startswith("https://mastodon.social/share?text=")
