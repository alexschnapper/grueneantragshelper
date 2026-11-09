from antragshelper.models import ActivityEntry, group_activity

BASE = "https://antraege.gruene.de/52bdk"


def entry(motion, action, url):
    return ActivityEntry(when="Heute", motion=motion, action=action, url=url)


def test_group_activity_by_motion():
    groups = group_activity([
        entry("W-04: Wachstum", "Änderungsantrag W-04-070 veröffentlicht", f"{BASE}/w04/1"),
        entry("KI-03: KI", "Änderungsantrag KI-03-167 veröffentlicht", f"{BASE}/ki03/2"),
        entry("W-04: Wachstum", "Änderungsantrag W-04-071 veröffentlicht", f"{BASE}/w04/3"),
        entry("V-07: Neu", "Antrag veröffentlicht", f"{BASE}/v07"),
    ])
    assert [g.motion for g in groups] == ["W-04: Wachstum", "KI-03: KI", "V-07: Neu"]
    w04 = groups[0]
    assert w04.amendment_count == 2
    assert w04.latest.action == "Änderungsantrag W-04-070 veröffentlicht"
    assert w04.motion_url == f"{BASE}/w04"
    assert groups[2].amendment_count == 0
    assert groups[2].motion_url == f"{BASE}/v07"
