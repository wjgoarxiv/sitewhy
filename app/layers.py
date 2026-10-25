"""Curated rule layers (federal, ISO/RTO) and county primary-source lists."""

from pathlib import Path

import yaml

from app import applicability
from app.applicability import Project

LAYERS_DIR = Path(__file__).resolve().parent.parent / "data/layers"


def load_rules() -> list[dict]:
    return yaml.safe_load((LAYERS_DIR / "rules.yaml").read_text())


def load_county_sources() -> dict[str, list[dict]]:
    return yaml.safe_load((LAYERS_DIR / "county_sources.yaml").read_text())


def evaluate_rule(rule: dict, project: Project, site: dict) -> dict | None:
    """Run the rule's deterministic check; None when the site is outside its scope."""
    if any(site.get(k) != v for k, v in rule["scope"].items()):
        return None
    check = rule["check"]
    if isinstance(check, str):
        return getattr(applicability, check)(project)
    return applicability.mw_threshold(
        project, check["mw_threshold"], check["label"], inclusive=check.get("inclusive", True)
    )
