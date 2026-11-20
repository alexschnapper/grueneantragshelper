# Fristen, Zeiten und Schwellen

Welche Zeitangaben der Antragshelper verwendet, was sie bedeuten und unter welchen Bedingungen sie gelten.
Alle Uhrzeiten sind **deutsche Ortszeit** (der Workflow setzt `TZ=Europe/Berlin`); gespeicherte Stände und Fristen
haben keine Zeitzone.

## 1. Antragsfristen je Konferenz

Hinterlegt in [`antragshelper/fristen.json`](../antragshelper/fristen.json), Schlüssel ist der Pfad der Konferenz
(`ANTRAGSHELPER_CONSULTATION`, Standard `52bdk`). Die Fristen stehen auf der Startseite von antraege.gruene.de nur als
Freitext und werden deshalb nicht gelesen, sondern von Hand gepflegt.

| Konferenz | Anträge | Änderungsanträge | Bemerkung |
| --- | --- | --- | --- |
| `52bdk` (52. BDK) | 09.10.2026, 11:59 Uhr | 13.11.2026, 11:59 Uhr | Dringlichkeitsanträge (20.11., 03.12.) sind nicht abgebildet |

Wie die Frist verwendet wird:

- **Welche Frist gilt?** Für Änderungsanträge die Änderungsantrags-Frist, für alles andere die Antragsfrist.
  Fehlt die Änderungsantrags-Frist, gilt auch für sie die Antragsfrist.
- **Ohne Eintrag** für die Konferenz zeigt die App das Sammeltempo, aber **keine Prognose, keine Ampel und keine Warnung**.
- Die Frist ist der Bezugspunkt der Hochrechnung („wie viele Personen fehlen zum Fristende“), der Mobilisierungs-Texte
  und des Sharepics („Antragsschluss …“).
- Ist die Frist abgelaufen und das Quorum nicht erreicht, steht die Ampel auf Rot.
- **Neue Konferenz:** Eintrag in `fristen.json` ergänzen (Format `JJJJ-MM-TTTHH:MM`) und diese Tabelle anpassen.
  `tests/test_fristen_doku.py` meldet, wenn Datei und Tabelle auseinanderlaufen.

## 2. Tempo und Prognose

Aus den gespeicherten Ständen rechnet [`trend.py`](../antragshelper/trend.py) das Sammeltempo und hochgerechnet den Stand zur Frist.

| Zeit | Bedeutung | Bedingung |
| --- | --- | --- |
| 24 h | kurzes rollierendes Fenster für das Tempo | bei kürzerem Verlauf zählt der ganze Verlauf |
| 72 h | langes rollierendes Fenster für das Tempo | wie oben; gerechnet wird mit dem **langsameren** der beiden Tempi, weil Sammeln in Schüben läuft |
| 1 h | Mindestbeobachtung | kürzer ergibt kein Tempo |
| 12 h | Ampel erst ab so viel Verlauf | oder so viel, wie bis zur Frist noch bleibt; vorher ist die Prognose „vorläufig“ und die Ampel erscheint erst später („Prognose ab ca. …“) |

Stände werden nur gespeichert, wenn sich die Zahlen ändern, und über Lücken fortgeschrieben.

## 3. Ampel

Verhältnis der **Prognose zum Quorum**, für Gesamt- und Frauenquorum; angezeigt wird die schlechtere Stufe.

| Stufe | Bedingung |
| --- | --- |
| Grün | Prognose mindestens 110 % des Quorums, oder Quorum erreicht |
| Gelb | Prognose zwischen 90 % und 110 % |
| Rot | Prognose unter 90 %, Gesamtquorum reicht nicht oder Frist abgelaufen |

## 4. Warnungen (Feed `warnungen.xml` und Benachrichtigungen)

| Stufe | Wann |
| --- | --- |
| Rot, Gelb | sobald die Ampel so steht (nur mit belastbarer Prognose) |
| „Frist läuft ab“ | solange die Ampel noch nicht belastbar ist: **72 Stunden** vor Fristende, wenn Frauen fehlen (Frauennetzwerke brauchen Zeit zum Weiterleiten), sonst **48 Stunden**; nur solange noch Personen fehlen und die Ampel nicht Grün ist |

Benachrichtigt wird, wenn sich die Warnstufe gegenüber dem letzten Stand ändert.

## 5. Abrufe und Aktualisierung (Pages-Seite)

Die Zeiten spiegeln [`.github/workflows/pages.yml`](../.github/workflows/pages.yml) und
[`zeitplan.py`](../antragshelper/zeitplan.py).

| Zeit | Bedeutung |
| --- | --- |
| stündlich, Minute 23 | Prüfung: Aktivitäts-Protokoll und beobachtete Links; Neubau **nur bei Änderung** (Zahlen, Ampel oder Warnstufe) |
| täglich 02:41 UTC | nächtlicher Sicherheits-Build, auch ohne Änderung |
| bei Push | nur bei Änderungen an Code, `pyproject.toml` oder `beobachtet.txt`; reine Doku-Pushes lösen **keinen** Abruf aus |

## 6. Server-Modus (lokal)

| Zeit | Bedeutung |
| --- | --- |
| 5 Min. | Zwischenspeicher für Startseite und Aktivitäts-Protokoll (`ttl_index`) |
| 2 Min. | Zwischenspeicher für Detailseiten (`ttl_detail`) |
| 1 Sek. | Pause zwischen zwei Abrufen der Dashboard-Auswertung |
| 3 Std. | frühestens alle 3 Stunden darf die Auswertung neu angestoßen werden |
| 7 Tage | beim statischen Build mit `--details` werden Statistiken, die jünger sind, wiederverwendet |

Alle Abrufe, auch die nach diesen Zeiten, stehen mit Zeitpunkt und Zweck auf der Seite „Transparenz“.
