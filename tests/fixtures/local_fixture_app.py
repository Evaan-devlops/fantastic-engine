"""Local stdlib HTTP fixture app for integration tests — written but not run."""
from __future__ import annotations

import json
import socketserver
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler

_LOGIN_HTML = """\
<html><body>
<form method="POST" action="/login">
  <input type="text" name="username" placeholder="Username">
  <input type="password" name="password" placeholder="Password">
  <button type="submit">Submit</button>
</form>
</body></html>"""

_DASHBOARD_HTML = """\
<html><body>
<h1>Welcome to Dashboard</h1>
<a href="/contacts">Create Contact</a>
</body></html>"""

_MANUAL_AUTH_HTML = """\
<html><body>
<p>Complete authentication</p>
</body></html>"""

_SPINNER_HTML = """\
<html><body>
<div id="loading">Loading...</div>
<button>Start</button>
</body></html>"""

_FORM_HTML = """\
<html><body>
<form>
  <input type="text" name="name">
  <input type="text" name="email">
  <input type="text" name="phone">
  <select id="status">
    <option value="active">Active</option>
    <option value="inactive">Inactive</option>
  </select>
  <input type="checkbox" id="agree">
</form>
</body></html>"""

_POPUP_HTML = """\
<html><body>
<button>Open Popup</button>
</body></html>"""

_UPLOAD_HTML = """\
<html><body>
<form>
  <input type="file" name="file_upload">
</form>
</body></html>"""

_MISSING_ELEMENT_HTML = """\
<html><body>
<p>This page has no buttons or inputs.</p>
</body></html>"""


class _FixtureHandler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass  # suppress server logs in tests

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path in ("/", "/login"):
            self._send_html(_LOGIN_HTML)
        elif path == "/dashboard":
            self._send_html(_DASHBOARD_HTML)
        elif path == "/manual-auth":
            self._send_html(_MANUAL_AUTH_HTML)
        elif path == "/spinner":
            self._send_html(_SPINNER_HTML)
        elif path == "/form":
            self._send_html(_FORM_HTML)
        elif path == "/popup":
            self._send_html(_POPUP_HTML)
        elif path == "/upload":
            self._send_html(_UPLOAD_HTML)
        elif path == "/download":
            body = b"sample content"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Disposition", "attachment; filename=sample.txt")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/success":
            self._send_json({"status": "ok"})
        elif path == "/not-found":
            self._send_text("not found", status=404)
        elif path == "/missing-element":
            self._send_html(_MISSING_ELEMENT_HTML)
        else:
            self._send_text("not found", status=404)

    def do_POST(self) -> None:
        if self.path == "/login":
            self.send_response(302)
            self.send_header("Location", "/dashboard")
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def _send_html(self, html: str, status: int = 200) -> None:
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200) -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class FixtureApp:
    def __init__(self, port: int = 0) -> None:
        self._port = port
        self._server: socketserver.TCPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._server = socketserver.TCPServer(("127.0.0.1", self._port), _FixtureHandler)
        self._server.allow_reuse_address = True
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._port}"

    @property
    def port(self) -> int:
        return self._port


@contextmanager
def running_fixture_app(port: int = 0):
    app = FixtureApp(port)
    app.start()
    try:
        yield app
    finally:
        app.stop()
