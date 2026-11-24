import hashlib
from datetime import UTC, datetime

from mapspack.config import load_countries
import pytest

from mapspack.manifest import OverBudget, merge, pack_entry, retired, to_free

CYPRUS = load_countries()[0][0]


def test_merge_keeps_countries_not_rebuilt():
    old = {"schema": 1, "packs": [{"id": "cyprus", "version": "2026-11-01"}, {"id": "greece", "version": "2026-11-01"}]}
    new = merge(old, [{"id": "greece", "version": "2026-12-01"}], "2026-12-02T00:00:00Z")
    assert [(p["id"], p["version"]) for p in new["packs"]] == [("cyprus", "2026-11-01"), ("greece", "2026-12-01")]
    assert new["generated"] == "2026-12-02T00:00:00Z" and new["schema"] == 1


def test_merge_orders_by_country_list_and_starts_empty():
    new = merge(None, [{"id": "tennessee", "version": "b"}, {"id": "cyprus", "version": "c"}], "t")
    assert [p["id"] for p in new["packs"]] == ["cyprus", "tennessee"]


def test_merge_drops_countries_removed_from_the_list():
    old = {"schema": 1, "packs": [{"id": "cyprus", "version": "v1"}, {"id": "belarus", "version": "v1"}]}
    new = merge(old, [{"id": "cyprus", "version": "v2"}], "t")
    assert [p["id"] for p in new["packs"]] == ["cyprus"]


def test_retired_waits_seven_days():
    cur = {"packs": [{"id": "cyprus", "version": "2026-12-01", "published": "2026-12-02T00:00:00Z"}]}
    listing = {"cyprus": ["2026-11-01", "2026-12-01"]}
    assert retired(listing, cur, datetime(2026, 12, 8, tzinfo=UTC)) == []
    assert retired(listing, cur, datetime(2026, 12, 10, tzinfo=UTC)) == ["packs/cyprus/2026-11-01/"]


def test_retired_never_touches_unknown_countries():
    cur = {"packs": [{"id": "cyprus", "version": "v2", "published": "2026-01-01T00:00:00Z"}]}
    assert retired({"poland": ["v1"]}, cur, datetime(2026, 12, 10, tzinfo=UTC)) == []


def test_entry_hashes_every_file(tmp_path):
    for n in ("valhalla_tiles.tar", "trail_tiles.tar", "landmarks.json", "basemap.mbtiles", "search.sqlite", "zones.json"):
        (tmp_path / n).write_text("x")
    (tmp_path / "lanes.json").write_text("{}")
    e = pack_entry(CYPRUS, "2026-12-01", tmp_path, "packs/cyprus/2026-12-01/", [[0, 0]], "2026-12-02T00:00:00Z")
    f = next(f for f in e["files"] if f["name"] == "lanes.json")
    assert f["name"] == "lanes.json" and f["size"] == 2 and f["sha256"] == hashlib.sha256(b"{}").hexdigest()
    assert f["path"] == "packs/cyprus/2026-12-01/lanes.json"
    assert e["valhalla"] == "3.9.1" and e["drivesOnLeft"] is True and e["name"] == "Cyprus"


def test_version_falls_back_to_today_without_header_stamp(tmp_path):
    from mapspack.cli import pbf_version
    from tests.osm import write_osm
    assert pbf_version(write_osm(tmp_path, nodes=[])) == datetime.now(UTC).strftime("%Y-%m-%d")


def test_entry_refuses_a_pack_missing_a_file(tmp_path):
    import pytest
    from mapspack.manifest import PackIncomplete
    for n in ("valhalla_tiles.tar", "lanes.json", "landmarks.json", "search.sqlite"):
        (tmp_path / n).write_text("x")
    with pytest.raises(PackIncomplete, match="basemap.mbtiles"):
        pack_entry(load_countries()[0][1], "v", tmp_path, "p/", [[0, 0]], "t")  # Greece: no zones needed


def test_entry_needs_zones_when_the_country_has_them(tmp_path):
    import pytest
    from mapspack.manifest import PackIncomplete
    for n in ("valhalla_tiles.tar", "lanes.json", "landmarks.json", "basemap.mbtiles", "search.sqlite"):
        (tmp_path / n).write_text("x")
    with pytest.raises(PackIncomplete, match="zones.json"):
        pack_entry(CYPRUS, "v", tmp_path, "p/", [[0, 0]], "t")


def test_entry_names_the_block(tmp_path):
    for n in ("valhalla_tiles.tar", "trail_tiles.tar", "landmarks.json", "basemap.mbtiles", "search.sqlite", "lanes.json"):
        (tmp_path / n).write_text("x")
    nc = next(c for c in load_countries()[0] if c.id == "north-carolina")
    e = pack_entry(nc, "2026-12-01", tmp_path, "packs/north-carolina/2026-12-01/", [[0, 0]], "t")
    assert e["block"] == "us-appalachia"
    (tmp_path / "zones.json").write_text("x")
    assert "block" not in pack_entry(CYPRUS, "2026-12-01", tmp_path, "p/", [[0, 0]], "t")


CUR = {"packs": [{"id": "cyprus", "version": "v3"}, {"id": "greece", "version": "v2"}]}
USAGE = {"*": 9_000, "packs/cyprus/v1/": 1_000, "packs/cyprus/v2/": 2_000, "packs/cyprus/v3/": 3_000,
         "packs/greece/v1/": 1_500, "packs/greece/v2/": 1_500}


def test_to_free_nothing_within_budget():
    assert to_free(USAGE, CUR, incoming=1_000, budget=10_000) == []


def test_to_free_drops_oldest_retired_first_and_no_more_than_needed():
    assert to_free(USAGE, CUR, incoming=2_500, budget=10_000) == ["packs/cyprus/v1/", "packs/greece/v1/"]


def test_to_free_never_drops_a_live_version():
    assert to_free(USAGE, CUR, incoming=5_500, budget=10_000) == ["packs/cyprus/v1/", "packs/greece/v1/",
                                                                   "packs/cyprus/v2/"]
    with pytest.raises(OverBudget):
        to_free(USAGE, CUR, incoming=6_000, budget=10_000)


def test_to_free_without_a_manifest_everything_is_retired():
    assert to_free({"*": 3, "packs/cyprus/v1/": 3}, None, incoming=8, budget=10) == ["packs/cyprus/v1/"]
