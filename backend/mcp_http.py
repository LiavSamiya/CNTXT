"""Localhost MCP HTTP transport for ShieldAI Desktop.

This implements a compact JSON-RPC endpoint at `POST /mcp` on port 8765. It
shares the exact same tool handler as the stdio transport, so policy enforcement
does not vary by client. No user identity header is required.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.gateway import ShieldAIGateway
from backend.mcp_server import _error, handle


gateway = ShieldAIGateway()


class MCPHTTPHandler(BaseHTTPRequestHandler):
    server_version = "ShieldAI-MCP/0.1"

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK, session_id: str | None = None) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", os.getenv("SHIELDAI_DASHBOARD_ORIGIN", "http://127.0.0.1:8787"))
        if session_id:
            self.send_header("Mcp-Session-Id", session_id)
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", os.getenv("SHIELDAI_DASHBOARD_ORIGIN", "http://127.0.0.1:8787"))
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Mcp-Session-Id")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._send_json({"service": "shieldai-local-mcp", "status": "healthy", "endpoint": "/mcp"})
            return
        self._send_json({"error": "Use POST /mcp for MCP JSON-RPC messages."}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/mcp":
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 250_000:
                raise ValueError("Invalid MCP request size")
            message = json.loads(self.rfile.read(length).decode("utf-8"))
            payload = handle(message, gateway)
            if payload is None:
                self.send_response(HTTPStatus.ACCEPTED)
                self.end_headers()
                return
            session_id = secrets.token_urlsafe(18) if message.get("method") == "initialize" else None
            self._send_json(payload, session_id=session_id)
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(_error(None, -32700, str(exc)), HTTPStatus.BAD_REQUEST)


def main() -> None:
    host = os.getenv("SHIELDAI_BIND_HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, 8765), MCPHTTPHandler)
    print(f"ShieldAI local MCP transport running at http://{host}:8765/mcp")
    server.serve_forever()


if __name__ == "__main__":
    main()
