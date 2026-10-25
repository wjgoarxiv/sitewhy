"""Python port of Meterless engines/world-model/conformance/runner.ts.

Each test keeps the reference check id. A green run is the spec's definition of done.
"""

import pytest

from app.worldmodel import ProvenanceError, WorldModel, decide, entity_id_from_name, normalize_name

OBSERVATIONS = [
    {
        "externalId": "a1",
        "title": "Fed holds rates",
        "at": "2026-05-17T14:00:00.000Z",
        "source": {"kind": "rss", "at": "2026-05-17T14:00:00.000Z"},
        "entities": [{"type": "person", "name": "Jerome Powell"}],
    },
    {
        "externalId": "a2",
        "title": "Powell signals patience",
        "at": "2026-05-17T16:30:00.000Z",
        "source": {"kind": "rss", "at": "2026-05-17T16:30:00.000Z"},
        "entities": [{"type": "person", "name": "Jerome Powell"}],
    },
]


def at(s):
    return {"kind": "manual", "at": s}


def test_sid_001_diacritics_and_nbsp_normalize_identically():
    assert normalize_name("José  García") == normalize_name("Jose Garcia")
    assert entity_id_from_name("person", "José García") == entity_id_from_name(
        "person", "jose garcia"
    )


def test_sid_002_distinct_names_stay_distinct():
    assert entity_id_from_name("org", "Acme Corp") != entity_id_from_name("org", "Acme Corporation")
    assert entity_id_from_name("person", "x") != entity_id_from_name("org", "x")


def test_band_001_merge_bands_at_boundaries():
    assert decide(0.85) == "auto-merge"
    assert decide(0.84) == "review"
    assert decide(0.82) == "review"
    assert decide(0.81) == "new"


def test_prov_001_writes_without_provenance_are_rejected():
    world = WorldModel()
    with pytest.raises(ProvenanceError):
        world.upsert_entity(type="person", name="No Provenance", source=None)


def test_idem_001_same_batch_twice_is_an_empty_diff():
    world = WorldModel()
    world.ingest(OBSERVATIONS)
    shape1 = world.state_shape_canonical()
    second = world.ingest(OBSERVATIONS)
    assert second["changed"] is False
    assert world.state_shape_canonical() == shape1


def test_idem_002_mutated_batch_changes_the_shape():
    world = WorldModel()
    world.ingest(OBSERVATIONS)
    shape1 = world.state_shape_canonical()
    mutated = [
        {**OBSERVATIONS[0], "title": OBSERVATIONS[0]["title"] + " (edited)"},
        OBSERVATIONS[1],
    ]
    assert world.ingest(mutated)["changed"] is True
    assert world.state_shape_canonical() != shape1


def test_bitemp_001_superseding_edge_closes_old_and_point_in_time_works():
    world = WorldModel()
    world.upsert_entity(
        type="player", external_key={"system": "g", "id": "p1"}, source=at("2087-01-01T00:00:00Z")
    )
    world.upsert_entity(
        type="team", external_key={"system": "g", "id": "a"}, source=at("2087-01-01T00:00:00Z")
    )
    world.upsert_entity(
        type="team", external_key={"system": "g", "id": "b"}, source=at("2088-03-01T00:00:00Z")
    )
    world.relate(
        "player:g:p1",
        "plays-for",
        "team:g:a",
        valid_from="2087-01-01T00:00:00Z",
        source=at("2087-01-01T00:00:00Z"),
    )
    world.relate(
        "player:g:p1",
        "plays-for",
        "team:g:b",
        valid_from="2088-03-01T00:00:00Z",
        source=at("2088-03-01T00:00:00Z"),
    )
    graph = world.view("graph")
    assert [e["id"] for e in graph.neighbors_of("player:g:p1", via="plays-for")] == ["team:g:b"]
    then = graph.neighbors_of("player:g:p1", via="plays-for", at="2087-06-01T00:00:00Z")
    assert [e["id"] for e in then] == ["team:g:a"]


def test_audit_001_every_mutation_writes_an_ordered_audit_entry():
    world = WorldModel()
    world.upsert_entity(type="x", name="Audit One", source=at("2026-01-01T00:00:00Z"))
    world.upsert_entity(type="x", name="Audit Two", source=at("2026-01-02T00:00:00Z"))
    audit = world.audit()
    assert len(audit) >= 2
    assert all(b["seq"] > a["seq"] for a, b in zip(audit, audit[1:], strict=False))
