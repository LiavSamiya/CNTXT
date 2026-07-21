"""Editable company policy for the ShieldAI Context Firewall.

The policy defines *what* information is sensitive — not *who* can access it.
A company uploads its policy once, and ShieldAI enforces it on every MCP
response before context reaches the LLM.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "data" / "policy.json"

# ── Category definitions ────────────────────────────────────────────────
# Each category groups a set of regex-detected entity types.  The UI
# renders these as checkboxes; enabled categories activate their detectors.
CATEGORIES: list[dict[str, Any]] = [
    {"id": "projects",  "label": "Project Names",   "entity_types": ["PROJECT"]},
    {"id": "people",    "label": "Employee Names",   "entity_types": ["PERSON"]},
    {"id": "money",     "label": "Budget / Money",   "entity_types": ["AMOUNT", "CREDIT_CARD"]},
    {"id": "api_keys",  "label": "API Keys / Tokens","entity_types": ["API_KEY", "TOKEN"]},
    {"id": "locations", "label": "Locations / GPS",  "entity_types": ["LOCATION"]},
    {"id": "databases", "label": "Databases / Servers","entity_types": ["DATABASE", "SERVER", "INTERNAL_SYSTEM"]},
    {"id": "customers", "label": "Customers",        "entity_types": ["CUSTOMER", "COMPANY"]},
    {"id": "contact",   "label": "Email / Phone",    "entity_types": ["EMAIL", "PHONE"]},
]

DEFAULT_POLICY: dict[str, Any] = {
    "company_name": "Acme Defense",
    "hide_categories": [cat["id"] for cat in CATEGORIES],   # all enabled
    "custom_dictionary": {
        "Project Falcon": "PROJECT",
        "Acme Defense": "COMPANY",
        "Lockheed": "COMPANY",
        "Helix Capital": "CUSTOMER",
        "Customer Alpha": "CUSTOMER",
        "John Smith": "PERSON",
        "Rina Patel": "PERSON",
        "Daniel Reeves": "PERSON",
        "Maya Chen": "PERSON",
        "Ava Robinson": "PERSON",
        "Sarah Miller": "PERSON",
        "North Ridge Test Facility": "LOCATION",
        "Aegis-9": "INTERNAL_SYSTEM",
        "Orion Database": "DATABASE",
        "eagle-prod-03": "SERVER",
        "falcon-core": "REPOSITORY",
        "falcon-infra": "REPOSITORY",
    },
}


def _ensure_path() -> None:
    POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_policy() -> dict[str, Any]:
    """Return the current company policy, creating the default if missing."""
    _ensure_path()
    if POLICY_PATH.is_file():
        try:
            return json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    save_policy(DEFAULT_POLICY)
    return dict(DEFAULT_POLICY)


def save_policy(policy: dict[str, Any]) -> None:
    _ensure_path()
    POLICY_PATH.write_text(json.dumps(policy, indent=2, ensure_ascii=False), encoding="utf-8")


def active_entity_types(policy: dict[str, Any]) -> set[str]:
    """Return entity types enabled by the current category selection."""
    enabled = set(policy.get("hide_categories", []))
    types: set[str] = set()
    for cat in CATEGORIES:
        if cat["id"] in enabled:
            types.update(cat["entity_types"])
    return types


def policy_for_sanitizer(policy: dict[str, Any]) -> dict:
    """Build the dict expected by Sanitizer (protected_terms + active types)."""
    return {
        "name": policy.get("company_name", "Company Policy"),
        "protected_terms": dict(policy.get("custom_dictionary", {})),
        "active_entity_types": active_entity_types(policy),
    }


def public_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """Policy view safe for the dashboard UI."""
    return {
        "company_name": policy.get("company_name", ""),
        "hide_categories": policy.get("hide_categories", []),
        "custom_dictionary": policy.get("custom_dictionary", {}),
        "available_categories": CATEGORIES,
    }
