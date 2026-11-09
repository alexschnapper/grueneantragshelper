from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from antragshelper import zeitplan

WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "pages.yml"


def test_schedule_matches_workflow():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    crons = [s["cron"] for s in workflow[True]["schedule"]]  # YAML liest "on" als True
    assert f"{zeitplan.CHECK_MINUTE} * * * *" in crons
    nightly = f"{zeitplan.NIGHTLY_UTC[1]} {zeitplan.NIGHTLY_UTC[0]} * * *"
    assert nightly in crons
    assert f'"schedule:{nightly}"' in WORKFLOW.read_text(encoding="utf-8")  # Anlass-Erkennung im Prüfschritt


def test_next_runs():
    berlin = timezone(timedelta(hours=1))
    now = datetime(2026, 11, 9, 18, 30, tzinfo=berlin)
    assert zeitplan.next_check(now) == datetime(2026, 11, 9, 19, 23, tzinfo=berlin)
    assert zeitplan.next_check(now.replace(minute=10)) == datetime(2026, 11, 9, 18, 23, tzinfo=berlin)
    # 02:41 UTC = 03:41 Uhr MEZ am Folgetag
    assert zeitplan.next_nightly(now) == datetime(2026, 11, 10, 3, 41, tzinfo=berlin)


def test_push_builds_only_for_code_changes():
    """Regel: Reine Doku-Pushes dürfen keine Abrufe bei antraege.gruene.de auslösen."""
    push = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))[True]["push"]
    paths = push["paths"]
    assert "paths-ignore" not in push  # Positivliste, damit neue Doku-Dateien automatisch ausgenommen sind
    assert set(paths) == {"antragshelper/**", "pyproject.toml", "beobachtet.txt"}
    for doc in ("README.md", "KONZEPT.md", "CLAUDE.md", "docs/sharepic/README.md", "tests/test_build.py",
                ".github/workflows/pages.yml"):
        assert not any(_matches(doc, p) for p in paths), doc
    assert _matches("antragshelper/templates/base.html", "antragshelper/**")


def _matches(path: str, pattern: str) -> bool:
    return path.startswith(pattern[:-2]) if pattern.endswith("/**") else path == pattern
