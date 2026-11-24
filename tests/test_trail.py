import osmium

from mapspack import trail
from tests.osm import write_osm

NODES = [{"id": i, "lat": 35 + i / 1000, "lon": 33} for i in range(1, 9)]


def _maxspeeds(path):
    return {w.id: w.tags.get("maxspeed") for w in osmium.FileProcessor(str(path), osmium.osm.WAY)}


def test_paved_slow_dirt_fast_rest_untouched(tmp_path):
    src = write_osm(tmp_path, NODES, ways=[
        {"id": 1, "nodes": [1, 2], "tags": {"highway": "primary", "maxspeed": "80"}},
        {"id": 2, "nodes": [2, 3], "tags": {"highway": "track"}},
        {"id": 3, "nodes": [3, 4], "tags": {"highway": "track", "tracktype": "grade1"}},
        {"id": 4, "nodes": [4, 5], "tags": {"highway": "unclassified", "surface": "gravel"}},
        {"id": 5, "nodes": [5, 6], "tags": {"highway": "track", "surface": "asphalt"}},
        {"id": 6, "nodes": [6, 7], "tags": {"highway": "footway"}},
        {"id": 7, "nodes": [7, 8], "tags": {"building": "yes"}},
    ])
    out = tmp_path / "trail.osm.pbf"
    assert trail.build(src, out) == {"paved": 3, "dirt": 2}
    speeds = _maxspeeds(out)
    paved, dirt = str(trail.PAVED_KMH), str(trail.DIRT_KMH)
    assert speeds == {1: paved, 2: dirt, 3: paved, 4: dirt, 5: paved, 6: None, 7: None}


def test_keeps_nodes_and_other_tags(tmp_path):
    src = write_osm(tmp_path, NODES[:2], ways=[
        {"id": 1, "nodes": [1, 2], "tags": {"highway": "track", "name": "Old road", "maxspeed:forward": "30"}}])
    out = tmp_path / "trail.osm.pbf"
    trail.build(src, out)
    (tags,) = [dict(w.tags) for w in osmium.FileProcessor(str(out), osmium.osm.WAY)]
    assert tags == {"highway": "track", "name": "Old road", "maxspeed": str(trail.DIRT_KMH)}
    assert sum(1 for _ in osmium.FileProcessor(str(out), osmium.osm.NODE)) == 2


def test_dirt_rule():
    assert trail.is_dirt({"highway": "track"})
    assert not trail.is_dirt({"highway": "track", "tracktype": "grade1"})
    assert trail.is_dirt({"highway": "residential", "surface": "compacted"})
    assert not trail.is_dirt({"highway": "track", "surface": "concrete"})
    assert not trail.is_dirt({"highway": "secondary"})
