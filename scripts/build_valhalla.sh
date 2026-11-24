#!/usr/bin/env bash
# Valhalla routing tiles for one country: <pbf> -> <outdir>/valhalla_tiles.tar
#   with "trail": <trail pbf> -> <outdir>/trail_tiles.tar, the second graph the dirt slider routes on (mapspack trail);
#   no elevation there: the app takes grades, speeds and cues from the normal graph.
# The Valhalla version must match the one inside the app (valhalla-mobile 0.6.4 = Valhalla 3.9.1): tiles from
# another version do not load. Admins (driving side, country), time zones and elevation (grades for the cues) are in.
set -euo pipefail
[ $# -eq 2 ] || [ $# -eq 3 -a "${3:-}" = trail ] || { echo "usage: $0 <pbf> <outdir> [trail]" >&2; exit 2; }
PBF=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
OUT=$(mkdir -p "$2" && cd "$2" && pwd)
IMAGE=ghcr.io/valhalla/valhalla:3.9.1
TAR=valhalla_tiles.tar ELEVATION=1
[ "${3:-}" = trail ] && TAR=trail_tiles.tar ELEVATION=0

docker run --rm -e TAR=$TAR -e ELEVATION=$ELEVATION -v "$PBF:/in/extract.osm.pbf:ro" -v "$OUT:/out" --entrypoint bash "$IMAGE" -c '
set -euo pipefail
W=/work; mkdir -p $W/tiles $W/elevation
step() { local t0=$SECONDS; "$@" > $W/step.log 2>&1 || { tail -40 $W/step.log; exit 1; }; echo "$1 ${*:2:2}: $((SECONDS - t0)) s"; }
valhalla_build_config --mjolnir-tile-dir $W/tiles --mjolnir-tile-extract /out/$TAR \
  --mjolnir-admin $W/admins.sqlite --mjolnir-timezone $W/timezones.sqlite \
  --additional-data-elevation $W/elevation --mjolnir-concurrency $(nproc) > $W/valhalla.json
step valhalla_build_admins -c $W/valhalla.json /in/extract.osm.pbf
t0=$SECONDS  # this one writes the database to stdout
valhalla_build_timezones > $W/timezones.sqlite 2> $W/step.log || { tail -40 $W/step.log; exit 1; }
[ -s $W/timezones.sqlite ] || { echo "timezones.sqlite is empty" >&2; exit 1; }
echo "valhalla_build_timezones: $((SECONDS - t0)) s, $(du -m $W/timezones.sqlite | cut -f1) MB"
step valhalla_build_tiles -c $W/valhalla.json -e bss /in/extract.osm.pbf
[ $ELEVATION = 1 ] && step valhalla_build_elevation --from-tiles --decompress -c $W/valhalla.json
step valhalla_build_tiles -c $W/valhalla.json -s hierarchy /in/extract.osm.pbf
step valhalla_build_extract -c $W/valhalla.json -v
cp $W/valhalla.json /out/valhalla.json
'
ls -l "$OUT/$TAR"
