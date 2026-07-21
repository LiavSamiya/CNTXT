"""Context Proxy Engine and mock upstream MCP connector adapters.

ShieldAI presents its own protected tools to AI clients. These adapters model
the private hop to Slack, GitHub, and Drive MCP servers. Replacing a mock
adapter with a real OAuth/MCP client does not change policy enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .connectors import get_channel_history, search_documents, search_slack_messages


class UpstreamMCPConnector(Protocol):
    name: str

    def call(self, tool_name: str, arguments: dict[str, Any]) -> str: ...


@dataclass
class SlackMCPAdapter:
    name: str = "Slack MCP"

    def call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        channel = str(arguments.get("channel", "engineering"))
        if tool_name == "search_messages":
            messages = search_slack_messages(str(arguments.get("query", "")), channel)
        elif tool_name == "get_channel_history":
            messages = get_channel_history(channel)
        else:
            raise ValueError(f"Slack MCP tool is not allowed: {tool_name}")
        return "\n".join(f"#{item['channel']} | {item['author']}: {item['text']}" for item in messages) or "No matching Slack messages were found."


@dataclass
class DriveMCPAdapter:
    name: str = "Google Drive MCP"

    def call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        if tool_name != "search_documents":
            raise ValueError(f"Drive MCP tool is not allowed: {tool_name}")
        documents = search_documents(str(arguments.get("query", "")))
        return "\n".join(f"{item['title']}: {item['body']}" for item in documents) or "No matching documents were found."


@dataclass
class GitHubMCPAdapter:
    """Reserved adapter boundary for the real GitHub MCP implementation."""

    name: str = "GitHub MCP"

    def call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        if tool_name != "search_repository":
            raise ValueError(f"GitHub MCP tool is not allowed: {tool_name}")
        return "GitHub mock adapter is policy-ready. Connect a repository OAuth token to retrieve protected code context."


class ContextProxyEngine:
    """Routes protected ShieldAI tools to narrowly scoped upstream MCP calls."""

    ROUTES = {
        "shieldai_search_slack_messages": ("slack", "search_messages"),
        "shieldai_get_channel_history": ("slack", "get_channel_history"),
        "shieldai_search_documents": ("drive", "search_documents"),
        "shieldai_search_github": ("github", "search_repository"),
    }

    def __init__(self) -> None:
        self.connectors: dict[str, UpstreamMCPConnector] = {
            "slack": SlackMCPAdapter(),
            "drive": DriveMCPAdapter(),
            "github": GitHubMCPAdapter(),
        }

    def retrieve(self, shieldai_tool: str, arguments: dict[str, Any]) -> tuple[str, str, str]:
        try:
            connector_id, upstream_tool = self.ROUTES[shieldai_tool]
        except KeyError as exc:
            raise ValueError("Unknown ShieldAI MCP tool") from exc
        connector = self.connectors[connector_id]
        return connector_id, upstream_tool, connector.call(upstream_tool, arguments)

