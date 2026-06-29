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

_EMAIL_LOGIN_HTML = """\
<!doctype html>
<html>
  <body>
    <label for="email">Email address</label>
    <input id="email" type="email" placeholder="Enter your email address">
    <button type="button">Next</button>
  </body>
</html>"""

_EMAIL_LOGIN_DELAYED_HTML = """\
<!doctype html>
<html>
  <body>
    <div id="mount"></div>
    <script>
      setTimeout(() => {
        document.getElementById("mount").innerHTML = `
          <label for="email">Email address</label>
          <input id="email" type="email" placeholder="Enter your email address">
          <button type="button">Next</button>
        `;
      }, 700);
    </script>
  </body>
</html>"""

_EMAIL_LOGIN_PLACEHOLDER_HTML = """\
<!doctype html>
<html>
  <body>
    <input id="email" type="email" placeholder="Enter your email address">
    <button type="button">Next</button>
  </body>
</html>"""

_EMAIL_LOGIN_HIDDEN_DUPLICATE_HTML = """\
<!doctype html>
<html>
  <body>
    <input aria-label="Email address" type="email" style="display:none">
    <label for="email">Email address</label>
    <input id="email" type="email" placeholder="Enter your email address">
    <button type="button">Next</button>
  </body>
</html>"""

_EMAIL_LOGIN_AMBIGUOUS_HTML = """\
<!doctype html>
<html>
  <body>
    <label for="email1">Email address</label>
    <input id="email1" type="email" placeholder="Enter your email address">
    <label for="email2">Email address</label>
    <input id="email2" type="email" placeholder="Enter your email address">
    <button type="button">Next</button>
  </body>
</html>"""

_AUTH_LOGIN_HTML = """\
<!doctype html>
<html>
  <body>
    <form id="email-form">
      <label for="email">Email address</label>
      <input id="email" type="email" placeholder="Enter your email address">
      <button id="next" type="submit" disabled>Next</button>
    </form>
    <script>
      const email = document.getElementById("email");
      const next = document.getElementById("next");
      const update = () => { next.disabled = !email.value.includes("@"); };
      email.addEventListener("input", update);
      email.addEventListener("blur", update);
      document.getElementById("email-form").addEventListener("submit", event => {
        event.preventDefault();
        setTimeout(() => {
          window.history.pushState({}, "", "/auth/password");
          document.body.innerHTML = `
            <form id="password-form">
              <label for="password">Password</label>
              <input id="password" type="password" placeholder="Password">
              <button type="submit">Sign in</button>
            </form>
          `;
          document.getElementById("password-form").addEventListener("submit", passwordEvent => {
            passwordEvent.preventDefault();
            window.history.pushState({}, "", "/auth/manual");
            document.body.innerHTML = "<p>Complete authentication</p><button>Continue</button>";
          });
        }, 300);
      });
    </script>
  </body>
</html>"""

_AUTH_LOGIN_DELAYED_HTML = """\
<!doctype html>
<html>
  <body>
    <form id="email-form">
      <label for="email">Email address</label>
      <input id="email" type="email" placeholder="Enter your email address">
      <button id="next" type="submit" disabled>Next</button>
    </form>
    <script>
      const email = document.getElementById("email");
      const next = document.getElementById("next");
      const update = () => { next.disabled = !email.value.includes("@"); };
      email.addEventListener("input", update);
      email.addEventListener("blur", update);
      document.getElementById("email-form").addEventListener("submit", event => {
        event.preventDefault();
        setTimeout(() => {
          window.history.pushState({}, "", "/auth/password-delayed");
          document.body.innerHTML = `
            <form id="password-form">
              <label for="password">Password</label>
              <input id="password" type="password" placeholder="Password">
              <button type="submit">Sign in</button>
            </form>
          `;
        }, 900);
      });
    </script>
  </body>
</html>"""

_AUTH_USERNAME_PASSWORD_HTML = """\
<!doctype html>
<html><body>
  <label for="username">Username</label>
  <input id="username" type="text">
  <label for="password">Password</label>
  <input id="password" type="password">
</body></html>"""

_AUTH_PASSWORD_ONLY_HTML = """\
<!doctype html>
<html><body>
  <label for="password">Password</label>
  <input id="password" type="password">
</body></html>"""

_AUTH_SSO_HTML = """\
<!doctype html>
<html><body><p>Redirecting to identity provider</p></body></html>"""

_AUTH_MANUAL_HTML = """\
<!doctype html>
<html><body><p>Complete authentication</p><button>Continue</button></body></html>"""

_AUTH_DASHBOARD_HTML = """\
<!doctype html>
<html><body><h1>Dashboard</h1><button>Log out</button></body></html>"""

_AUTH_ERROR_HTML = """\
<!doctype html>
<html><body><p>Authentication failed</p></body></html>"""

_AUTH_SIGN_IN_HTML = """\
<!doctype html>
<html>
  <body>
    <form id="signin-form">
      <label for="password">Password</label>
      <input id="password" type="password" placeholder="Password">
      <button type="submit">Sign in</button>
    </form>
    <script>
      document.getElementById("signin-form").addEventListener("submit", ev => {
        ev.preventDefault();
        window.history.pushState({}, "", "/auth/manual-waiting");
        document.body.innerHTML = "<p>Complete authentication</p><button>Continue</button>";
      });
    </script>
  </body>
</html>"""

_AUTH_MANUAL_WAITING_HTML = """\
<!doctype html>
<html><body><p>Complete authentication</p><button>Continue</button></body></html>"""

_AUTH_AUTHENTICATED_HTML = """\
<!doctype html>
<html><body><h1>Dashboard</h1><p>You are now signed in.</p><button>Log out</button></body></html>"""

_AUTH_LOGIN_INTERCEPT_HTML = """\
<!doctype html>
<html>
  <body>
    <form id="email-form">
      <label for="email">Email address</label>
      <input id="email" type="email" placeholder="Enter your email address">
      <button id="next" type="submit" disabled>Next</button>
    </form>
    <div id="overlay" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5)"></div>
    <script>
      const email = document.getElementById("email");
      const next = document.getElementById("next");
      const overlay = document.getElementById("overlay");
      const update = () => { next.disabled = !email.value.includes("@"); };
      email.addEventListener("input", update);
      email.addEventListener("blur", update);
      let clickCount = 0;
      next.addEventListener("click", ev => {
        ev.preventDefault();
        clickCount++;
        if (clickCount === 1) {
          overlay.style.display = "block";
          setTimeout(() => {
            overlay.style.display = "none";
            window.history.pushState({}, "", "/auth/password");
            document.body.innerHTML = "<form id='password-form'><label for='password'>Password</label><input id='password' type='password'><button type='submit'>Sign in</button></form>";
          }, 500);
        }
      });
    </script>
  </body>
</html>"""


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
        elif path == "/email-login":
            self._send_html(_EMAIL_LOGIN_HTML)
        elif path == "/email-login-delayed":
            self._send_html(_EMAIL_LOGIN_DELAYED_HTML)
        elif path == "/email-login-placeholder":
            self._send_html(_EMAIL_LOGIN_PLACEHOLDER_HTML)
        elif path == "/email-login-hidden-duplicate":
            self._send_html(_EMAIL_LOGIN_HIDDEN_DUPLICATE_HTML)
        elif path == "/email-login-ambiguous":
            self._send_html(_EMAIL_LOGIN_AMBIGUOUS_HTML)
        elif path == "/auth/login":
            self._send_html(_AUTH_LOGIN_HTML)
        elif path == "/auth/login-delayed":
            self._send_html(_AUTH_LOGIN_DELAYED_HTML)
        elif path == "/auth/username-password":
            self._send_html(_AUTH_USERNAME_PASSWORD_HTML)
        elif path == "/auth/password-only":
            self._send_html(_AUTH_PASSWORD_ONLY_HTML)
        elif path == "/auth/sso/redirect":
            self._send_html(_AUTH_SSO_HTML)
        elif path == "/auth/manual":
            self._send_html(_AUTH_MANUAL_HTML)
        elif path == "/auth/dashboard":
            self._send_html(_AUTH_DASHBOARD_HTML)
        elif path == "/auth/error":
            self._send_html(_AUTH_ERROR_HTML)
        elif path == "/auth/sign-in":
            self._send_html(_AUTH_SIGN_IN_HTML)
        elif path == "/auth/manual-waiting":
            self._send_html(_AUTH_MANUAL_WAITING_HTML)
        elif path == "/auth/authenticated":
            self._send_html(_AUTH_AUTHENTICATED_HTML)
        elif path == "/auth/login-intercept":
            self._send_html(_AUTH_LOGIN_INTERCEPT_HTML)
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
