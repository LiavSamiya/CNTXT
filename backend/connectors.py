"""Upstream MCP connector adapters.

Each adapter provides the interface between ShieldAI and an upstream data
source.  In this release the adapters load company data from local JSON
files; swapping in a real Slack/Drive/GitHub OAuth client requires only
implementing the same `call()` signature.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "fake_company_data"


def _load_json(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


SLACK_MESSAGES: list[dict] = _load_json("slack_messages.json")
DOCUMENTS: list[dict] = _load_json("documents.json")
GITHUB_DATA: list[dict] = _load_json("github_data.json")


# ── Slack ────────────────────────────────────────────────────────────────

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
    return [m for m in SLACK_MESSAGES if m["channel"].casefold() == channel.casefold()]


# ── Google Drive ─────────────────────────────────────────────────────────

def search_documents(query: str) -> list[dict]:
    terms = [term.casefold() for term in query.split() if term.strip()]
    return [
        doc for doc in DOCUMENTS
        if not terms or any(term in f"{doc['title']} {doc['body']}".casefold() for term in terms)
    ]


# ── GitHub ───────────────────────────────────────────────────────────────

def search_github(query: str, repo: str = "") -> list[dict]:
    terms = [term.casefold() for term in query.split() if term.strip()]
    results = []
    for item in GITHUB_DATA:
        if repo and item.get("repo", "").casefold() != repo.casefold():
            continue
        searchable = " ".join(str(v) for v in item.values()).casefold()
        if not terms or any(term in searchable for term in terms):
            results.append(item)
    return results


def format_github_results(items: list[dict]) -> str:
    if not items:
        return "No matching GitHub results."
    lines = []
    for item in items:
        item_type = item.get("type", "unknown")
        repo = item.get("repo", "")
        if item_type == "pull_request":
            lines.append(f"[PR #{item['number']}] {repo}: {item['title']}")
            lines.append(f"  Author: {item['author']} | Status: {item['status']}")
            lines.append(f"  {item['body']}")
        elif item_type == "issue":
            lines.append(f"[Issue #{item['number']}] {repo}: {item['title']}")
            lines.append(f"  Author: {item['author']} | Status: {item['status']}")
            lines.append(f"  {item['body']}")
        elif item_type == "commit":
            lines.append(f"[Commit {item['sha']}] {repo}")
            lines.append(f"  Author: {item['author']}")
            lines.append(f"  {item['message']}")
            if item.get("files_changed"):
                lines.append(f"  Files: {', '.join(item['files_changed'])}")
        lines.append("")
    return "\n".join(lines).strip()
