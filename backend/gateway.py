"""ShieldAI Context Firewall — the core enforcement point.

The ordering is: retrieve → sanitize → audit.
There is no authentication or authorization step — ShieldAI protects
*what* the LLM sees, not *who* can access the data.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .context_proxy import ContextProxyEngine
from .policies import load_policy, policy_for_sanitizer
from .project_memory import ProjectMemoryStore
from .sanitizer import Sanitizer


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "data" / "audit.jsonl"


class ShieldAIGateway:
    def __init__(self, proxy: ContextProxyEngine | None = None, memory: ProjectMemoryStore | None = None) -> None:
        self.proxy = proxy or ContextProxyEngine()
        self.memory = memory or ProjectMemoryStore()

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
        tool_name: str,
        arguments: dict[str, Any],
        policy: dict | None = None,
        include_mapping: bool = False,
    ) -> dict[str, Any]:
        source, upstream_tool, raw_context = self.proxy.retrieve(tool_name, arguments)
        return self.protect_text(
            raw_context,
            project_id=str(arguments.get("project_id", "demo-falcon")),
            source=source,
            upstream_tool=upstream_tool,
            tool_name=tool_name,
            policy=policy,
            include_mapping=include_mapping,
        )

    def protect_text(
        self,
        raw_context: str,
        *,
        project_id: str,
        source: str,
        upstream_tool: str,
        tool_name: str = "shieldai_protect_local_document",
        policy: dict | None = None,
        include_mapping: bool = False,
        audit_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apply the same local enforcement path to already-retrieved text."""
        started = time.perf_counter()
        current_policy = policy or load_policy()
        sanitizer_policy = policy_for_sanitizer(current_policy)
        sanitizer = Sanitizer(sanitizer_policy, self.memory.load(project_id))
        safe_context = sanitizer.sanitize(raw_context)
        self.memory.remember(project_id, sanitizer.mapping)

        event = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tool": tool_name,
            "policy": sanitizer_policy["name"],
            "project_id": project_id,
            "source": source,
            "upstream_tool": upstream_tool,
            "decision": "REDACT" if sanitizer.entities else "PASS",
            "entities_hidden": len(sanitizer.entities),
            "entity_types": sorted({entity["entity_type"] for entity in sanitizer.entities}),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
        if audit_metadata:
            event.update(audit_metadata)
        self._audit(event)

        response: dict[str, Any] = {
            "decision": event["decision"],
            "safe_context": safe_context,
            "entities": sanitizer.entities,
            "audit": event,
        }
        if include_mapping:
            response["raw_context"] = raw_context
            llm_response = self._safe_llm_demo(safe_context)
            response["mapping"] = sanitizer.mapping
            response["project_memory_entries"] = self.memory.count(project_id)
            response["demo_llm_response"] = llm_response
            response["rehydrated_response"] = sanitizer.rehydrate(llm_response)
        return response

    def recent_audit_events(self, limit: int = 20) -> list[dict]:
        if not AUDIT_PATH.exists():
            return []
        lines = AUDIT_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(line) for line in reversed(lines) if line.strip()]
