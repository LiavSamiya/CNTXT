"""Identity and authorization boundary for the ShieldAI demonstration."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class User:
    id: str
    name: str
    department: str
    role: str
    allowed_sources: tuple[str, ...]
    allowed_channels: tuple[str, ...]


USERS: dict[str, User] = {
    "john": User(
        id="john",
        name="John Carter",
        department="Engineering",
        role="Engineer",
        allowed_sources=("slack", "drive", "github"),
        allowed_channels=("engineering", "operations"),
    ),
    "maya": User(
        id="maya",
        name="Maya Chen",
        department="Finance",
        role="Finance Analyst",
        allowed_sources=("slack", "drive"),
        allowed_channels=("finance",),
    ),
    "ava": User(
        id="ava",
        name="Ava Robinson",
        department="Security",
        role="Security Administrator",
        allowed_sources=("slack", "drive", "github"),
        allowed_channels=("engineering", "operations", "finance", "security"),
    ),
}


TOOL_SOURCE = {
    "shieldai_search_slack_messages": "slack",
    "shieldai_get_channel_history": "slack",
    "shieldai_search_documents": "drive",
    "shieldai_search_github": "github",
}


def get_user(user_id: str) -> User:
    try:
        return USERS[user_id]
    except KeyError as exc:
        raise PermissionError("Unknown user identity") from exc


def authorize(user: User, tool_name: str, arguments: dict) -> tuple[bool, str]:
    """Return a deterministic authorization decision before data retrieval."""
    source = TOOL_SOURCE.get(tool_name)
    if source is None:
        return False, "Tool is not registered with ShieldAI"
    if source not in user.allowed_sources:
        return False, f"{user.role} is not authorized for the {source} connector"

    if source == "slack":
        channel = str(arguments.get("channel", "engineering")).lower()
        if channel not in user.allowed_channels:
            return False, f"{user.role} is not authorized for #{channel}"

    if source == "drive" and user.department == "Finance":
        # A simple demonstration of resource-sensitive authorization.
        query = str(arguments.get("query", "")).lower()
        if "engineering" in query or "falcon" in query:
            return False, "Finance policy blocks engineering program documents"

    return True, "Authorized by role and resource policy"


def public_users() -> list[dict]:
    """Dashboard-safe identity view; no credentials are ever exposed."""
    return [asdict(user) for user in USERS.values()]
