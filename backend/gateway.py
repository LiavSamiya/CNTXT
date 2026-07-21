"""ShieldAI's policy enforcement point.

The ordering here is intentional: authenticate -> authorize -> retrieve ->
sanitize -> audit. Sensitive connector data is never returned before the
sanitizer has transformed it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .authorization import authorize, get_user
from .connectors import get_channel_history, search_documents, search_slack_messages
from .policies import get_policy
from .sanitizer import Sanitizer


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "data" / "audit.jsonl"


class ShieldAIGateway:
    def _retrieve(self, tool_name: str, arguments: dict[str, Any]) -> tuple[str, str]:
        if tool_name == "shieldai_search_slack_messages":
            channel = str(arguments.get("channel", "engineering"))
            messages = search_slack_messages(str(arguments.get("query", "")), channel)
            lines = [f"#{item['channel']} | {item['author']}: {item['text']}" for item in messages]
            return "slack", "\n".join(lines) or "No matching Slack messages were found."
        if tool_name == "shieldai_get_channel_history":
            channel = str(arguments.get("channel", "engineering"))
            messages = get_channel_history(channel)
            lines = [f"#{item['channel']} | {item['author']}: {item['text']}" for item in messages]
            return "slack", "\n".join(lines) or "No messages were found in this channel."
        if tool_name == "shieldai_search_documents":
            documents = search_documents(str(arguments.get("query", "")))
            lines = [f"{item['title']}: {item['body']}" for item in documents]
            return "drive", "\n".join(lines) or "No matching documents were found."
        raise ValueError("Unknown ShieldAI MCP tool")

    @staticmethod
    def _safe_llm_demo(safe_context: str) -> str:
        """A local stand-in for an external model; it receives safe text only."""
        project = next((token for token in safe_context.split() if token.startswith("[PROJECT_")), "the program")
        location = next((token for token in safe_context.split() if token.startswith("[LOCATION_")), "the test site")
        amount = next((token for token in safe_context.split() if token.startswith("[AMOUNT_")), "the approved budget")
        return f"Summary: {project} is delayed by integration validation at {location}. The team should complete a restricted review before acting on {amount}."

    @staticmethod
    def _audit(event: dict[str, Any]) -> None:
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def execute(
        self,
        user_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        policy_id: str = "defense",
        include_mapping: bool = False,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        user = get_user(user_id)
        allowed, reason = authorize(user, tool_name, arguments)
        policy = get_policy(policy_id)

        base_event = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "user": user.name,
            "department": user.department,
            "role": user.role,
            "tool": tool_name,
            "policy": policy["name"],
        }

        if not allowed:
            event = {**base_event, "decision": "BLOCK", "reason": reason, "entities_hidden": 0, "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
            self._audit(event)
            return {"decision": "BLOCK", "reason": reason, "safe_context": "", "entities": [], "audit": event}

        source, raw_context = self._retrieve(tool_name, arguments)
        sanitizer = Sanitizer(policy)
        safe_context = sanitizer.sanitize(raw_context)
        event = {
            **base_event,
            "source": source,
            "decision": "REDACT" if sanitizer.entities else "ALLOW",
            "reason": reason,
            "entities_hidden": len(sanitizer.entities),
            "entity_types": sorted({entity["entity_type"] for entity in sanitizer.entities}),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
        self._audit(event)
        response = {"decision": event["decision"], "reason": reason, "safe_context": safe_context, "entities": sanitizer.entities, "audit": event}
        if include_mapping:
            # The locally hosted dashboard may render raw context to an
            # authorized human. This field is never returned through MCP or
            # written into an audit event.
            response["raw_context"] = raw_context
            llm_response = self._safe_llm_demo(safe_context)
            response["mapping"] = sanitizer.mapping
            response["demo_llm_response"] = llm_response
            response["rehydrated_response"] = sanitizer.rehydrate(llm_response)
        return response

    def recent_audit_events(self, limit: int = 20) -> list[dict]:
        if not AUDIT_PATH.exists():
            return []
        lines = AUDIT_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(line) for line in reversed(lines) if line.strip()]
