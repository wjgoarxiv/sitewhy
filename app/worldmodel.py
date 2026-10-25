"""Meterless World Model engine, implemented in Python from the open spec
(github.com/Meterless/Meterless, engines/world-model/AGENTS.md, Apache-2.0).

Pure-graph aggregate with bitemporal edges. Every mutation is an event in an
append-only log (optionally a JSONL file); the in-memory state is a projection
of that log, so `WorldModel.replay(path)` rebuilds it exactly. IDs are derived
from content, so re-ingesting the same observation is a no-op.

SiteWhy uses it as the shared evidence graph: rules, source documents, claims,
objections, and the edges between them (cites, supports, contradicts,
objection_on), each carrying the agent role and model that wrote it.
"""

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

AUTO_MERGE = 0.85
REVIEW = 0.82


class ProvenanceError(ValueError):
    pass


def normalize_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip().lower()


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def entity_id_from_name(type_: str, name: str) -> str:
    norm = normalize_name(name)
    slug = re.sub(r"[^a-z0-9]+", "-", norm).strip("-")[:40]
    return f"{type_}:{slug}-{_short_hash(type_ + '|' + norm)}"


def decide(similarity: float) -> str:
    """Merge banding for entity resolution."""
    if similarity >= AUTO_MERGE:
        return "auto-merge"
    if similarity >= REVIEW:
        return "review"
    return "new"


def _ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _check_source(source: dict | None) -> dict:
    if not source or not source.get("kind") or not source.get("at"):
        raise ProvenanceError("every write needs a source with 'kind' and 'at'")
    return dict(source)


class GraphView:
    def __init__(self, world: "WorldModel"):
        self.world = world

    def neighbors_of(self, node_id: str, via: str, at: str | None = None) -> list[dict]:
        when = _ts(at)
        out = []
        for e in self.world.edges.values():
            if e["from"] != node_id or e["type"] != via:
                continue
            start, end = _ts(e["valid_from"]), _ts(e["valid_to"])
            if when is None:
                valid = end is None
            else:
                valid = (start is None or start <= when) and (end is None or when < end)
            if valid:
                out.append(self.world.entities[e["to"]])
        return sorted(out, key=lambda x: x["id"])


class WorldModel:
    def __init__(self, log_path: Path | None = None):
        self.entities: dict[str, dict] = {}
        self.edges: dict[str, dict] = {}
        self._events: list[dict] = []
        self.log_path = Path(log_path) if log_path else None
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

    # -- event log -------------------------------------------------------

    def _emit(self, op: str, payload: dict, source: dict) -> None:
        event = {"seq": len(self._events) + 1, "op": op, "payload": payload, "source": source}
        self._apply(event)
        if self.log_path:
            with self.log_path.open("a") as f:
                f.write(json.dumps(event, sort_keys=True) + "\n")

    def _apply(self, event: dict) -> None:
        p = event["payload"]
        if event["op"] == "upsert_entity":
            current = self.entities.get(p["id"], {"attrs": {}})
            self.entities[p["id"]] = {
                "id": p["id"],
                "type": p["type"],
                "name": p["name"],
                "attrs": {**current["attrs"], **p["attrs"]},
                "source": event["source"],
            }
        elif event["op"] == "relate":
            self.edges[p["id"]] = {**p, "source": event["source"]}
        elif event["op"] == "close_edge":
            self.edges[p["id"]]["valid_to"] = p["valid_to"]
        self._events.append(event)

    @classmethod
    def replay(cls, log_path: Path) -> "WorldModel":
        world = cls()
        for line in Path(log_path).read_text().splitlines():
            world._apply(json.loads(line))
        return world

    def audit(self) -> list[dict]:
        return list(self._events)

    # -- writes ----------------------------------------------------------

    def upsert_entity(
        self,
        type: str,
        source: dict | None,
        name: str | None = None,
        external_key: dict | None = None,
        attrs: dict | None = None,
    ) -> str:
        source = _check_source(source)
        if external_key:
            entity_id = f"{type}:{external_key['system']}:{external_key['id']}"
        elif name:
            entity_id = entity_id_from_name(type, name)
        else:
            raise ValueError("entity needs a name or an external_key")
        attrs = attrs or {}
        current = self.entities.get(entity_id)
        display = name or entity_id
        if current and current["name"] == display and attrs.items() <= current["attrs"].items():
            return entity_id
        self._emit(
            "upsert_entity",
            {"id": entity_id, "type": type, "name": display, "attrs": attrs},
            source,
        )
        return entity_id

    def relate(
        self,
        frm: str,
        type: str,
        to: str,
        source: dict | None,
        valid_from: str | None = None,
        props: dict | None = None,
        exclusive: bool = True,
    ) -> str:
        """Add a directed edge. With `exclusive`, a new target supersedes (closes)
        the open edge of the same type from the same node."""
        source = _check_source(source)
        for node in (frm, to):
            if node not in self.entities:
                raise KeyError(f"unknown node {node!r}")
        valid_from = valid_from or source["at"]
        for e in list(self.edges.values()):
            if e["from"] == frm and e["type"] == type and e["valid_to"] is None:
                if e["to"] == to:
                    return e["id"]
                if exclusive:
                    self._emit("close_edge", {"id": e["id"], "valid_to": valid_from}, source)
        edge_id = f"edge:{_short_hash(f'{frm}|{type}|{to}|{valid_from}')}"
        self._emit(
            "relate",
            {
                "id": edge_id,
                "from": frm,
                "type": type,
                "to": to,
                "valid_from": valid_from,
                "valid_to": None,
                "props": props or {},
            },
            source,
        )
        return edge_id

    def ingest(self, observations: list[dict]) -> dict:
        before = self.state_shape_canonical()
        for obs in observations:
            item = self.upsert_entity(
                type="item",
                external_key={"system": "ingest", "id": obs["externalId"]},
                attrs={"title": obs.get("title"), "at": obs.get("at")},
                source=obs.get("source"),
            )
            for ent in obs.get("entities", []):
                ent_id = self.upsert_entity(
                    type=ent["type"], name=ent["name"], source=obs["source"]
                )
                self.relate(
                    item, "mentions", ent_id, source=obs["source"], valid_from=obs.get("at"),
                    exclusive=False,
                )  # fmt: skip
        return {"changed": self.state_shape_canonical() != before}

    # -- reads -----------------------------------------------------------

    def view(self, name: str) -> GraphView:
        if name != "graph":
            raise ValueError(f"unknown view {name!r}")
        return GraphView(self)

    def state_shape_canonical(self) -> str:
        ents = sorted(
            ({k: e[k] for k in ("id", "type", "name", "attrs")} for e in self.entities.values()),
            key=lambda e: e["id"],
        )
        edges = sorted(
            (
                {k: e[k] for k in ("from", "type", "to", "valid_from", "valid_to", "props")}
                for e in self.edges.values()
            ),
            key=lambda e: json.dumps(e, sort_keys=True),
        )
        return json.dumps({"entities": ents, "edges": edges}, sort_keys=True)

    # -- SiteWhy domain surface -----------------------------------------

    def add_claim(
        self,
        layer: str,
        text: str,
        quote: str,
        rule_id: str,
        source_id: str,
        source: dict,
        attrs: dict | None = None,
    ) -> str:
        claim_id = self.upsert_entity(
            type="claim",
            name=f"{rule_id}|{source_id}|{quote}|{text}",
            attrs={"layer": layer, "text": text, "quote": quote, **(attrs or {})},
            source=source,
        )
        self.relate(claim_id, "cites", source_id, source=source, exclusive=False)
        self.relate(claim_id, "supports", rule_id, source=source, exclusive=False)
        return claim_id

    def _open_targets(self, node_id: str, via: str) -> list[str]:
        return [e["id"] for e in self.view("graph").neighbors_of(node_id, via)]

    def claims_for(self, layer: str) -> list[dict]:
        return sorted(
            (
                e
                for e in self.entities.values()
                if e["type"] == "claim" and e["attrs"].get("layer") == layer
            ),
            key=lambda e: e["id"],
        )

    def evidence_path(self, claim_id: str) -> list[dict]:
        path = [self.entities[claim_id]]
        path += [self.entities[i] for i in self._open_targets(claim_id, "cites")]
        path += [self.entities[i] for i in self._open_targets(claim_id, "supports")]
        return path

    def conflicts(self) -> list[tuple[str, str]]:
        return sorted(
            (e["from"], e["to"])
            for e in self.edges.values()
            if e["type"] == "contradicts" and e["valid_to"] is None
        )

    def add_objection(self, target_id: str, text: str, round: int, source: dict) -> str:
        obj_id = self.upsert_entity(
            type="objection",
            name=f"{target_id}|{round}|{text}",
            attrs={"text": text, "round": round, "status": "open", "target": target_id},
            source=source,
        )
        self.relate(obj_id, "objection_on", target_id, source=source, exclusive=False)
        return obj_id

    def resolve_objection(self, objection_id: str, resolution: str, source: dict) -> None:
        obj = self.entities[objection_id]
        self.upsert_entity(
            type="objection",
            name=obj["name"],
            attrs={"status": "resolved", "resolution": resolution},
            source=source,
        )

    def open_objections(self) -> list[dict]:
        return sorted(
            (
                e
                for e in self.entities.values()
                if e["type"] == "objection" and e["attrs"].get("status") == "open"
            ),
            key=lambda e: e["id"],
        )
