from datetime import date
from pathlib import Path

from antragshelper.dashboard import QuorumPoint, build
from antragshelper.models import ActivityEntry
from antragshelper.parsers import parse_index

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://antraege.gruene.de"


def test_quorum_point_buffer():
    # 102 Mitantragsteller*innen + Antragsteller*in = 103 Personen, 56 % -> 58 Frauen
    p = QuorumPoint("VR-02-284", "amendment", "u", supporters=102, women_share=56, min_total=91, min_women=46)
    assert (p.persons, p.women) == (103, 58)
    assert (p.buffer_total, p.buffer_women, p.buffer) == (11, 12, 11)
    assert p.meets

    # niedriger Frauenanteil reicht nur bei vielen Personen
    low = QuorumPoint("X", "motion", "u", supporters=95, women_share=40, min_total=91, min_women=46)
    assert low.women == 38 and not low.meets


def test_activity_day():
    today = date(2026, 11, 9)
    assert ActivityEntry("Heute, 12:20", "", "", "").day(today) == today
    assert ActivityEntry("Gestern, 09:00", "", "", "").day(today) == date(2026, 11, 8)
    assert ActivityEntry("04.11.2026, 16:18", "", "", "").day(today) == date(2026, 11, 4)
    assert ActivityEntry("4h", "", "", "").day(today) is None


def test_build_dashboard():
    index = parse_index((FIXTURES / "home.html").read_text(encoding="utf-8"), BASE)
    index.min_total, index.min_women = 91, 46
    activity = [
        ActivityEntry("Heute, 10:00", "VR-02", "Änderungsantrag VR-02-284 veröffentlicht", ""),
        ActivityEntry("07.11.2026, 10:00", "VR-01", "Antrag veröffentlicht", ""),
    ]
    stats = [{"prefix": "VR-02-284", "kind": "amendment", "url": "u", "supporter_count": 102, "women_share": 56}]
    dash = build(index, activity, stats, today=date(2026, 11, 9))

    assert dash.counts["motions"] == 3 and dash.counts["withdrawn"] == 2
    assert [(r.label, r.values) for r in dash.per_agenda_motions] == [("„Im V-Ranking priorisierte Anträge“", [2, 1])]
    assert dash.women_histogram[5].values == [0, 1]  # 56 % (eingereicht), 51 % ist zurückgezogen
    assert [r.label for r in dash.activity_days] == ["07.11.", "08.11.", "09.11."]
    assert [r.values for r in dash.activity_days] == [[1, 0], [0, 0], [0, 1]]
    assert dash.most_amended[0].label == "VR-02" and dash.most_amended[0].values == [1, 1]
    assert [p.prefix for p in dash.quorum_points] == ["VR-02-284"]


def test_without_quorum_split():
    index = parse_index((FIXTURES / "home.html").read_text(encoding="utf-8"), BASE)
    index.min_total, index.min_women = 91, 46
    stats = [
        {"prefix": "VR-02-284", "kind": "amendment", "url": "a", "supporter_count": 102, "women_share": 56},
        {"prefix": "X-1", "kind": "amendment", "url": "b", "supporter_count": 0, "women_share": 100},
    ]
    dash = build(index, [], stats, today=date(2026, 11, 9))
    assert [p.prefix for p in dash.with_quorum] == ["VR-02-284"]
    assert [p.prefix for p in dash.without_quorum] == ["X-1"]
    assert dash.supporters_median == 102  # ohne die Einträge ohne Quorum

    from antragshelper.dashboard import without_quorum_urls
    assert without_quorum_urls(stats, 91) == {"b"}
    assert without_quorum_urls(stats, None) == set()
