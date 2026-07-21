# ShieldAI

**The policy layer between enterprise data and AI agents.**

ShieldAI is a runnable MVP of an enterprise AI security gateway. It exposes
safe MCP tools, applies local policy enforcement before a model sees connector
data, and preserves useful context with deterministic placeholders.

## What the demo proves

1. An AI client calls a ShieldAI MCP tool instead of a connector directly.
2. A connector returns enterprise data only to the gateway.
3. The local policy engine detects protected values and replaces them with
   stable placeholders such as `[PROJECT_1]` and `[PERSON_1]`.
4. The MCP response contains only the transformed text. The original values
   and the mapping never leave the gateway.
5. An audit log records the policy decision without retaining the raw message.

## Architecture

```text
ChatGPT / Codex / Claude Desktop
      |  localhost MCP client
      v
ShieldAI Desktop (Electron)
      |
Local MCP server: http://127.0.0.1:8765/mcp
      |
Context Proxy Engine
      +-- Slack MCP adapter
      +-- GitHub MCP adapter
      +-- Drive MCP adapter
      |
Policy enforcement + deterministic placeholder engine
      |
Project Memory Store (local SQLite)
      v
safe text only -> AI client / external model
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

## Run the local MCP HTTP endpoint

The Desktop architecture exposes a local JSON-RPC MCP endpoint at port 8765:

```powershell
cd shieldai
python backend/mcp_http.py
```

Health check: `http://127.0.0.1:8765/health`  
MCP endpoint: `http://127.0.0.1:8765/mcp`

## Connect a real Google Drive (optional)

ShieldAI uses a local, read-only OAuth connection. It never returns a Drive
document to an MCP client before the Gateway has sanitized it.

1. In Google Cloud Console, enable the Google Drive API and create a
   **Desktop app** OAuth client.
2. Download its JSON file and save it locally as
   `secrets/google-oauth-client.json`. This directory is ignored by Git.
3. Restart the dashboard, click **Connect Google Drive**, then approve the
   read-only Google consent screen in your browser.

Choose **Google Drive — Search Documents** in the dashboard or use
`shieldai_search_documents` over MCP. Google Docs and text-based files are
read locally; other file formats remain metadata-only until a local converter
such as MarkItDown is added.

## Run with Docker (isolated from VooDo)

ShieldAI now has its own Docker Compose project, bridge network
(`shieldai_net`), containers (`shieldai-dashboard`, `shieldai-mcp`) and
persisted local data volume (`shieldai_data`). It does not reuse any VooDo
container, network, port, or volume.

```powershell
cd shieldai
docker compose up --build -d
docker compose ps
```

Open the local dashboard at `http://127.0.0.1:18787` and configure an MCP
client to call `http://127.0.0.1:18765/mcp`. Both host ports are bound to
`127.0.0.1`, so other devices cannot access the raw-context gateway.

To stop ShieldAI without touching VooDo:

```powershell
docker compose down
```

## Run the stdio MCP server

The MCP server uses JSON-RPC over stdio and exposes:

- `shieldai_search_slack_messages`
- `shieldai_get_channel_history`
- `shieldai_search_documents`
- `shieldai_search_github`

```powershell
cd shieldai
python backend/mcp_server.py
```

An MCP client configuration can invoke `backend/mcp_server.py`. This MVP
enforces data-transformation policy but does not yet implement enterprise SSO
or per-user authorization. A production deployment should derive identity from
SSO/OAuth claims and preserve the source system's per-user authorization.

## Run ShieldAI Desktop

The optional Electron shell starts both local services and opens the dashboard:

```powershell
cd shieldai\desktop
npm install
npm start
```

See `desktop/README.md` for the Windows Python setting.

## Demo scenario

Search Slack for `Falcon`. The source contains project, employee, location,
budget, and infrastructure details. ShieldAI returns safe context such as:

```text
[PROJECT_1] validation is delayed at [LOCATION_1].
[PERSON_1] requested a review of [AMOUNT_1].
```

For a policy demonstration, disable a category or add a custom dictionary term,
run the same query again, and compare the safe context.

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
- The localhost HTTP endpoint works only with MCP clients that can connect to
  local servers. Cloud-only clients cannot reach `127.0.0.1`; use the stdio
  transport or a secured remote deployment for those clients.

## Project layout

```text
backend/
  connectors.py      Fake enterprise datasets used by mock adapters
  context_proxy.py   Routes protected calls to upstream MCP adapters
  google_drive.py    Optional local, read-only Google Drive OAuth connector
  gateway.py         Policy enforcement orchestration
  project_memory.py  Local SQLite placeholder continuity per project
  sanitizer.py       Local detection and deterministic placeholders
  mcp_server.py      MCP stdio server
  mcp_http.py        Localhost MCP HTTP server on port 8765
  app.py             Local dashboard/API server
frontend/            Dependency-free dashboard
desktop/             Optional Electron local desktop shell
data/                Runtime audit log directory
tests/               Unit and integration tests
```
