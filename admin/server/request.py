"""HTTP Request representation for the admin console server."""

import json
from http.cookies import SimpleCookie
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, unquote_plus


class AdminRequest:
    """Encapsulates an incoming HTTP request."""

    def __init__(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        body: bytes = b"",
    ):
        self.method = method.upper()
        self.raw_path = path
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.body = body

        # Parse path and query parameters
        if "?" in path:
            self.path, query_str = path.split("?", 1)
            raw_query = parse_qs(query_str, keep_blank_values=True)
            self.query_params = {k: v[0] if len(v) == 1 else v for k, v in raw_query.items()}
        else:
            self.path = path
            self.query_params = {}

        # Parse cookies
        self.cookies: Dict[str, str] = {}
        cookie_header = self.headers.get("cookie")
        if cookie_header:
            try:
                simple_cookie = SimpleCookie()
                simple_cookie.load(cookie_header)
                self.cookies = {k: morsel.value for k, morsel in simple_cookie.items()}
            except Exception:
                self.cookies = {}

        # Parse form data and JSON body
        self.form_data: Dict[str, Any] = {}
        self._json_data: Optional[Any] = None
        self._parse_body()

    def _parse_body(self) -> None:
        """Parse request body according to Content-Type header."""
        if not self.body:
            return

        content_type = self.headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type:
            try:
                body_str = self.body.decode("utf-8", errors="replace")
                raw_form = parse_qs(body_str, keep_blank_values=True)
                self.form_data = {k: v[0] if len(v) == 1 else v for k, v in raw_form.items()}
            except Exception:
                self.form_data = {}
        elif "application/json" in content_type:
            try:
                self._json_data = json.loads(self.body.decode("utf-8", errors="replace"))
            except Exception:
                self._json_data = None

    def json(self) -> Optional[Any]:
        """Return parsed JSON body if present."""
        if self._json_data is not None:
            return self._json_data
        if self.body:
            try:
                self._json_data = json.loads(self.body.decode("utf-8", errors="replace"))
                return self._json_data
            except Exception:
                return None
        return None

    def get_cookie(self, name: str) -> Optional[str]:
        """Get value of specified cookie name."""
        return self.cookies.get(name)

    def get_basic_auth(self) -> Optional[Tuple[str, str]]:
        """Extract username and password from HTTP Basic Authorization header if present."""
        auth_header = self.headers.get("authorization", "")
        if auth_header.lower().startswith("basic "):
            import base64
            try:
                b64_creds = auth_header.split(" ", 1)[1].strip()
                decoded = base64.b64decode(b64_creds).decode("utf-8")
                if ":" in decoded:
                    username, password = decoded.split(":", 1)
                    return username, password
            except Exception:
                return None
        return None
