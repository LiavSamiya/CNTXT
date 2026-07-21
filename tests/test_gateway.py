from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.context_proxy import ContextProxyEngine
from backend.gateway import ShieldAIGateway
from backend.project_memory import ProjectMemoryStore
from backend.sanitizer import Sanitizer
from backend.policies import get_policy


class SanitizerTests(unittest.TestCase):
    def test_repeated_entities_keep_the_same_placeholder(self) -> None:
        sanitizer = Sanitizer(get_policy("defense"))
        sanitized = sanitizer.sanitize("Project Falcon is active. Project Falcon needs review.")
        self.assertEqual(sanitized.count("[PROJECT_1]"), 2)
        self.assertEqual(sanitizer.mapping["[PROJECT_1]"], "Project Falcon")

    def test_card_number_is_replaced_only_when_luhn_valid(self) -> None:
        sanitizer = Sanitizer(get_policy("finance"))
        sanitized = sanitizer.sanitize("Use card 4532 0151 1283 0366 for the payment.")
        self.assertIn("[CREDIT_CARD_1]", sanitized)

    def test_api_key_does_not_leave_the_gateway(self) -> None:
        sanitizer = Sanitizer(get_policy("engineering"))
        sanitized = sanitizer.sanitize("rotate sk-prod-7GtQvU3rL5JmN8pK now")
        self.assertNotIn("sk-prod", sanitized)
        self.assertIn("[API_KEY_1]", sanitized)


class GatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gateway = ShieldAIGateway()

    def test_engineer_receives_sanitized_slack_context(self) -> None:
        result = self.gateway.execute("john", "shieldai_search_slack_messages", {"query": "Falcon", "channel": "engineering"}, include_mapping=False)
        self.assertEqual(result["decision"], "REDACT")
        self.assertIn("[PROJECT_1]", result["safe_context"])
        self.assertNotIn("Project Falcon", result["safe_context"])
        self.assertNotIn("mapping", result)
        self.assertNotIn("raw_context", result)

    def test_finance_role_is_blocked_from_engineering_channel(self) -> None:
        result = self.gateway.execute("maya", "shieldai_search_slack_messages", {"query": "Falcon", "channel": "engineering"})
        self.assertEqual(result["decision"], "BLOCK")
        self.assertEqual(result["safe_context"], "")

    def test_rehydration_is_limited_to_current_request_mapping(self) -> None:
        result = self.gateway.execute("john", "shieldai_search_slack_messages", {"query": "Falcon", "channel": "engineering"}, include_mapping=True)
        self.assertIn("Project Falcon", result["rehydrated_response"])
        self.assertNotIn("[PROJECT_1]", result["rehydrated_response"])
        self.assertIn("Project Falcon", result["raw_context"])

    def test_project_memory_reuses_placeholder_across_gateway_instances(self) -> None:
        with TemporaryDirectory() as directory:
            memory = ProjectMemoryStore(Path(directory) / "memory.db")
            first = ShieldAIGateway(memory=memory).execute(
                "john", "shieldai_search_slack_messages", {"query": "Falcon", "channel": "engineering", "project_id": "falcon"}
            )
            second = ShieldAIGateway(memory=memory).execute(
                "john", "shieldai_search_documents", {"query": "Falcon", "project_id": "falcon"}
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
