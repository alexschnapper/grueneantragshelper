"""docs/fristen.md muss zu den Fristen und Schwellen im Code passen."""
from pathlib import Path

from antragshelper import service, stand, trend, zeitplan
from antragshelper.config import FRISTEN, Settings

DOKU = (Path(__file__).parent.parent / "docs" / "fristen.md").read_text(encoding="utf-8")


def test_fristen_stehen_in_der_doku():
    assert FRISTEN, "fristen.json ist leer"
    for pfad, fristen in FRISTEN.items():
        assert f"`{pfad}`" in DOKU
        for frist in (fristen.antraege, fristen.aenderungsantraege):
            assert frist.strftime("%d.%m.%Y, %H:%M Uhr") in DOKU


def test_fristen_json_wird_gelesen():
    assert Settings(consultation="52bdk").frist_fuer("motion") is not None
    assert Settings(consultation="gibt-es-nicht").frist_fuer("motion") is None


def test_schwellen_stehen_in_der_doku():
    stunden = lambda delta: f"{delta.total_seconds() / 3600:.0f} h"  # noqa: E731
    for wert in (trend.FENSTER, trend.FENSTER_LANG, trend.MIN_BEOBACHTUNG, trend.BELASTBAR_AB):
        assert f"| {stunden(wert)} |" in DOKU
    assert f"{round(trend.GRUEN_AB * 100)} %" in DOKU and f"{round(trend.GELB_AB * 100)} %" in DOKU
    for wert in (trend.WARNUNG_VOR_FRIST, trend.WARNUNG_VOR_FRIST_FRAUEN):
        assert f"**{wert.total_seconds() / 3600:.0f} Stunden**" in DOKU
    assert f"Minute {zeitplan.CHECK_MINUTE}" in DOKU
    assert "%02d:%02d UTC" % zeitplan.NIGHTLY_UTC in DOKU
    assert f"{stand.STATS_MAX_AGE.days} Tage" in DOKU
    assert f"{service.STATS_MIN_INTERVAL.total_seconds() / 3600:.0f} Std." in DOKU
    settings = Settings()
    assert f"{settings.ttl_index // 60} Min." in DOKU and f"{settings.ttl_detail // 60} Min." in DOKU
