# 🌻 Grüne Antragshelper

**Quorum-Rechnung und Statistik für Anträge auf [antraege.gruene.de](https://antraege.gruene.de/) – ohne Login ins Grüne Netz.**

[![GitHub Pages](https://github.com/alexschnapper/grueneantragshelper/actions/workflows/pages.yml/badge.svg)](https://github.com/alexschnapper/grueneantragshelper/actions/workflows/pages.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Lizenz](https://img.shields.io/badge/lizenz-GPL--3.0-green)
![Status](https://img.shields.io/badge/status-MVP-orange)

👉 **Online ansehen:** <https://alexschnapper.github.io/grueneantragshelper/>

> [!IMPORTANT]
> **Inoffizielles Projekt.** Der Grüne Antragshelper ist **keine Anwendung von BÜNDNIS 90/DIE GRÜNEN**
> und steht in keiner Verbindung zur Partei oder zur Bundesgeschäftsstelle.
> Er ist ein **MVP für die 52. Bundesdelegiertenkonferenz (BDK)** und wird **ohne Garantie oder Gewähr
> auf Vollständigkeit oder Richtigkeit** bereitgestellt. Verbindlich sind ausschließlich die Angaben auf
> [antraege.gruene.de](https://antraege.gruene.de/).

![Dashboard](docs/dashboard.png)

---

## ✨ Was kann der Antragshelper?

| | |
|---|---|
| 🔎 **Suche** | Antragskürzel (z. B. `VR-01`, `W-04-070`) oder Link eingeben → direkt zur Auswertung |
| 🧮 **Quorum-Rechnung** | Gesamt- und Frauenquorum, aktueller Stand, wie viele Personen und Frauen noch fehlen, wie viele Plätze frei sind |
| 📋 **Listen** | Anträge und Änderungsanträge je Tagesordnungspunkt, filterbar, Änderungsanträge nach Hauptantrag gruppiert, zurückgezogene getrennt |
| 📊 **Dashboard** | Anträge je TOP, Gremien vs. Mitglieder, Verteilung des Frauenanteils, meiste Änderungsanträge, Veröffentlichungen pro Tag, „Puffer über dem Quorum“ |
| 🕒 **Aktivität** | Aktivitäts-Protokoll, nach Antrag gruppiert und aufklappbar |
| 👀 **Beobachten** | Anträge in der Sammelphase per Direktlink beobachten, inklusive Verlauf |
| 🔍 **Transparenz** | Jeder Abruf bei antraege.gruene.de mit Zeitpunkt, Zweck und Größe; Laufprotokoll mit Anlass; im Footer letzter Abruf und nächste geplante Prüfung |

**Datenschutz:** Es werden **keine Namen** von Antragsteller*innen oder Unterstützer*innen ausgelesen oder
gespeichert – nur Kürzel, Titel, Links und Zahlen. Damit klar ist, worum es geht (gerade bei mehreren
Änderungsanträgen zum selben Antrag), zeigt die App **kurze Auszüge** aus Antragstext und Begründung (je
höchstens 15 Wörter, bei Änderungsanträgen die Änderung selbst: „Von Zeile 31 bis 33: Streichen … · Einfügen …“).
Die Auszüge werden nicht gespeichert; den vollständigen Text gibt es auf antraege.gruene.de.

### Warum fehlen Anträge in der Sammelphase?

Antragsgrün blendet (Änderungs-)Anträge mit dem Status „Antragsteller*innen sammeln“ für alle ohne
Berechtigung aus: Sie stehen nicht in der Tagesordnung, nicht unter dem Hauptantrag, nicht in Suche,
Feeds oder Aktivitäts-Protokoll. Der Antragshelper kann sie daher **nicht selbst finden** – sie kommen
nur über ihren Direktlink in die Beobachtungsliste. Eine leere Liste heißt also nicht, dass kein Antrag
Unterstützung braucht. Hintergründe stehen in [KONZEPT.md](KONZEPT.md).

---

## 🚀 Lokal ausführen

Voraussetzung: Python 3.9 oder neuer.

```sh
git clone https://github.com/alexschnapper/grueneantragshelper.git
cd grueneantragshelper
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

| Befehl | Was passiert |
|---|---|
| `.venv/bin/python -m antragshelper server` | Web-App auf <http://localhost:8000> (mit Beobachten und Verlauf) |
| `.venv/bin/python -m antragshelper zeige VR-01` | Auswertung direkt im Terminal (Kürzel oder Link) |
| `.venv/bin/python -m antragshelper build --out _site` | Statische Seite erzeugen (wie auf GitHub Pages) |
| `.venv/bin/pytest` | Tests ausführen (ohne Browser) |
| `.venv/bin/pytest -m ui` | Browser-Tests mit Playwright (einmalig: `pip install -e '.[dev,ui]'` und `python -m playwright install chromium`) |

Optionen für `build`:

- `--details` – ruft zusätzlich die Einzelseiten der veröffentlichten Mitglieder-Anträge ab (gedrosselt,
  1 Seite pro Sekunde, ca. 1,5 Minuten) für die Quorum-Auswertung im Dashboard.
- `--beobachten beobachtet.txt` – Direktlinks zu Anträgen in der Sammelphase (eine URL pro Zeile).

Konfiguration über Umgebungsvariablen:

| Variable | Standard |
|---|---|
| `ANTRAGSHELPER_BASE_URL` | `https://antraege.gruene.de` |
| `ANTRAGSHELPER_CONSULTATION` | `52bdk` |
| `ANTRAGSHELPER_DB` | `data/antragshelper.sqlite3` |

Die Antragsfristen für die Hochrechnung stehen je Konferenz in `FRISTEN` in
[`antragshelper/config.py`](antragshelper/config.py) (für `52bdk`: Anträge 09.10.2026, Änderungsanträge
13.11.2026, jeweils 11:59 Uhr). Für eine andere Konferenz (Landes-, Bezirksparteitag,
Kreismitgliederversammlung) dort einen Eintrag mit ihrem Pfad ergänzen und `ANTRAGSHELPER_CONSULTATION`
setzen. Ohne Eintrag zeigt die App das Tempo, aber keine Prognose.

**Trend bis zur Frist**: Aus den gespeicherten Ständen rechnet der Antragshelper auf die Frist hoch:
Stand + Tempo × verbleibende Stunden. Als Tempo zählt vorsichtig das langsamere aus den letzten 24 und
72 Stunden (bei kürzerem Verlauf seit Beobachtungsbeginn, mindestens 1 Stunde) – Sammeln läuft in Schüben.
Die **Ampel** (drei Lichter plus Text) zeigt den schlechteren Stand von Frauen- und Gesamtquorum: Grün (auf Kurs)
ab 110 % des Quorums, Gelb (gefährdet) ab 90 %, sonst Rot (Scheitern droht) – Rot auch, wenn das Gesamtquorum
bei diesem Tempo nicht erreicht wird. Eine Ampel gibt es erst ab 12 Stunden Verlauf (kurz vor der Frist
entsprechend weniger); vorher steht dort, ab wann es eine Prognose gibt. Dazu zeigt sie, wie viele Personen pro
Stunde ab jetzt nötig sind, eine Handlungsempfehlung, eine aufklappbare Erklärung und einen kopierbaren
Mobilisierungs-Text. Auf der öffentlichen Seite kommen die Stände aus den stündlichen Prüfungen; auf dem eigenen
Rechner nur beim Öffnen einer Seite (je öfter, desto genauer).

**Frühwarnungen**: Bei gelber oder roter Ampel – und, solange es noch keine Prognose gibt, ab 72 Stunden vor
Fristende, wenn Frauen fehlen (sonst ab 48 Stunden) – erscheint ein Antrag oben in der Übersicht unter „Frühwarnungen“ („Achtung: Gesamtfortschritt
bei 74 %, Frauenquorum bei 60 % – noch 18 Frauen nötig …“). Die Auswertungsseite bietet zusätzlich einen
gezielten **Aufruf an Frauennetzwerke** zum Kopieren.

**Teilen**: Mobilisierungs-Text und Aufruf an Frauennetzwerke lassen sich vor dem Senden anpassen und direkt
weitergeben – geteilt wird der Text, wie er im Feld steht:

| Button | Was passiert |
|---|---|
| **Teilen …** | öffnet das Teilen-Menü des Geräts (Signal, Threema, WhatsApp, Telegram, Mail …) mit fertigem Text; erscheint nur, wo der Browser das kann (vor allem auf dem Handy) |
| **Threema** | öffnet Threema mit vorausgefülltem Text, die Empfänger*in wird in der App gewählt |
| **Signal** | kopiert den Text (Signal kann per Link keinen Text vorausfüllen) – im Chat einfügen |
| **Mail** | öffnet das Mailprogramm mit Betreff und Text |

**Sharepic**: „Sharepic erstellen“ zeigt unter dem Mobilisierungs-Text ein Bild (1080 × 1350) mit fehlenden
Personen und Frauen, Fortschritt, Stand, Antragsschluss und QR-Code zum Original. Es lässt sich als PNG oder SVG
herunterladen und – wo das Gerät es kann – mit **„Bild teilen …“** direkt an Signal, Threema oder WhatsApp schicken.

**Tests**: Bei jedem Pull Request und jedem Push auf `main` laufen über
[`.github/workflows/tests.yml`](.github/workflows/tests.yml) die Python-Tests und die Browser-Tests (Playwright,
Chromium). Die Browser-Tests bauen aus den Testdaten eine statische Seite und prüfen sie wie ein Mensch: keine
Fehler oder fehlenden Dateien, Icons, Prüfung beim Vorschlagen, Ampel, Teilen-Buttons, Sharepic als PNG und die
Darstellung auf dem Handy. Keiner der Tests ruft antraege.gruene.de ab.

## 🌐 GitHub Pages

Der Workflow [`.github/workflows/pages.yml`](.github/workflows/pages.yml) hält die Seite aktuell und
geht dabei sparsam mit antraege.gruene.de um:

| Wann | Was | Abrufe |
|---|---|---|
| stündlich | **Prüfung** (`antragshelper check`): Seite 1 des Aktivitäts-Protokolls und beobachtete Links, verglichen mit `static/stand.json` der veröffentlichten Seite | 1 + je 1 pro Link in `beobachtet.txt` |
| nur bei Änderung | **Neubau**: Startseite, Aktivitäts-Protokoll, Quorum-Zahlen **nur für neue** Mitglieder-Anträge (ältere gelten 7 Tage) | ca. 6 + neue Anträge |
| nachts, auf Knopfdruck, bei Push **mit Code-Änderungen** | Sicherheits-Build (z. B. für zurückgezogene Anträge, die nicht im Protokoll stehen) | wie Neubau |

Reine Doku-Änderungen (README, `docs/`, Konzept, Tests, Workflow) lösen beim Push **keinen** Abruf aus –
nur Änderungen an `antragshelper/`, `pyproject.toml` oder `beobachtet.txt`.

Warum nicht die Feeds? `feedall` & Co. sind nach Anlegedatum sortiert und enthalten nur 20 Einträge –
spät veröffentlichte Änderungsanträge tauchen dort nicht auf. Das Aktivitäts-Protokoll ist kleiner
(ca. 16 statt 55 KB) und nach Ereignis sortiert.

Für Trend und Frühwarnungen speichert `stand.json` den Verlauf der beobachteten Anträge (nur Zahlen und
Status, nur bei Änderungen, nur Links aus `beobachtet.txt`). Die stündliche Prüfung rechnet daraus die Ampel
mit und baut auch dann neu, wenn sie umspringt (etwa weil das Tempo mit der Zeit nicht mehr reicht) – ohne
zusätzliche Abrufe. Frühwarnungen gibt es als **Atom-Feed** unter `warnungen.xml`
(<https://alexschnapper.github.io/grueneantragshelper/warnungen.xml>): abonnierbar in jedem Feed-Reader, ohne
Anmeldung und ohne Daten über Abonnent*innen. Eine Warnung erscheint dort als neuer Eintrag, sobald ein Antrag
eine neue Warnstufe erreicht.

### Benachrichtigungen an Messenger (optional)

Neue Frühwarnungen kann der Build zusätzlich an Messenger schicken – einmal pro neuer Warnstufe, nicht
stündlich. Die Ziele stehen im GitHub-Secret **`ANTRAGSHELPER_WEBHOOKS`** (Settings → Secrets and variables →
Actions), nie im Repo, denn Webhook-URLs sind Zugangsdaten. Eine Zeile pro Ziel:

```text
json https://chatbegruenung.de/hooks/<id>/<token>
ntfy https://ntfy.sh/<geheimes-thema>
get <URL aus der CallMeBot-Anleitung für WhatsApp bzw. Signal, mit phone=…&apikey=…, ohne text=>
get https://api.telegram.org/bot<token>/sendMessage?chat_id=<chat-id>
signal-cli https://<dein-server>/v2/send?number=%2B49…&recipients=group.<id>
discord https://discord.com/api/webhooks/<id>/<token>
```

| Art | Wofür |
|---|---|
| `json` | Incoming Webhook von Chatbegrünung/Rocket.Chat, Mattermost oder Slack (`{"text": …}`) |
| `ntfy` | Push-Nachricht aufs Handy über die ntfy-App; das Thema ist das Geheimnis |
| `get` | Hängt `text=…` an: CallMeBot (WhatsApp oder Signal **an die eigene Nummer**), Telegram-Bot |
| `signal-cli` | [signal-cli-rest-api](https://github.com/bbernhard/signal-cli-rest-api) auf eigenem Server – auch an **Signal-Gruppen** |
| `discord` | Discord-Webhook (`{"content": …}`) |

WhatsApp und Signal haben keine offiziellen Webhooks für Gruppen: In eine Signal-Gruppe kommt man nur über
einen eigenen signal-cli-Server mit eigener Nummer, in WhatsApp-Gruppen gar nicht (dann z. B. ntfy oder
CallMeBot an die eigene Nummer und von Hand weiterleiten). Die Nachricht enthält nur, was auch auf der
Pages-Seite steht (Titel, Zahlen, Warnung, Link) und geht an den jeweiligen Dienst. Fehlerhafte Zeilen oder
nicht erreichbare Ziele brechen den Build nicht ab; das Laufprotokoll in `stand.json` zählt gesendete und
fehlgeschlagene Meldungen (ohne URLs). Ohne früheren Stand (`--vorher`) wird nichts gesendet, damit nach einem
verlorenen Stand nicht alle Warnungen erneut kommen.

Einmalig einrichten: **Settings → Pages → Build and deployment → Source: „GitHub Actions“**.

Anträge in der Sammelphase stehen in [`beobachtet.txt`](beobachtet.txt). Auf der Übersicht der Seite kann sie
jede*r **vorschlagen**: Der Link wird im Browser streng geprüft (nur `https://antraege.gruene.de/52bdk/<antrag>[/<id>]`,
sonst „Nur Links in Zusammenhang mit der 52BDK“ bzw. „Nicht gültig“) und geht dann

- **per GitHub** (Konto nötig) als vorausgefülltes Issue an den Workflow
  [`antrag-vorschlagen.yml`](.github/workflows/antrag-vorschlagen.yml), der den Link noch einmal prüft und per
  Pull Request einträgt – gemergt wird von Hand. Dafür einmalig **Settings → Actions → General → „Allow GitHub
  Actions to create and approve pull requests“** einschalten.
- **ohne Konto per Threema, Signal oder Mail** als Nachricht an die in `antragshelper/config.py` eingetragenen
  Kontakte (`vorschlag_threema`, `vorschlag_signal` als Benutzernamen-Link, `vorschlag_mail`; leer = Button
  ausgeblendet). Diese Links werden von Hand eingetragen.

Die Icons der Buttons stammen aus [Simple Icons](https://simpleicons.org) (CC0, siehe
`antragshelper/static/icons/LICENSE.md`).

## 🤝 Rücksicht auf antraege.gruene.de

Der Antragshelper ruft nur öffentlich verlinkte Seiten ab, speichert sie zwischen und drosselt
Einzelabrufe (1 Seite pro Sekunde). IDs werden **nicht** durchprobiert. Die GitHub-Pages-Version
prüft stündlich mit einem einzigen kleinen Abruf und baut nur bei Änderungen neu. Welche Seiten
wann und warum abgerufen wurden, steht auf der Seite
[Transparenz](https://alexschnapper.github.io/grueneantragshelper/transparenz.html).

## 📣 Teilen

Fertige Sharepics (KI-generiert, als inoffiziell gekennzeichnet) liegen in [`docs/sharepic/`](docs/sharepic/):
[Hochformat 1080 × 1350](docs/sharepic/sharepic-1080x1350.png) für Instagram/Facebook und
[Querformat 1200 × 675](docs/sharepic/sharepic-1200x675.png) für Mastodon, Bluesky, LinkedIn und X.

<img src="docs/sharepic/sharepic-1200x675.png" alt="Sharepic: Wie viele Unterstützer*innen fehlen noch?" width="600">

## 💚 Danke

Ein großes Dankeschön an die Entwickler*innen von **[Antragsgrün](https://github.com/CatoTH/antragsgruen)**,
der Open-Source-Software hinter antraege.gruene.de. Ohne ihre Arbeit – und den offenen Quellcode, aus dem
sich Seitenaufbau und Texte ablesen ließen – gäbe es dieses Projekt nicht.

## 📄 Lizenz

[GPL-3.0](LICENSE). Beiträge, Hinweise und Issues sind willkommen.
