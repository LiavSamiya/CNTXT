"""Local web dashboard and API for the ShieldAI Context Firewall."""

from __future__ import annotations

import json
import mimetypes
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

# `python backend/app.py` places backend/ rather than the project root on
# sys.path. Add the root so the package imports below work from the README.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.gateway import ShieldAIGateway
from backend.policies import load_policy, save_policy, public_policy
from backend.document_converter import DocumentConversionError, LocalDocumentConverter


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
gateway = ShieldAIGateway()
document_converter = LocalDocumentConverter()


class ShieldAIHandler(BaseHTTPRequestHandler):
    server_version = "ShieldAI/0.1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _json(self, data: dict | list, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 100_000:
            raise ValueError("Request payload is too large")
        payload = self.rfile.read(length).decode("utf-8")
        return json.loads(payload or "{}")

    def _binary_body(self, limit: int) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid upload length") from exc
        if length <= 0:
            raise ValueError("Select a non-empty file")
        if length > limit:
            raise ValueError("Files larger than 10 MB are not accepted")
        payload = self.rfile.read(length)
        if len(payload) != length:
            raise ValueError("The local upload was incomplete")
        return payload

    def _serve_static(self, path: str) -> None:
        requested = "index.html" if path in ("", "/") else path.lstrip("/")
        candidate = (FRONTEND / requested).resolve()
        if FRONTEND not in candidate.parents and candidate != FRONTEND:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(candidate.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:  # noqa: N802
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        if path == "/api/policy":
            self._json(public_policy(load_policy()))
            return
        if path == "/api/connectors":
            recent_events = gateway.recent_audit_events(50)
            proxy_status = dict(zip(
                ("slack", "drive", "github"),
                gateway.proxy.connector_status(),
                strict=True,
            ))
            defaults = {
                "slack": {"name": "Slack MCP", "tools": 2, "last_request": "Slack.search_messages()", "data_processed": 24},
                "github": {"name": "GitHub MCP", "tools": 1, "last_request": "GitHub.search_repository()", "data_processed": 18},
                "drive": {"name": "Google Drive MCP", "tools": 1, "last_request": "Drive.search_documents()", "data_processed": 12},
            }
            connectors = []
            for source, details in defaults.items():
                source_events = [event for event in recent_events if event.get("source") == source]
                latest = source_events[0] if source_events else None
                upstream = proxy_status[source]
                connectors.append({
                    **details,
                    "id": source,
                    "status": upstream["status"],
                    "detail": upstream.get("detail", "Mock connector data for the local demo."),
                    "connected": bool(upstream.get("connected", False)),
                    "entities_protected": sum(int(event.get("entities_hidden", 0)) for event in source_events) or details["data_processed"],
                    "last_request": latest.get("upstream_tool", details["last_request"]) if latest else details["last_request"],
                    "last_seen": latest.get("timestamp") if latest else "Ready for requests",
                })
            self._json(connectors)
            return
        if path == "/api/logs":
            self._json(gateway.recent_audit_events())
            return
        if path == "/api/memory":
            project_id = parse_qs(parsed_url.query).get("project_id", ["demo-falcon"])[0]
            entries = gateway.memory.load(project_id)
            self._json({
                "project_id": project_id,
                "entries": [
                    {
                        "entity_type": entry.entity_type,
                        "original_value": entry.original_value,
                        "placeholder": entry.placeholder,
                    }
                    for entry in entries
                ],
            })
            return
        if path == "/api/overview":
            events = gateway.recent_audit_events(500)
            self._json({
                "proxy_status": "Running",
                "mcp_endpoint": "http://127.0.0.1:8765/mcp",
                "requests_protected": len(events),
                "entities_transformed": sum(int(event.get("entities_hidden", 0)) for event in events),
                "active_policies": len(load_policy().get("hide_categories", [])),
                "recent_events": events[:5],
            })
            return
        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path == "/api/policy":
            try:
                payload = self._body()
                current = load_policy()
                if "hide_categories" in payload:
                    current["hide_categories"] = list(payload["hide_categories"])
                if "custom_dictionary" in payload:
                    current["custom_dictionary"] = dict(payload["custom_dictionary"])
                if "company_name" in payload:
                    current["company_name"] = str(payload["company_name"])
                save_policy(current)
                self._json(public_policy(current))
            except (ValueError, json.JSONDecodeError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/protect":
            try:
                payload = self._body()
                tool = str(payload.get("tool", "shieldai_search_slack_messages"))
                arguments = {
                    "query": str(payload.get("query", "Falcon")),
                    "channel": str(payload.get("channel", "engineering")),
                    "project_id": str(payload.get("project_id", "demo-falcon")),
                }
                response = gateway.execute(
                    tool_name=tool,
                    arguments=arguments,
                    include_mapping=True,
                )
                self._json(response)
            except (ValueError, json.JSONDecodeError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/documents/protect":
            try:
                encoded_filename = self.headers.get("X-File-Name", "")
                filename = unquote(encoded_filename)
                project_id = str(self.headers.get("X-Project-Id", "local-upload"))[:120]
                content = self._binary_body(document_converter.MAX_UPLOAD_BYTES)
                converted = document_converter.convert_bytes(filename, content)
                response = gateway.protect_text(
                    converted.markdown,
                    project_id=project_id or "local-upload",
                    source="local_upload",
                    upstream_tool="markitdown.convert_local",
                    include_mapping=True,
                    audit_metadata={
                        "document_format": converted.extension,
                        "converted_characters": len(converted.markdown),
                    },
                )
                # The filename is returned only to the local dashboard. It is
                # intentionally not included in the audit event.
                response["document"] = {
                    "filename": converted.filename,
                    "format": converted.extension.removeprefix("."),
                    "markdown_characters": len(converted.markdown),
                    "converter": "MarkItDown (local)",
                }
                self._json(response)
            except (DocumentConversionError, ValueError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/connectors/google-drive/authorize":
            try:
                # This opens Google's consent page locally. The user must
                # explicitly choose the account and approve read-only access.
                self._json(gateway.proxy.authorize_google_drive())
            except (RuntimeError, ValueError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self.send_error(HTTPStatus.NOT_FOUND)


def main() -> None:
    address = (
        os.getenv("SHIELDAI_BIND_HOST", "127.0.0.1"),
        int(os.getenv("SHIELDAI_PORT", "8787")),
    )
    print(f"ShieldAI dashboard running at http://{address[0]}:{address[1]}")
    ThreadingHTTPServer(address, ShieldAIHandler).serve_forever()


if __name__ == "__main__":
    main()
