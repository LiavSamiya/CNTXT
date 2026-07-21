"""Local web dashboard and API for the ShieldAI MVP."""

from __future__ import annotations

import json
import mimetypes
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# `python backend/app.py` places backend/ rather than the project root on
# sys.path. Add the root so the package imports below work from the README.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.authorization import public_users
from backend.gateway import ShieldAIGateway
from backend.policies import public_policies


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
gateway = ShieldAIGateway()


class ShieldAIHandler(BaseHTTPRequestHandler):
    server_version = "ShieldAI/0.1"

    def log_message(self, _format: str, *_args: object) -> None:
        # Keep the demo terminal readable; audit events are persisted separately.
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
        path = urlparse(self.path).path
        if path == "/api/bootstrap":
            self._json(
                {
                    "users": public_users(),
                    "policies": public_policies(),
                    "connectors": [
                        {"name": "Slack", "status": "Protected", "tools": 2},
                        {"name": "Google Drive", "status": "Protected", "tools": 1},
                        {"name": "GitHub", "status": "Protected", "tools": 1},
                    ],
                    "logs": gateway.recent_audit_events(),
                }
            )
            return
        if path == "/api/logs":
            self._json(gateway.recent_audit_events())
            return
        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path != "/api/demo":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._body()
            response = gateway.execute(
                user_id=str(payload.get("user_id", "john")),
                tool_name=str(payload.get("tool", "shieldai_search_slack_messages")),
                arguments={
                    "query": str(payload.get("query", "Falcon")),
                    "channel": str(payload.get("channel", "engineering")),
                },
                policy_id=str(payload.get("policy_id", "defense")),
                include_mapping=True,
            )
            self._json(response)
        except (PermissionError, ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)


def main() -> None:
    # Desktop mode remains loopback-only. Docker opts in to 0.0.0.0 inside
    # its private network, while Compose still publishes the port only to the
    # host loopback interface.
    address = (os.getenv("SHIELDAI_BIND_HOST", "127.0.0.1"), 8787)
    print(f"ShieldAI dashboard running at http://{address[0]}:{address[1]}")
    ThreadingHTTPServer(address, ShieldAIHandler).serve_forever()


if __name__ == "__main__":
    main()
