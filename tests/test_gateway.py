from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.context_proxy import ContextProxyEngine
from backend.gateway import ShieldAIGateway
from backend.project_memory import ProjectMemoryStore
from backend.sanitizer import Sanitizer
from backend.policies import policy_for_sanitizer, load_policy


class SanitizerTests(unittest.TestCase):
    def _policy(self, **overrides):
        base = load_policy()
        base.update(overrides)
        return policy_for_sanitizer(base)

    def test_repeated_entities_keep_the_same_placeholder(self) -> None:
        sanitizer = Sanitizer(self._policy())
        sanitized = sanitizer.sanitize("Project Falcon is active. Project Falcon needs review.")
        self.assertEqual(sanitized.count("[PROJECT_1]"), 2)
        self.assertEqual(sanitizer.mapping["[PROJECT_1]"], "Project Falcon")

    def test_card_number_is_replaced_only_when_luhn_valid(self) -> None:
        sanitizer = Sanitizer(self._policy())
        sanitized = sanitizer.sanitize("Use card 4532 0151 1283 0366 for the payment.")
        self.assertIn("[CREDIT_CARD_1]", sanitized)

    def test_api_key_does_not_leave_the_gateway(self) -> None:
        sanitizer = Sanitizer(self._policy())
        sanitized = sanitizer.sanitize("rotate sk-prod-7GtQvU3rL5JmN8pK now")
        self.assertNotIn("sk-prod", sanitized)
        self.assertIn("[API_KEY_1]", sanitized)

    def test_disabled_category_skips_detection(self) -> None:
        # Disable money category
        pol = self._policy(hide_categories=["projects", "people", "api_keys"])
        sanitizer = Sanitizer(pol)
        sanitized = sanitizer.sanitize("Budget is $15,000,000 for Project Falcon.")
        self.assertIn("$15,000,000", sanitized)  # money NOT hidden
        self.assertIn("[PROJECT_1]", sanitized)   # project IS hidden


class GatewayTests(unittest.TestCase):
    def test_context_is_sanitized_without_auth(self) -> None:
        gw = ShieldAIGateway()
        result = gw.execute(
            tool_name="shieldai_search_slack_messages",
            arguments={"query": "Falcon", "channel": "engineering"},
            include_mapping=False,
        )
        self.assertEqual(result["decision"], "REDACT")
        self.assertIn("[PROJECT_1]", result["safe_context"])
        self.assertNotIn("Project Falcon", result["safe_context"])
        self.assertNotIn("mapping", result)
        self.assertNotIn("raw_context", result)

    def test_mapping_returned_when_requested(self) -> None:
        gw = ShieldAIGateway()
        result = gw.execute(
            tool_name="shieldai_search_slack_messages",
            arguments={"query": "Falcon", "channel": "engineering"},
            include_mapping=True,
        )
        self.assertIn("Project Falcon", result["rehydrated_response"])
        self.assertNotIn("[PROJECT_1]", result["rehydrated_response"])
        self.assertIn("Project Falcon", result["raw_context"])

    def test_project_memory_reuses_placeholder_across_gateway_instances(self) -> None:
        with TemporaryDirectory() as directory:
            memory = ProjectMemoryStore(Path(directory) / "memory.db")
            first = ShieldAIGateway(memory=memory).execute(
                tool_name="shieldai_search_slack_messages",
                arguments={"query": "Falcon", "channel": "engineering", "project_id": "falcon"},
            )
            second = ShieldAIGateway(memory=memory).execute(
                tool_name="shieldai_search_documents",
                arguments={"query": "Falcon", "project_id": "falcon"},
            )
            self.assertIn("[PROJECT_1]", first["safe_context"])
            self.assertIn("[PROJECT_1]", second["safe_context"])
            self.assertEqual(memory.count("falcon"), 8)


class ContextProxyTests(unittest.TestCase):
    def test_proxy_routes_to_scoped_slack_tool(self) -> None:
        source, upstream_tool, raw_context = ContextProxyEngine().retrieve(
            "shieldai_search_slack_messages", {"query": "Falcon", "channel": "engineering"}
        )
        self.assertEqual(source, "slack")
        self.assertEqual(upstream_tool, "search_messages")
        self.assertIn("Project Falcon", raw_context)


if __name__ == "__main__":
    unittest.main()
