"""Streamlabs Desktop TikTok workflow ported from T0G Stream Control.

This is a best-effort integration with the Desktop API family, not an official
third-party Streamlabs API. Tokens and RTMP keys stay in process memory.
The LIVE-start operation creates a real LIVE session; calling it is never
part of sign-in or startup.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import re
import threading
import webbrowser
from urllib.parse import urlencode, urlsplit, parse_qs, quote

import requests

from streamkey.credentials import Credentials

BASE = "https://streamlabs.com"
API = BASE + "/api/v5/slobs"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) StreamlabsDesktop/1.20.4 Chrome/122.0.6261.156 "
    "Electron/29.3.1 Safari/537.36"
)
TOKEN_PATTERN = re.compile(rb'"apiToken":"([a-fA-F0-9]+)"')


class StreamlabsError(RuntimeError):
    """A safe-to-display error that does not include bearer credentials."""


class SessionRejected(StreamlabsError):
    """Streamlabs rejected or expired the current token."""


@dataclass(frozen=True)
class AccountInfo:
    username: str
    status: str
    can_go_live: bool


@dataclass(frozen=True)
class LiveSession:
    credentials: Credentials = field(repr=False)
    stream_id: str = field(repr=False)


def load_token_from_pc() -> str:
    """Explicitly load a token from the user's own Streamlabs Desktop profile."""
    root = os.environ.get("APPDATA")
    if not root:
        raise StreamlabsError("Windows APPDATA is unavailable.")
    leveldb = Path(root) / "slobs-client" / "Local Storage" / "leveldb"
    if not leveldb.is_dir():
        raise StreamlabsError("Streamlabs Desktop data was not found on this PC.")
    files = sorted(leveldb.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        matches = TOKEN_PATTERN.findall(data)
        if matches:
            return matches[-1].decode("ascii")
    raise StreamlabsError("No Streamlabs token found. Use Load from Web instead.")


def _pkce() -> tuple[str, str]:
    verifier = os.urandom(64).hex()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).decode("ascii").rstrip("=")
    return verifier, challenge


def login_from_web(timeout: int = 300) -> str:
    """Authorize in the browser, receiving only a one-use code on loopback."""
    verifier, challenge = _pkce()
    finished = threading.Event()
    callback: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            location = urlsplit(self.path)
            if location.path not in ("/", "/callback"):
                self.send_error(404)
                return
            params = parse_qs(location.query)
            code = params.get("code", [""])[0]
            success = params.get("success", [""])[0].lower() == "true" and bool(code)
            if not finished.is_set():
                if success:
                    callback["code"] = code
                body = (b"Streamlabs authorization received. You may close this tab."
                        if success else b"Streamlabs authorization was not completed.")
                self.send_response(200 if success else 400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                finished.set()
            else:
                self.send_error(409)

        def log_message(self, *_args):
            pass  # Never log an authorization code in an HTTP request URL.

    try:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    except OSError as exc:
        raise StreamlabsError("Could not open local Streamlabs login callback.") from exc
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        params = {
            "skip_splash": "true", "external": "electron", "tiktok": "",
            "force_verify": "", "origin": "slobs", "port": server.server_port,
            "code_challenge": challenge, "code_flow": "true",
        }
        if not webbrowser.open(BASE + "/slobs/login?" + urlencode(params)):
            raise StreamlabsError("Could not open the default web browser.")
        if not finished.wait(timeout=timeout):
            raise StreamlabsError("Streamlabs login timed out; please try again.")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    if "code" not in callback:
        raise StreamlabsError("Streamlabs login was canceled or returned no code.")

    try:
        response = requests.get(
            API + "/auth/data",
            params={"code_verifier": verifier, "code": callback["code"]},
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            timeout=30,
            allow_redirects=False,
        )
        if response.status_code != 200:
            raise StreamlabsError(f"Streamlabs token exchange failed (HTTP {response.status_code}).")
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise StreamlabsError("Streamlabs token exchange failed or returned invalid data.") from exc
    token = data.get("data", {}).get("oauth_token") if isinstance(data, dict) else None
    if not data.get("success") or not isinstance(token, str) or not token:
        raise StreamlabsError("Streamlabs did not provide a session token.")
    return token


class StreamlabsTikTok:
    """Only uses Streamlabs' HTTPS API and never stores a token on disk."""

    def __init__(self, token: str, session: requests.Session | None = None):
        if not token or not token.strip():
            raise StreamlabsError("Connect Streamlabs first.")
        self._token = token.strip()
        self._session = session if session is not None else requests.Session()

    def disconnect(self):
        self._token = ""
        self._session.close()

    def _request(self, method: str, path: str, **kwargs) -> dict:
        if not self._token:
            raise SessionRejected("Streamlabs is disconnected; sign in again.")
        try:
            response = self._session.request(
                method, API + path,
                headers={"User-Agent": USER_AGENT, "Authorization": "Bearer " + self._token,
                         "Accept": "application/json"},
                timeout=30, allow_redirects=False, **kwargs,
            )
        except requests.RequestException as exc:
            raise StreamlabsError("Could not reach Streamlabs. Check your connection.") from exc
        if response.status_code in (401, 403):
            self._token = ""
            raise SessionRejected("Streamlabs rejected the session. Sign in again.")
        if not 200 <= response.status_code < 300:
            raise StreamlabsError(f"Streamlabs request failed (HTTP {response.status_code}).")
        try:
            result = response.json()
        except ValueError as exc:
            raise StreamlabsError("Streamlabs returned an unreadable response.") from exc
        if not isinstance(result, dict):
            raise StreamlabsError("Streamlabs returned an unexpected response.")
        return result

    def get_account(self) -> AccountInfo:
        info = self._request("GET", "/tiktok/info")
        user = info.get("user") or {}
        status = info.get("application_status") or {}
        return AccountInfo(
            username=str(user.get("username") or "Unknown"),
            status=str(status.get("status") or "Unknown"),
            can_go_live=info.get("can_be_live") is True,
        )

    def resolve_category(self, name: str) -> str:
        name = name.strip()
        if not name:
            return ""
        info = self._request("GET", "/tiktok/info", params={"category": name[:25]})
        categories = info.get("categories") or []
        if not isinstance(categories, list) or not categories:
            return ""
        for entry in categories:
            if isinstance(entry, dict) and str(entry.get("full_name", "")).casefold() == name.casefold():
                return str(entry.get("game_mask_id") or "")
        first = categories[0]
        return str(first.get("game_mask_id") or "") if isinstance(first, dict) else ""

    def start_live(self, title: str, category: str = "", mature: bool = False) -> LiveSession:
        title = title.strip()
        if not title:
            raise StreamlabsError("Enter a TikTok LIVE title.")
        category_id = self.resolve_category(category)
        result = self._request("POST", "/tiktok/stream/start", files=[
            ("title", (None, title)),
            ("device_platform", (None, "win32")),
            ("category", (None, category_id)),
            ("audience_type", (None, "1" if mature else "0")),
        ])
        try:
            credentials = Credentials.parse(
                str(result.get("rtmp") or ""), str(result.get("key") or "")
            )
        except ValueError as exc:
            raise StreamlabsError("Streamlabs did not return valid RTMP credentials.") from exc
        stream_id = result.get("id")
        return LiveSession(credentials, str(stream_id) if stream_id is not None else "")

    def end_live(self, stream_id: str) -> None:
        if not stream_id:
            raise StreamlabsError("No Streamlabs LIVE session ID is available.")
        # Escape the ID; it is only ever supplied by Streamlabs' start response.
        result = self._request("POST", "/tiktok/stream/" + quote(stream_id, safe="") + "/end")
        if result.get("success") is not True:
            raise StreamlabsError("Streamlabs did not confirm the TikTok LIVE ended.")
