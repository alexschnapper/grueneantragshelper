"""CLI: `python -m antragshelper zeige VR-01`, `… server` oder `… build --out _site`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from .client import SourceError
from .config import settings


def _show(query: str) -> int:
    from .service import Antragshelper

    helper = Antragshelper(settings)
    try:
        url, _ = helper.resolve(query)
        if url is None:
            print(f"Kein veröffentlichter Antrag mit Kürzel „{query}“. Für Sammelphase den Direktlink angeben.")
            return 1
        d = helper.detail(url)
    except SourceError as e:
        print(e, file=sys.stderr)
        return 2
    print(d.title)
    print(f"  Status:        {d.status or '–'}")
    if d.women_share is not None:
        print(f"  Frauenanteil:  {d.women_share} %")
    q = d.quorum
    if q is None:
        print("  Quorum:        keine Sammelphase (eingereicht oder durch Gremium gestellt)")
    elif q.reached:
        print(f"  Quorum:        erreicht (mindestens {q.min_total})")
    else:
        women = f" / {q.current_women} von {q.min_women} Frauen" if q.min_women is not None else ""
        print(f"  Stand:         {q.current_total} von {q.min_total}{women}")
        print(f"  Fehlen:        {q.still_needed} Personen, davon mindestens {q.missing_women} Frauen "
              f"({q.open_any_gender} Plätze frei)")
    print(f"  Quelle:        {d.url}")
    return 0


def _check(previous_source: str, watch_file: Optional[Path]) -> int:
    """Gibt `changed`, `anlass` und `abrufe` aus (und schreibt sie nach $GITHUB_OUTPUT, falls gesetzt)."""
    import dataclasses
    import os
    import tempfile

    from . import stand
    from .build import read_watch_file
    from .service import Antragshelper

    previous = stand.load(previous_source)
    watch_urls = read_watch_file(watch_file) if watch_file else []
    with tempfile.TemporaryDirectory() as tmp:
        helper = Antragshelper(dataclasses.replace(settings, db_path=Path(tmp) / "check.sqlite3"))
        try:
            current = stand.fingerprint(helper, [u for u in watch_urls if helper.client.is_own_url(u)])
        except SourceError as e:
            print(e, file=sys.stderr)
            return 2
        requests = len(helper.client.log)
    before = (previous or {}).get("fingerprint") or {}
    if previous is None:
        reason = "kein früherer Stand"
    elif before.get("aktivitaet") != current["aktivitaet"]:
        reason = "neue Einträge im Aktivitäts-Protokoll"
    elif before.get("beobachtet") != current["beobachtet"]:
        reason = "Stand eines beobachteten Antrags geändert"
    else:
        reason = None
    outputs = {
        "changed": "true" if reason else "false",
        "anlass": f"Stündliche Prüfung: {reason}" if reason else "",
        "abrufe": str(requests),
    }
    print(f"changed={outputs['changed']} ({reason or 'unverändert'}, {requests} {'Abruf' if requests == 1 else 'Abrufe'})")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.writelines(f"{k}={v}\n" for k, v in outputs.items())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="antragshelper", description="Quorum-Auswertung für antraege.gruene.de")
    sub = parser.add_subparsers(dest="cmd", required=True)
    show = sub.add_parser("zeige", help="Auswertung für Kürzel (z. B. VR-01) oder Link ausgeben")
    show.add_argument("query")
    server = sub.add_parser("server", help="Web-Oberfläche starten")
    server.add_argument("--port", type=int, default=8000)
    build = sub.add_parser("build", help="Statische Seite (z. B. für GitHub Pages) erzeugen")
    build.add_argument("--out", type=Path, default=Path("_site"))
    build.add_argument("--details", action="store_true",
                       help="Einzelseiten der Mitglieder-Anträge abrufen (gedrosselt, ca. 1,5 Minuten)")
    build.add_argument("--beobachten", type=Path, metavar="DATEI",
                       help="Datei mit Direktlinks (eine URL pro Zeile) zu Anträgen in der Sammelphase")
    build.add_argument("--vorher", metavar="URL|DATEI",
                       help="stand.json des letzten Builds: nur neue Mitglieder-Anträge werden abgerufen")
    build.add_argument("--anlass", default="Lokaler Build", help="Grund des Laufs (für die Transparenzseite)")
    build.add_argument("--pruef-abrufe", type=int, default=0, metavar="N",
                       help="Abrufe der vorgeschalteten Prüfung, werden im Laufprotokoll mitgezählt")
    check = sub.add_parser("check", help="Prüfen, ob sich seit dem letzten Build etwas geändert hat (1 Abruf)")
    check.add_argument("--vorher", metavar="URL|DATEI", required=True, help="stand.json des letzten Builds")
    check.add_argument("--beobachten", type=Path, metavar="DATEI")
    args = parser.parse_args()

    if args.cmd == "zeige":
        return _show(args.query)
    if args.cmd == "check":
        return _check(args.vorher, args.beobachten)
    if args.cmd == "build":
        from . import stand
        from .build import build_site, read_watch_file

        watch_urls = read_watch_file(args.beobachten) if args.beobachten else []
        try:
            pages = build_site(args.out, settings, details=args.details, watch_urls=watch_urls,
                               previous=stand.load(args.vorher), anlass=args.anlass,
                               check_requests=args.pruef_abrufe)
        except SourceError as e:
            print(e, file=sys.stderr)
            return 2
        print(f"{pages} Seiten nach {args.out} geschrieben.")
        return 0
    import uvicorn

    uvicorn.run("antragshelper.web:app", host="127.0.0.1", port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
