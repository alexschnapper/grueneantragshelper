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

**Datenschutz:** Es werden **keine Namen** von Antragsteller*innen oder Unterstützer*innen und **kein
Antragstext** ausgelesen oder gespeichert – nur Kürzel, Titel, Links und Zahlen.

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
| `.venv/bin/pytest` | Tests ausführen |

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

**Trend bis zur Frist** (lokale App und GitHub-Pages-Seite): Aus den gespeicherten Ständen berechnet die App das
Sammeltempo (letzte 24 Stunden, bei kürzerem Verlauf seit Beobachtungsbeginn, mindestens 1 Stunde) und
rechnet auf die Frist hoch: Stand + Tempo × verbleibende Stunden. Die Ampel gilt für das Frauenquorum
(ohne Frauenquorum für das Gesamtquorum): Grün (auf Kurs) ab 110 % des Quorums, Gelb (gefährdet) ab 90 %,
sonst Rot (Scheitern droht) – Rot auch, wenn das Gesamtquorum bei diesem Tempo nicht erreicht wird. Eine
Ampel gibt es erst ab 12 Stunden Verlauf (kurz vor der Frist entsprechend weniger). Dazu zeigt sie, wie viele
Personen pro Stunde ab jetzt nötig sind, eine Handlungsempfehlung und einen kopierbaren Mobilisierungs-Text.
In der lokalen App werden Stände nur beim Aufruf gespeichert – je öfter beobachtete Anträge geöffnet
werden, desto genauer. Auf der GitHub-Pages-Seite kommen sie aus den stündlichen Prüfungen.

**Frühwarnungen**: Bei gelber oder roter Ampel – und, solange die Prognose noch vorläufig ist, ab 48 Stunden
vor Fristende – erscheint ein Antrag oben in der Übersicht unter „Frühwarnungen“ („Achtung: Gesamtfortschritt
bei 74 %, Frauenquorum bei 60 % – noch 18 Frauen nötig …“). Die Auswertungsseite bietet zusätzlich einen
gezielten **Aufruf an Frauennetzwerke** zum Kopieren.

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

Einmalig einrichten: **Settings → Pages → Build and deployment → Source: „GitHub Actions“**.

Anträge in der Sammelphase können in [`beobachtet.txt`](beobachtet.txt) eingetragen werden. Die Datei ist
öffentlich – bitte nur Links eintragen, die die Antragsteller*innen selbst öffentlich teilen.

Die statische Version kann nichts speichern: Beobachten per Knopf, Verlauf und Auswertung beliebiger
Links gibt es nur in der lokal ausgeführten App.

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
