import pytest

from mapspack.config import blocks, load_countries, plan

STATES = ("countries:\n"
          "  - {id: cyprus, name: Cyprus, geofabrik: europe/cyprus, drives_on_left: true}\n"
          "  - {id: greece, name: Greece, geofabrik: europe/greece, drives_on_left: false}\n"
          "  - {id: north-carolina, name: North Carolina, geofabrik: x/nc, drives_on_left: false, block: us-appalachia}\n"
          "  - {id: tennessee, name: Tennessee, geofabrik: x/tn, drives_on_left: false, block: us-appalachia}\n")


@pytest.fixture
def states(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text(STATES)
    return path


def test_states_share_a_block(states):
    countries, _ = load_countries(states)
    assert {c.id: c.block for c in countries} == {"cyprus": None, "greece": None,
                                                   "north-carolina": "us-appalachia", "tennessee": "us-appalachia"}


def test_blocks_group_members_and_keep_standalone_alone(states):
    countries, _ = load_countries(states)
    assert {k: [c.id for c in v] for k, v in blocks(countries).items()} == {
        "cyprus": ["cyprus"], "greece": ["greece"], "us-appalachia": ["north-carolina", "tennessee"]}


def test_block_id_must_not_clash_with_a_country(tmp_path):
    # a block named like a country would merge a standalone pack into it
    (tmp_path / "c.yaml").write_text("countries:\n"
                                     "  - {id: a, name: A, geofabrik: x/a, drives_on_left: false, block: b}\n"
                                     "  - {id: b, name: B, geofabrik: x/b, drives_on_left: false}\n")
    with pytest.raises(ValueError):
        blocks(load_countries(tmp_path / "c.yaml")[0])


def test_plan_expands_a_member_to_its_block(states):
    assert plan(["tennessee"], states) == ["us-appalachia"]
    assert plan([], states) == ["cyprus", "greece", "us-appalachia"]
    assert plan(["greece", "north-carolina", "tennessee"], states) == ["greece", "us-appalachia"]
    with pytest.raises(SystemExit):
        plan(["nowhere"], states)


def test_plan_of_the_real_list_builds_every_country():
    assert plan([]) == ["cyprus", "greece", "georgia"]
