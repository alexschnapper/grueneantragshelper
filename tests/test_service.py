from pathlib import Path

from antragshelper.config import Settings
from antragshelper.models import Detail, Quorum
from antragshelper.parsers import parse_index
from antragshelper.service import Antragshelper, WatchedItem

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://antraege.gruene.de"


def test_amendments_of_combines_published_and_watched(tmp_path, monkeypatch):
    helper = Antragshelper(Settings(db_path=tmp_path / "db.sqlite3"))
    index = parse_index((FIXTURES / "home.html").read_text(encoding="utf-8"), BASE)
    collecting = WatchedItem(
        f"{BASE}/52bdk/chancen-antrag-2/999", "ÄA",
        Detail(url="", title="", kind="amendment", quorum=Quorum(91, 46, 52, 19)),
    )
    other = WatchedItem(f"{BASE}/52bdk/chancen-antrag-22/5", "anderer Antrag", None)
    monkeypatch.setattr(helper, "index", lambda: index)
    monkeypatch.setattr(helper, "watchlist", lambda: [collecting, other])

    published, watched = helper.amendments_of(f"{BASE}/52bdk/chancen-antrag-2")
    assert [e.prefix for e in published] == ["VR-02-284", "VR-02-300"]
    assert watched == [collecting]
