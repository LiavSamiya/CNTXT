"""Mock enterprise connector adapters.

They stand in for Slack/Drive APIs in the demo. In production, adapters would
use the provider's OAuth token and enforce its source-side ACLs as well.
"""

from __future__ import annotations

import json
from pathlib import Path

SLACK_MESSAGES = [
    {
        "channel": "engineering",
        "author": "John Smith",
        "timestamp": "2026-07-21T09:12:00Z",
        "text": "Project Falcon validation is delayed at North Ridge Test Facility. Aegis-9 telemetry is inconsistent after the latest integration run.",
    },
    {
        "channel": "engineering",
        "author": "Rina Patel",
        "timestamp": "2026-07-21T09:24:00Z",
        "text": "Acme Defense approved an additional $15,000,000 for Project Falcon. Please keep the Orion Database migration restricted to the program team.",
    },
    {
        "channel": "finance",
        "author": "Maya Chen",
        "timestamp": "2026-07-21T08:48:00Z",
        "text": "Helix Capital asked for a reconciliation of account 4111-2900-7788 and invoice INV-2048.",
    },
    {
        "channel": "operations",
        "author": "Ava Robinson",
        "timestamp": "2026-07-21T10:01:00Z",
        "text": "Vendor access token sk-prod-7GtQvU3rL5JmN8pK should be rotated before tomorrow's deployment.",
    },
]


DOCUMENTS = [
    {
        "id": "eng-falcon-status",
        "title": "Project Falcon weekly engineering status",
        "body": "Project Falcon remains in integration testing. John Smith is coordinating the Aegis-9 validation at North Ridge Test Facility. The program budget is $15,000,000.",
    },
    {
        "id": "finance-q3",
        "title": "Helix Capital Q3 reconciliation",
        "body": "Helix Capital requested confirmation for account 4111-2900-7788. Payment reference is 4532 0151 1283 0366.",
    },
]


# Keep the demo corpus as editable JSON data rather than code. The inline
# defaults above make this module still importable if an example dataset was
# intentionally removed.
DATA_DIR = Path(__file__).resolve().parents[1] / "fake_company_data"
if (DATA_DIR / "slack_messages.json").is_file():
    SLACK_MESSAGES = json.loads((DATA_DIR / "slack_messages.json").read_text(encoding="utf-8"))
if (DATA_DIR / "documents.json").is_file():
    DOCUMENTS = json.loads((DATA_DIR / "documents.json").read_text(encoding="utf-8"))


def search_slack_messages(query: str, channel: str = "engineering") -> list[dict]:
    terms = [term.casefold() for term in query.split() if term.strip()]
    results = []
    for message in SLACK_MESSAGES:
        if message["channel"].casefold() != channel.casefold():
            continue
        haystack = f"{message['author']} {message['text']}".casefold()
        if not terms or any(term in haystack for term in terms):
            results.append(message)
    return results


def get_channel_history(channel: str = "engineering") -> list[dict]:
    return [message for message in SLACK_MESSAGES if message["channel"].casefold() == channel.casefold()]


def search_documents(query: str) -> list[dict]:
    terms = [term.casefold() for term in query.split() if term.strip()]
    return [
        document
        for document in DOCUMENTS
        if not terms or any(term in f"{document['title']} {document['body']}".casefold() for term in terms)
    ]
