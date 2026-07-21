"""Context Proxy Engine — routes ShieldAI tools to upstream MCP connectors.

ShieldAI presents its own protected tools to AI clients.  Each adapter
represents a connection to an upstream MCP server (Slack, GitHub, Drive).
The proxy retrieves raw context from the upstream source; the gateway then
sanitizes it before it reaches the LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .connectors import (
    get_channel_history,
    search_documents,
    search_slack_messages,
    search_github,
    format_github_results,
)


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
            raise ValueError(f"Unknown Slack tool: {tool_name}")
        return "\n".join(
            f"#{item['channel']} | {item['author']}: {item['text']}"
            for item in messages
        ) or "No matching Slack messages."


@dataclass
class DriveMCPAdapter:
    name: str = "Google Drive MCP"

    def call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        if tool_name != "search_documents":
            raise ValueError(f"Unknown Drive tool: {tool_name}")
        documents = search_documents(str(arguments.get("query", "")))
        return "\n".join(
            f"{doc['title']}: {doc['body']}" for doc in documents
        ) or "No matching documents."


@dataclass
class GitHubMCPAdapter:
    name: str = "GitHub MCP"

    def call(self, tool_name: str, arguments: dict[str, Any]) -> str:
        if tool_name != "search_repository":
            raise ValueError(f"Unknown GitHub tool: {tool_name}")
        query = str(arguments.get("query", ""))
        repo = str(arguments.get("repo", ""))
        results = search_github(query, repo)
        return format_github_results(results)


class ContextProxyEngine:
    """Routes ShieldAI tools to upstream MCP connectors."""

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
            raise ValueError("Unknown ShieldAI tool") from exc
        connector = self.connectors[connector_id]
        return connector_id, upstream_tool, connector.call(upstream_tool, arguments)
