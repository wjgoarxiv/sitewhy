from app.worldmodel import WorldModel, entity_id_from_name

SRC = {"kind": "agent", "at": "2026-10-25T00:00:00Z", "role": "investigator", "model": "m"}


def build(world):
    rule = world.upsert_entity(
        type="rule", name="Washington County moratorium", attrs={"layer": "county"}, source=SRC
    )
    doc = world.upsert_entity(
        type="source_document",
        name="https://example.gov/ord-2026-12.pdf",
        attrs={"url": "https://example.gov/ord-2026-12.pdf"},
        source=SRC,
    )
    claim = world.add_claim(
        layer="county",
        text="The county paused data center approvals for 12 months.",
        quote="a 12-month moratorium",
        rule_id=rule,
        source_id=doc,
        source=SRC,
    )
    return rule, doc, claim


def test_claim_ids_are_content_derived_and_idempotent():
    world = WorldModel()
    _, _, c1 = build(world)
    n_events = len(world.audit())
    _, _, c2 = build(world)
    assert c1 == c2 and len(world.audit()) == n_events
    assert len(world.claims_for("county")) == 1


def test_evidence_path_walks_claim_to_source_and_rule():
    world = WorldModel()
    rule, doc, claim = build(world)
    path = world.evidence_path(claim)
    assert [p["type"] for p in path] == ["claim", "source_document", "rule"]
    assert path[0]["attrs"]["quote"] == "a 12-month moratorium"
    assert rule == entity_id_from_name("rule", "Washington County moratorium")


def test_contradicting_claims_surface_as_conflicts_and_objections_close():
    world = WorldModel()
    rule, doc, claim = build(world)
    other = world.add_claim(
        layer="county",
        text="The moratorium was rescinded.",
        quote="rescinded",
        rule_id=rule,
        source_id=doc,
        source=SRC,
    )
    world.relate(other, "contradicts", claim, source=SRC, exclusive=False)
    assert world.conflicts() == [(other, claim)]
    obj = world.add_objection(target_id=claim, text="Quote not verified", round=1, source=SRC)
    assert [o["id"] for o in world.open_objections()] == [obj]
    world.resolve_objection(obj, resolution="verified on retry", source=SRC)
    assert world.open_objections() == []


def test_log_replay_rebuilds_identical_state(tmp_path):
    log = tmp_path / "worldmodel.jsonl"
    world = WorldModel(log_path=log)
    build(world)
    replayed = WorldModel.replay(log)
    assert replayed.state_shape_canonical() == world.state_shape_canonical()
    assert replayed.claims_for("county") == world.claims_for("county")
