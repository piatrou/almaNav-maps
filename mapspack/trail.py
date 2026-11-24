"""The trail extract: a copy of a country's extract for the second routing graph (trail_tiles.tar), where every
paved road is slow and every unpaved one fast. On that graph Valhalla's fastest way is the dirtiest one, and the app
blends back towards the shortest with use_distance: the dirt slider's upper half routes like the TransEuroTrail.

The speeds only steer the search; the app takes the route's cues, speeds and time from the normal graph."""

from pathlib import Path

import osmium

# Valhalla drops a maxspeed under 10 km/h and falls back to its default for the road class
PAVED_KMH = 10
# a track's default speed (about 7 km/h) is below the slowed asphalt: dirt must be the fast way
DIRT_KMH = 80

DRIVABLE = frozenset({
    "motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link", "unclassified", "residential", "living_street", "service", "road", "track",
})
UNPAVED = frozenset({
    "unpaved", "gravel", "fine_gravel", "dirt", "earth", "ground", "compacted", "sand", "grass", "mud", "pebblestone",
    "rock", "rocks", "woodchips", "clay", "salt", "snow", "ice",
})


def is_dirt(tags) -> bool:
    """A surface tag decides; untagged, a track is dirt unless it is grade1 (a paved farm road)."""
    surface = tags.get("surface")
    if surface is not None:
        return surface in UNPAVED
    return tags.get("highway") == "track" and tags.get("tracktype") != "grade1"


class _Retag(osmium.SimpleHandler):
    def __init__(self, writer):
        super().__init__()
        self.writer, self.paved, self.dirt = writer, 0, 0

    def node(self, n):
        self.writer.add_node(n)

    def relation(self, r):
        self.writer.add_relation(r)

    def way(self, w):
        if w.tags.get("highway") not in DRIVABLE:
            self.writer.add_way(w)
            return
        tags = {t.k: t.v for t in w.tags if not t.k.startswith("maxspeed")}
        if is_dirt(w.tags):
            tags["maxspeed"] = str(DIRT_KMH)
            self.dirt += 1
        else:
            tags["maxspeed"] = str(PAVED_KMH)
            self.paved += 1
        self.writer.add_way(w.replace(tags=tags))


def build(src: Path, dst: Path) -> dict[str, int]:
    """Writes the trail extract of `src` to `dst`; returns how many drivable ways went each way."""
    Path(dst).unlink(missing_ok=True)
    writer = osmium.SimpleWriter(str(dst))
    h = _Retag(writer)
    try:
        h.apply_file(str(src))
    finally:
        writer.close()
    return {"paved": h.paved, "dirt": h.dirt}
