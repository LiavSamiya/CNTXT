"""Declarative security policies. These are interpreted locally by the gateway."""

from __future__ import annotations


POLICIES: dict[str, dict] = {
    "defense": {
        "id": "defense",
        "name": "Defense Program Protection",
        "description": "Protect programs, personnel, locations, facilities, budgets, and systems.",
        "mode": "redact",
        "protected_terms": {
            "Project Falcon": "PROJECT",
            "Acme Defense": "COMPANY",
            "Lockheed": "COMPANY",
            "John Smith": "PERSON",
            "Rina Patel": "PERSON",
            "North Ridge Test Facility": "LOCATION",
            "Aegis-9": "INTERNAL_SYSTEM",
            "Orion Database": "DATABASE",
        },
    },
    "finance": {
        "id": "finance",
        "name": "Financial Data Protection",
        "description": "Protect customers, account data, payment identifiers, and balances.",
        "mode": "redact",
        "protected_terms": {
            "Helix Capital": "COMPANY",
            "Meridian Holdings": "CUSTOMER",
            "LedgerCore": "INTERNAL_SYSTEM",
        },
    },
    "engineering": {
        "id": "engineering",
        "name": "Engineering Secrets Protection",
        "description": "Protect source systems, repositories, infrastructure, and access secrets.",
        "mode": "redact",
        "protected_terms": {
            "Aegis-9": "INTERNAL_SYSTEM",
            "Orion Database": "DATABASE",
            "Project Falcon": "PROJECT",
        },
    },
}


def get_policy(policy_id: str) -> dict:
    return POLICIES.get(policy_id, POLICIES["defense"])


def public_policies() -> list[dict]:
    return [
        {"id": policy["id"], "name": policy["name"], "description": policy["description"]}
        for policy in POLICIES.values()
    ]
