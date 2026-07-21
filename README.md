# ShieldAI

**The policy layer between enterprise data and AI agents.**

ShieldAI is a runnable MVP of an enterprise AI security gateway. It exposes
safe MCP tools, applies local policy enforcement before a model sees connector
data, and preserves useful context with deterministic placeholders.

## What the demo proves

1. An AI client calls a ShieldAI MCP tool instead of a connector directly.
2. ShieldAI authenticates a demo employee and authorizes the requested source.
3. A mock Slack connector returns enterprise data only to the gateway.
4. The local policy engine detects protected values and replaces them with
   stable placeholders such as `[PROJECT_1]` and `[PERSON_1]`.
5. The MCP response contains only the transformed text. The original values
   and the mapping never leave the gateway.
6. An audit log records the policy decision without retaining the raw message.

## Architecture

```text
AI client / Codex
      |  MCP tools
      v
ShieldAI MCP server
      |
      +-- identity + authorization
      +-- policy decision
      +-- mock connector adapter
      +-- local sanitizer + placeholder map
      +-- minimal audit event
      v
safe text only -> external model
```

The web dashboard is intentionally a local demonstration surface. It shows the
mapping and optional response rehydration to an authorized human; MCP clients
only receive `safe_context`.

## Run the dashboard

This MVP uses the Python standard library so it can run without downloading
dependencies. Python 3.10+ is enough.

```powershell
cd shieldai
python backend/app.py
```

If Python is not on your PATH, use the bundled Codex runtime:

```powershell
& "C:\Users\liavs\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" backend\app.py
```

Open `http://127.0.0.1:8787`.

## Run the MCP server

The MCP server uses JSON-RPC over stdio and exposes:

- `shieldai_search_slack_messages`
- `shieldai_get_channel_history`
- `shieldai_search_documents`

```powershell
cd shieldai
python backend/mcp_server.py
```

An MCP client configuration can invoke `backend/mcp_server.py`. In this MVP,
the authenticated identity is simulated through `SHIELDAI_DEMO_USER` (default:
`john`). A production deployment would derive it from SSO/OAuth claims and
preserve the source system's per-user authorization.

## Demo scenario

Choose **John / Engineer**, then search Slack for `Falcon`. The source contains
project, employee, location, budget, and infrastructure details. ShieldAI
returns safe context such as:

```text
[PROJECT_1] validation is delayed at [LOCATION_1].
[PERSON_1] requested a review of [AMOUNT_1].
```

Switch to **Maya / Finance** and request the same engineering channel to show a
blocked authorization decision.

## Security boundaries and limitations

- Detection and replacement run locally; no external model is used to classify
  the text in this MVP.
- Regex and dictionaries are strong for known and structured data, but cannot
  guarantee detection of every trade secret written in free text.
- Unknown or high-risk content should be handled with a fail-closed policy in a
  production deployment.
- MCP protects connector data returned to an AI client. It does not by itself
  sanitize text that a user types directly into a third-party chat interface.
- Response rehydration is only safe in a ShieldAI-controlled user interface;
  never send the placeholder map back through MCP to the model.

## Project layout

```text
backend/
  authorization.py   Demo identities and source permissions
  connectors.py      Mock Slack and Drive connector adapters
  gateway.py         Policy enforcement orchestration
  sanitizer.py       Local detection and deterministic placeholders
  mcp_server.py      MCP stdio server
  app.py             Local dashboard/API server
frontend/            Dependency-free dashboard
data/                Runtime audit log directory
tests/               Unit and integration tests
```

