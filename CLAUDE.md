# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Local web app (German UI) that scrapes public pages of antraege.gruene.de (an [Antragsgrün](https://github.com/CatoTH/antragsgruen) instance) and shows quorum calculations and statistics for motions (Anträge) and amendments (Änderungsanträge). `KONZEPT.md` holds the product concept and the analysis of the data sources.

## Commands

```sh
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'   # setup (Python >= 3.9)
.venv/bin/pytest                                             # all tests
.venv/bin/pytest tests/test_parsers.py::test_index_counts_and_lookup   # single test
.venv/bin/python -m antragshelper server                     # web UI on localhost:8000
.venv/bin/python -m antragshelper zeige VR-01                # CLI evaluation (prefix or URL)
.venv/bin/python -m antragshelper build --out _site [--details] [--beobachten beobachtet.txt] [--vorher stand.json]   # static site
.venv/bin/python -m antragshelper check --vorher <URL|stand.json>   # prints changed=true|false
```

Env vars: `ANTRAGSHELPER_BASE_URL`, `ANTRAGSHELPER_CONSULTATION` (default `52bdk`), `ANTRAGSHELPER_DB` (default `data/antragshelper.sqlite3`, gitignored). Deadlines for the trend live in `FRISTEN` in `config.py`, keyed by consultation path (they are free text on the start page, so not parsed); add an entry per new conference.

## Architecture

Flow: `client.py` (httpx + in-memory TTL cache, refuses foreign hosts) → `parsers.py` (BeautifulSoup) → `models.py` dataclasses → `service.py` (`Antragshelper`, shared by `web.py` FastAPI/Jinja2 and the CLI in `__main__.py`) → `store.py` (SQLite: watchlist + snapshots of quorum numbers, written only when values change).

`trend.py` holds the pure quorum projection (velocity over a rolling 24 h window from `snapshots`, carried forward because snapshots are only written on change; traffic light at 110 % / 90 % of the quorum; messenger snippet). `Antragshelper.hochrechnung` feeds it. For the static site, `stand.json` carries `verlauf` (snapshot rows of watched links) and `warnungen` (stage + since, keeps Atom entry IDs stable); `stand.import_history` must run before `fingerprint`/`watchlist` in both `check` and `build`. The fingerprint includes ampel + warnstufe, so the hourly check also rebuilds when the traffic light flips without new numbers (no extra fetches). `build.py` writes the Atom feed `warnungen.xml` (absolute links via `Settings.site_url`). The workflow sets `TZ=Europe/Berlin` because snapshots and deadlines are naive local time.

`dashboard.py` computes chart data (pure, no fetching); `charts.py` renders SVG server-side (scatter, progress lines), bar/column charts are HTML/CSS macros in `templates/dashboard.html`. Series colors are the validated blue/orange pair as CSS vars (`--s1`/`--s2`) in `static/style.css`. The dashboard's "Stufe B" crawl (`Antragshelper.start_stats_refresh`) runs in a background thread, only on button press, rate-limited (`STATS_DELAY_SECONDS`, `STATS_MIN_INTERVAL`), and stores only counts in `published_stats`.

Server and static export share templates and context builders (`views.py`). Templates must build every link via `href(name, **params)` (`links.py`): in server mode it returns `/auswertung?url=…`, in static mode relative file paths (`antrag/<slug>.html`, `liste/<art>_<top>_<stand>.html`). Templates branch on `static` for features that need a server (watch button, refresh, filters → `static/static.js`). `build.py` renders everything into `_site/` from one fetch of the start page + activity log; `.github/workflows/pages.yml` runs `antragshelper check` hourly (fingerprint of activity log page 0 + watched links, compared against `static/stand.json` of the deployed site; `stand.py`) and only rebuilds on change, plus a nightly forced build. `--details` is incremental via `--vorher` (stats younger than `STATS_MAX_AGE` are reused). Feeds are deliberately not used as trigger: sorted by creation date, they miss late-published items. Every page carries the "inoffizielles Projekt" disclaimer (asserted in `tests/test_build.py`).

Transparency: `AntragsgruenClient.get(url, ttl, purpose)` logs every real network fetch (not cache hits) as `FetchRecord` with a human-readable purpose — always pass a purpose for new fetches. Builds append a run record (Anlass, fetches per purpose) to `laeufe` in `stand.json`; the workflow passes `--anlass`/`--pruef-abrufe` from the check job. `zeitplan.py` mirrors the workflow crons (asserted by `tests/test_zeitplan.py`); the footer and `/transparenz` show last run and next planned check. Tests fake `httpx.Client.get` (not the client) so cache and logging run for real.

Key facts about the data source:
- The Antragsgrün REST API is disabled on this instance (`403 Public API disabled`), so everything is HTML scraping. Selectors come from Antragsgrün templates: `ul.motionListBelowAgenda` (agenda on the consultation start page = the search index), `table.motionDataTable`, `tr.statusRow`, `.supportCollectionHint`, `.womenQuota`.
- Quorum text formats are from Antragsgrün `messages/de/motion.php` (`support_collection_hint_female`, `support_collection_hint`, `support_collection_reached_hint`); the BDK uses a custom wording ("Mitantragsteller*innen"), so regexes in `parsers.py` must stay wording-tolerant. The "reached" text contains no current counts.
- Motions/amendments still collecting supporters are not listed anywhere public (the Antragsgrün `/collecting` page is disabled, they have no prefix yet), so they only enter the app via a direct link on the watchlist. Do not add ID enumeration.
- Statute amendments appear as top-level `li.motion.amendmentRowNNN` on the start page; normal amendments are nested in `ul.amendments`.
- The consultation-wide quorum (e.g. 91 / 46) is parsed from the start page text (`#stdTextHolder`). Submitter type: "dort beschlossen" = Gremium, a shown women share = Mitglieder.
- Activity log dates are relative ("Heute, 12:20", "Gestern, …") or `dd.mm.yyyy`; see `ActivityEntry.day`.
- Feeds only contain the latest 20 items — never use them for counting.

## Constraints

- **Pushes that only change docs must not trigger any fetch on antraege.gruene.de.** The workflow's `push` trigger uses a `paths` allowlist (`antragshelper/**`, `pyproject.toml`, `beobachtet.txt`); README, `docs/`, KONZEPT.md, CLAUDE.md, tests and the workflow itself are excluded. Keep it an allowlist (not `paths-ignore`); `tests/test_zeitplan.py` asserts this.
- Never probe/enumerate motion IDs; only fetch publicly linked pages.
- Never extract or persist person names (initiators, supporters, activity log actors, feed authors) and never pull motion text; tests assert this (`"Muster" not in repr(...)`).
- Test fixtures in `tests/fixtures/` are hand-written, anonymized imitations of the real markup. Do not commit real downloaded pages (they contain names).
- License GPL-3.0; dependencies must be compatible.
