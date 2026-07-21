"""Minimal ShieldAI MCP server using JSON-RPC messages over stdio.

The server intentionally exposes *ShieldAI* tools rather than raw upstream
Slack/Drive tools. Its results contain only sanitized text.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# Support the direct stdio command documented in the README.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.gateway import ShieldAIGateway


TOOLS = [
    {
        "name": "shieldai_search_slack_messages",
        "description": "Search Slack through ShieldAI policy enforcement. The result is always sanitized.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "channel": {"type": "string", "default": "engineering"}, "project_id": {"type": "string", "default": "demo-falcon"}},
            "required": ["query"],
        },
    },
    {
        "name": "shieldai_get_channel_history",
        "description": "Read a permitted Slack channel through ShieldAI policy enforcement.",
        "inputSchema": {"type": "object", "properties": {"channel": {"type": "string", "default": "engineering"}, "project_id": {"type": "string", "default": "demo-falcon"}}},
    },
    {
        "name": "shieldai_search_documents",
        "description": "Search Drive-like documents through ShieldAI policy enforcement.",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "project_id": {"type": "string", "default": "demo-falcon"}}, "required": ["query"]},
    },
    {
        "name": "shieldai_search_github",
        "description": "Search GitHub through ShieldAI policy enforcement. The demo adapter returns no raw repository context.",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "project_id": {"type": "string", "default": "demo-falcon"}}, "required": ["query"]},
    },
]


def _result(request_id: Any, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(message: dict, gateway: ShieldAIGateway, user_id: str | None = None) -> dict | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return _result(request_id, {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "shieldai-gateway", "version": "0.1.0"}})
    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        authenticated_user = user_id or os.getenv("SHIELDAI_DEMO_USER", "john")
        try:
            response = gateway.execute(authenticated_user, tool_name, arguments, include_mapping=False)
        except (PermissionError, ValueError) as exc:
            return _error(request_id, -32001, str(exc))
        if response["decision"] == "BLOCK":
            return _result(request_id, {"content": [{"type": "text", "text": f"ShieldAI blocked this request: {response['reason']}"}], "isError": True})
        return _result(request_id, {"content": [{"type": "text", "text": response["safe_context"]}], "structuredContent": {"decision": response["decision"], "entitiesHidden": response["audit"]["entities_hidden"]}})
    return _error(request_id, -32601, f"Method not found: {method}")


def main() -> None:
    gateway = ShieldAIGateway()
    for raw_message in sys.stdin:
        try:
            response = handle(json.loads(raw_message), gateway)
            if response is not None:
                print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            print(json.dumps(_error(None, -32700, "Parse error")), flush=True)
        except Exception as exc:  # keep the protocol process alive for the client
            print(json.dumps(_error(None, -32603, f"Internal error: {exc}")), flush=True)


if __name__ == "__main__":
    main()
