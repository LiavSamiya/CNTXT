"""Local, read-only Google Drive connector for ShieldAI.

This module uses Python's standard library only. The OAuth authorization code
flow happens in the user's system browser; the resulting token stays on the
local device and raw Drive content stays behind the ShieldAI Gateway.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from .document_converter import DocumentConversionError, LocalDocumentConverter


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CREDENTIALS_PATH = ROOT / "secrets" / "google-oauth-client.json"
DEFAULT_TOKEN_PATH = ROOT / "data" / "google_token.json"
SCOPES = ("https://www.googleapis.com/auth/drive.readonly",)


class GoogleDriveError(RuntimeError):
    """A safe error message for the local dashboard or an MCP client."""


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        self.server.oauth_result = {key: value[0] for key, value in params.items()}  # type: ignore[attr-defined]
        body = (
            "<html><body style='font-family:system-ui;padding:2rem'>"
            "<h2>ShieldAI connected to Google Drive</h2>"
            "<p>You can close this window and return to ShieldAI.</p>"
            "</body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class GoogleDriveConnector:
    """Desktop OAuth + read-only Google Drive adapter without external SDKs."""

    def __init__(self, credentials_path: Path | None = None, token_path: Path | None = None) -> None:
        configured = os.getenv("SHIELDAI_GOOGLE_OAUTH_CLIENT")
        self.credentials_path = Path(configured) if configured else (credentials_path or DEFAULT_CREDENTIALS_PATH)
        self.token_path = token_path or DEFAULT_TOKEN_PATH
        self.document_converter = LocalDocumentConverter()

    def status(self) -> dict[str, str | bool]:
        if not self.credentials_path.is_file():
            return {
                "status": "Demo data",
                "detail": "Add secrets/google-oauth-client.json to connect your Drive.",
                "connected": False,
            }
        if not self.token_path.is_file():
            return {
                "status": "Ready to connect",
                "detail": "OAuth client found. Click Connect Google Drive.",
                "connected": False,
            }
        return {"status": "Connected", "detail": "Read-only OAuth connection", "connected": True}

    def _client(self) -> dict[str, str]:
        if not self.credentials_path.is_file():
            raise GoogleDriveError(
                "OAuth client file not found. Save the Google JSON as "
                "secrets/google-oauth-client.json first."
            )
        try:
            payload = json.loads(self.credentials_path.read_text(encoding="utf-8"))
            client = payload["installed"]
            required = ("client_id", "auth_uri", "token_uri")
            if not all(client.get(key) for key in required):
                raise ValueError("missing required OAuth client fields")
            return client
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise GoogleDriveError("Invalid Google Desktop OAuth client JSON.") from exc

    @staticmethod
    def _form_post(url: str, values: dict[str, str]) -> dict[str, Any]:
        request = urllib.request.Request(
            url,
            data=urllib.parse.urlencode(values).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise GoogleDriveError("Google OAuth could not complete. Check your connection and try again.") from exc

    @staticmethod
    def _pkce_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def authorize(self) -> dict[str, str | bool]:
        """Launch Google consent in the system browser and persist a local token."""
        client = self._client()
        callback = HTTPServer(("127.0.0.1", 0), _OAuthCallbackHandler)
        callback.timeout = 1
        redirect_uri = f"http://127.0.0.1:{callback.server_port}/oauth2/callback"
        state = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        params = {
            "client_id": client["client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "code_challenge": self._pkce_challenge(verifier),
            "code_challenge_method": "S256",
        }
        webbrowser.open(f"{client['auth_uri']}?{urllib.parse.urlencode(params)}")
        deadline = time.monotonic() + 300
        try:
            while not hasattr(callback, "oauth_result") and time.monotonic() < deadline:
                callback.handle_request()
        finally:
            callback.server_close()
        result = getattr(callback, "oauth_result", {})
        if result.get("state") != state or not result.get("code"):
            raise GoogleDriveError("Google Drive authorization was cancelled or timed out.")
        token = self._form_post(
            client["token_uri"],
            {
                "code": result["code"],
                "client_id": client["client_id"],
                "client_secret": client.get("client_secret", ""),
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
        )
        token["expires_at"] = time.time() + int(token.get("expires_in", 3600))
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(json.dumps(token), encoding="utf-8")
        return self.status()

    def _token(self) -> dict[str, Any]:
        if not self.token_path.is_file():
            raise GoogleDriveError("Google Drive is not connected. Click Connect Google Drive first.")
        try:
            token = json.loads(self.token_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GoogleDriveError("Saved Google Drive session is invalid. Connect again.") from exc
        if token.get("expires_at", 0) > time.time() + 60:
            return token
        if not token.get("refresh_token"):
            raise GoogleDriveError("Google Drive session expired. Connect Google Drive again.")
        client = self._client()
        refreshed = self._form_post(
            client["token_uri"],
            {
                "client_id": client["client_id"],
                "client_secret": client.get("client_secret", ""),
                "refresh_token": token["refresh_token"],
                "grant_type": "refresh_token",
            },
        )
        token.update(refreshed)
        token["expires_at"] = time.time() + int(token.get("expires_in", 3600))
        self.token_path.write_text(json.dumps(token), encoding="utf-8")
        return token

    def _request(self, url: str) -> bytes:
        token = self._token()
        request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token['access_token']}"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise GoogleDriveError(f"Google Drive request failed ({exc.code}).") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise GoogleDriveError("Could not reach Google Drive. Check your connection and try again.") from exc

    def _read_file(self, file: dict[str, str]) -> str:
        file_id = file["id"]
        mime_type = file.get("mimeType", "")
        try:
            if mime_type == "application/vnd.google-apps.document":
                url = "https://www.googleapis.com/drive/v3/files/" + urllib.parse.quote(file_id) + "/export?" + urllib.parse.urlencode({"mimeType": "text/plain"})
                return self._request(url).decode("utf-8", errors="replace")
            if mime_type in {"text/plain", "text/markdown", "application/json", "text/csv", "text/html"}:
                url = "https://www.googleapis.com/drive/v3/files/" + urllib.parse.quote(file_id) + "?alt=media"
                return self._request(url).decode("utf-8", errors="replace")
            if mime_type in {
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel",
            }:
                url = "https://www.googleapis.com/drive/v3/files/" + urllib.parse.quote(file_id) + "?alt=media"
                converted = self.document_converter.convert_bytes(
                    file.get("name", "document"), self._request(url)
                )
                return converted.markdown
        except DocumentConversionError as exc:
            return f"[Could not convert file locally: {exc}]"
        except GoogleDriveError as exc:
            return f"[Could not read file content: {exc}]"
        return f"[Metadata only: conversion for {mime_type or 'this file type'} is not enabled yet.]"

    def search_documents(self, query: str, max_results: int = 10) -> str:
        """Retrieve raw Drive content locally; Gateway sanitizes it before return."""
        terms = [term.replace("'", "\\'") for term in query.split() if term.strip()]
        drive_query = "trashed = false"
        if terms:
            drive_query += " and (" + " or ".join(f"fullText contains '{term}'" for term in terms) + ")"
        params = {
            "q": drive_query,
            "pageSize": str(max_results),
            "fields": "files(id,name,mimeType,modifiedTime)",
            "orderBy": "modifiedTime desc",
        }
        response = json.loads(self._request("https://www.googleapis.com/drive/v3/files?" + urllib.parse.urlencode(params)).decode("utf-8"))
        files = response.get("files", [])
        if not files:
            return "No matching Google Drive documents were found."
        return "\n\n".join(
            f"Google Drive | {file.get('name', 'Untitled document')}: {self._read_file(file)}"
            for file in files
        )
