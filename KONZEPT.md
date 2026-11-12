# Konzept: Grüne Antragshelper

Lokale Web-App, die öffentlich zugängliche Daten von [antraege.gruene.de](https://antraege.gruene.de/)
(Antragsgrün) ausliest und **Statistik und Quorum-Rechnung** für Anträge und Änderungsanträge
einer Konferenz (z. B. der 52. BDK, Pfad `52bdk`) anzeigt.

## Ziele

- Antragskürzel (z. B. `VR-01`, `W-04-070`) oder Link in ein Suchfeld eingeben → direkt zur Auswertung.
- Je (Änderungs-)Antrag: Status, Gesamtquorum, Frauenquorum, aktueller Stand,
  **fehlende Personen gesamt / fehlende Frauen**, Frauenanteil, Link zur Originalquelle.
- Übersicht: wie viele Anträge und Änderungsanträge es gibt (gesamt, je Tagesordnungspunkt,
  zurückgezogen).
- Liste der Anträge, die **noch Unterstützung brauchen**, sortiert nach dem, was fehlt.
- Verlauf: wie sich der Stand eines beobachteten Antrags über die Zeit ändert.

## Abgrenzung

- **Kein Login** ins Grüne Netz. Nur, was anonym sichtbar ist.
- **Nur kurze Auszüge aus dem Antragstext.** Anträge sind auf antraege.gruene.de öffentlich lesbar. Damit
  erkennbar ist, worum es geht (sonst wirken mehrere Änderungsanträge zum selben Antrag wie Doppelungen),
  zeigt die App je höchstens 15 Wörter aus Antragstext und Begründung – bei Änderungsanträgen die Änderung
  selbst (Zeilen, Streichen/Einfügen) – und verlinkt für den Volltext auf das Original. Auszüge werden nicht
  gespeichert (seit 12.11.2026; die bis dahin aufgenommenen Teams sind informiert).
- **Keine Namen speichern.** Weder Antragsteller*innen noch Unterstützer*innen werden
  gespeichert. Gespeichert werden nur Zahlen (Quorum, Stand) und öffentliche URLs/Kürzel/Titel.
- Zunächst nur lokal ausführbar (eine Person, ein Rechner).

## Datenquellen (Stand: Analyse 09.11.2026, Antragsgrün 4.18.1)

Die öffentliche REST-API von Antragsgrün (`/rest/...`) ist auf antraege.gruene.de deaktiviert
(`403 Public API disabled`). Daher wird HTML gelesen. `robots.txt` verbietet nichts; trotzdem
wird schonend abgerufen (Cache, eigener User-Agent, keine Massenabfragen).

| Quelle | URL | Inhalt | Nutzung |
|---|---|---|---|
| Startseite der Konferenz | `/52bdk` | Tagesordnung mit allen **veröffentlichten** Anträgen und deren Änderungsanträgen (Kürzel, Titel, Link, Frauenanteil, zurückgezogen) | Index für die Suche, Zählung |
| Antrags-/ÄA-Seite | `/52bdk/<slug>` bzw. `/52bdk/<slug>/<id>` | Rahmendaten-Tabelle (`.motionDataTable`), Status (`tr.statusRow`), Quorum-Hinweis (`.supportCollectionHint`), Frauenanteil (`.womenQuota`) | Quorum-Auswertung |
| Feeds | `/52bdk/feedmotions`, `/feedamendments`, `/feedall` | RSS, **nur die letzten 20 Einträge** | Neue Einträge erkennen (nicht zum Zählen) |
| Aktivitäts-Protokoll | `/52bdk/activitylog?page=N` | Ereignisse mit Zeit, Antrag, Aktion (bisher nur „… veröffentlicht“) | Änderungen anzeigen |

### Quorum-Hinweis (aus dem Antragsgrün-Quellcode)

`views/motion/view.php` / `views/amendment/view.php` zeigen in der Sammelphase einen der Texte
aus `messages/de/motion.php` (Wortlaut auf der BDK leicht angepasst: „Mitantragsteller*innen“):

- mit Frauenquorum: „Nötig sind **mindestens 91 Mitantragsteller*innen, davon 46 Frauen
  (aktueller Stand: 52 / 19)**“
- ohne Frauenquorum: „Nötig sind **mindestens %MIN% … (aktueller Stand: %CURR%)**“
- erreicht: „**Die Mindestzahl an Unterstützer*innen (%MIN%) wurde erreicht** …“
  (ohne aktuellen Stand)

`%CURR%` zählt die Unterstützer*innen **ohne** die Antragsteller*in selbst.

### Wichtige Lücke: Anträge in der Sammelphase

Anträge mit Status „Antragsteller*innen sammeln“ werden **nirgends öffentlich gelistet**: Sie
stehen nicht auf der Startseite, nicht unter dem Hauptantrag, nicht in Feeds oder im
Aktivitäts-Protokoll. Antragsgrün hätte dafür eine Seite `/<konferenz>/collecting`, die auf der
BDK aber abgeschaltet ist (404). Sie haben auch noch kein eigenes Kürzel
(„Änderungsantrag zu VR-01“).

Grund im Quellcode: `IMotionStatusEngine` definiert `STATUS_COLLECTING_SUPPORTERS` als
`userInvisible: true`. Solche (Änderungs-)Anträge fehlen deshalb in allen öffentlichen Listen,
in der Suche, in den Feeds und in den PDF-Sammlungen. Sichtbar wären sie nur auf der Seite
`/collecting`, wenn die Admins die Einstellung `collectingPage` aktivieren. Das wäre die
sauberste Lösung und ließe sich bei der Bundesgeschäftsstelle anfragen
(antragsgruen@gruene.de).

→ Die App führt eine **Beobachtungsliste**: Man fügt den Direktlink ein (den die
Antragsteller*innen meist herumschicken), die App ruft den Stand regelmäßig ab und zeigt ihn in
der Liste „braucht noch Unterstützung“. IDs durchzuprobieren ist bewusst **nicht** vorgesehen.

## Rechnung

Gegeben: `min_gesamt`, `min_frauen`, `stand_gesamt`, `stand_frauen`.

- fehlend gesamt = `max(0, min_gesamt − stand_gesamt)`
- fehlende Frauen = `max(0, min_frauen − stand_frauen)`
- davon frei (beliebiges Geschlecht) = `max(0, fehlend gesamt − fehlende Frauen)`
- tatsächlich noch nötig = `max(fehlend gesamt, fehlende Frauen)`

Beispiel (ÄA zu VR-01): 91 / 46, Stand 52 / 19 → 39 fehlen, davon mindestens 27 Frauen,
höchstens 12 Plätze frei.

## Funktionen der App

1. **Suche** (`/suche?q=…`): Kürzel → Index der Startseite → Auswertungsseite. Ein Link auf
   antraege.gruene.de wird direkt ausgewertet.
2. **Auswertung** (`/auswertung?url=…`): Titel, Status, Quorum, fehlende Personen, Fortschritts-
   balken, Verlauf der gespeicherten Stände, Link zum Original, Button „beobachten“.
3. **Übersicht** (`/`): Anzahl Anträge/Änderungsanträge gesamt und je TOP, zurückgezogene,
   Beobachtungsliste mit „braucht noch Unterstützung“ (sortiert nach fehlenden Personen).
4. **Aktivität** (`/aktivitaet`): letzte Einträge des Aktivitäts-Protokolls (nur Zeit, Antrag,
   Aktion – ohne Namen der handelnden Person).
5. **Dashboard** (`/dashboard`):
   - Stufe A (ohne Zusatzabrufe): Anträge/ÄA je TOP, Gremien vs. Mitglieder, Verteilung des
     Frauenanteils, Anträge mit den meisten ÄA, Veröffentlichungen pro Tag, Verlauf beobachteter
     Anträge in der Sammelphase.
   - Stufe B (nur auf Knopfdruck, höchstens alle 3 Stunden, 1 Seite pro Sekunde): Einzelseiten
     der veröffentlichten Mitglieder-Anträge → Zahl der Mitantragsteller*innen. Streudiagramm
     Personen vs. Frauen mit Quorum-Linien und „Puffer über dem Quorum“. Veröffentlichte Anträge
     haben das Quorum per Definition erreicht – gezeigt wird, wie knapp. Frauenzahl = gerundeter
     Frauenanteil × (Mitantragsteller*innen + 1), also ±1 Person.
6. **CLI**: `python -m antragshelper zeige VR-01` für eine schnelle Auswertung im Terminal.

## Technik

- Python ≥ 3.9, `httpx` (Abruf), `beautifulsoup4` (HTML), `FastAPI` + `Jinja2` (Oberfläche),
  SQLite aus der Standardbibliothek (Beobachtungsliste, Verlauf der Zahlen).
- Cache im Speicher (Startseite 5 min, Einzelseiten 2 min), damit Neuladen keine Last erzeugt.
- Konferenz-Pfad und Basis-URL konfigurierbar (`ANTRAGSHELPER_BASE_URL`,
  `ANTRAGSHELPER_CONSULTATION`), damit z. B. eine spätere BDK oder LDK funktioniert.
- Tests mit eigenen, **anonymisierten** HTML-Ausschnitten (keine echten Namen im Repo).

## Aktualisierung auf GitHub Pages

Stündliche Prüfung mit einem Abruf (Seite 1 des Aktivitäts-Protokolls, plus beobachtete Links),
Vergleich mit `static/stand.json` der veröffentlichten Seite, Neubau nur bei Änderung, Quorum-Zahlen
inkrementell, nachts ein Sicherheits-Build. Die Feeds sind als Auslöser ungeeignet: Sie sind nach
Anlegedatum sortiert (nur 20 Einträge) und verpassen spät veröffentlichte Änderungsanträge; ETag oder
Last-Modified liefert der Server nicht (`no-store`).

## Ausbaustufen (später)

- Regelmäßiger Hintergrundabruf der Beobachtungsliste, Benachrichtigung bei Quorum erreicht.
- Neue Einträge aus Feeds/Aktivitäts-Protokoll seit dem letzten Besuch hervorheben.
- Fristen der Konferenz anzeigen (stehen als Freitext auf der Startseite).
- Diagramm: Verlauf des Stands über die Zeit.
- Hosting für mehrere Nutzer*innen (dann Rate-Limit und Rücksprache mit dem Bundesverband).
