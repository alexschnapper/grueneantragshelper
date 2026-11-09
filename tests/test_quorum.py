from antragshelper.models import Quorum


def test_example_vr01_amendment():
    q = Quorum(min_total=91, min_women=46, current_total=52, current_women=19)
    assert q.missing_total == 39
    assert q.missing_women == 27
    assert q.open_any_gender == 12
    assert q.still_needed == 39


def test_women_quorum_dominates():
    # Gesamtzahl erreicht, aber Frauen fehlen noch
    q = Quorum(min_total=91, min_women=46, current_total=95, current_women=40)
    assert q.missing_total == 0
    assert q.missing_women == 6
    assert q.open_any_gender == 0
    assert q.still_needed == 6


def test_reached():
    q = Quorum(min_total=91, reached=True)
    assert q.still_needed == 0
    assert q.progress_total == 1.0


def test_agenda_label():
    from antragshelper.models import agenda_label

    assert agenda_label("TOP 02 - Verantwortung übernehmen") == "im TOP 02"
    assert agenda_label("TOP 05- Wahl Rechnungsprüfungskommission") == "im TOP 05"
    assert agenda_label("Im V-Ranking priorisierte Anträge") == "in „Im V-Ranking priorisierte Anträge“"
