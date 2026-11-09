from pathlib import Path

from antragshelper.parsers import parse_activitylog, parse_detail, parse_feed, parse_index, parse_quorum

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://antraege.gruene.de"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_index_counts_and_lookup():
    index = parse_index(read("home.html"), BASE)
    assert [e.prefix for e in index.motions] == ["VR-01", "VR-02", "WO-RP 01"]
    assert [e.prefix for e in index.amendments] == ["S-01", "VR-02-284", "VR-02-300"]

    am = index.find("vr-02-284")
    assert am.url == f"{BASE}/52bdk/chancen-antrag-2/201"
    assert am.parent_prefix == "VR-02"
    assert am.women_share == 56
    assert index.find("wo-rp-01").withdrawn
    assert index.find("VR-02-300").withdrawn
    assert index.find("XX-99") is None

    stats = index.by_agenda_item()
    assert stats["Im V-Ranking priorisierte Anträge"] == {"motions": 3, "amendments": 2, "withdrawn": 2}
    assert stats["TOP 03 - Satzung"] == {"motions": 0, "amendments": 1, "withdrawn": 0}


def test_detail_collecting_amendment():
    d = parse_detail(read("amendment_collecting.html"), f"{BASE}/52bdk/wasser-antrag-1/999")
    assert d.kind == "amendment"
    assert d.status == "Antragsteller*innen sammeln"
    assert d.women_share == 36
    assert d.supporter_count == 52
    assert d.parent_url == f"{BASE}/52bdk/wasser-antrag-1"
    q = d.quorum
    assert (q.min_total, q.min_women, q.current_total, q.current_women) == (91, 46, 52, 19)
    assert d.collecting


def test_detail_never_contains_names():
    d = parse_detail(read("amendment_collecting.html"), f"{BASE}/x")
    assert "Muster" not in repr(d)


def test_detail_reached_and_submitted():
    reached = parse_detail(read("motion_reached.html"), f"{BASE}/a")
    assert reached.quorum.reached and reached.quorum.min_total == 91
    assert not reached.collecting

    submitted = parse_detail(read("motion_submitted.html"), f"{BASE}/b")
    assert submitted.kind == "motion"
    assert submitted.status == "Eingereicht"
    assert submitted.quorum is None


def test_quorum_without_women():
    q = parse_quorum("Nötig sind mindestens 20 Unterstützer*innen (aktueller Stand: 7).")
    assert (q.min_total, q.current_total, q.min_women) == (20, 7, None)
    assert q.still_needed == 13


def test_activitylog_omits_actor():
    [entry] = parse_activitylog(read("activitylog.html"), BASE)
    assert entry.when == "Heute, 12:20"
    assert entry.action == "Änderungsantrag KI-03-167 veröffentlicht"
    assert entry.url == f"{BASE}/52bdk/ki-antrag/300"
    assert "Muster" not in repr(entry)


def test_feed():
    [item] = parse_feed(read("feed.xml"))
    assert item.title == "VR-01: Wasser sichern"
    assert "Muster" not in repr(item)


def test_index_filter():
    index = parse_index(read("home.html"), BASE)
    assert [e.prefix for e in index.filter(kind="motion", withdrawn=False)] == ["VR-01", "VR-02"]
    assert [e.prefix for e in index.filter(withdrawn=True)] == ["VR-02-300", "WO-RP 01"]
    assert [e.prefix for e in index.filter(agenda_item="TOP 03 - Satzung")] == ["S-01"]
    assert [e.prefix for e in index.filter(text="wasser")] == ["VR-01"]
    assert index.agenda_items == ["TOP 03 - Satzung", "Im V-Ranking priorisierte Anträge"]


def test_index_status():
    index = parse_index(read("home.html"), BASE)
    withdrawn = index.find("WO-RP 01")
    assert withdrawn.status == "Zurückgezogen"
    assert withdrawn.women_share == 51
    assert index.find("VR-01").status == "Eingereicht"
    assert index.find("VR-02-300").status == "Zurückgezogen"


def test_group_amendments():
    index = parse_index(read("home.html"), BASE)
    groups = index.group_amendments(index.amendments)
    assert [g.label for g in groups] == [
        "TOP 03 - Satzung – eigenständige Änderungsanträge",
        "VR-02: Chancen",
    ]
    vr02 = groups[1]
    assert vr02.motion.prefix == "VR-02"
    assert (vr02.active_count, vr02.withdrawn_count) == (1, 1)
    assert [e.prefix for e in vr02.entries] == ["VR-02-284", "VR-02-300"]

    only_withdrawn = index.group_amendments([index.find("VR-02-300"), index.find("S-01")])
    assert [g.label for g in only_withdrawn][-1] == "VR-02: Chancen"


def test_index_consultation_quorum():
    index = parse_index(read("home.html"), BASE)
    assert (index.min_total, index.min_women) == (91, 46)
