"""HTTP Request representation for the admin console server."""

import email
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

        # Parse form data, uploaded files, and JSON body
        self.form_data: Dict[str, Any] = {}
        self.files: Dict[str, Dict[str, Any]] = {}
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
        elif "multipart/form-data" in content_type:
            try:
                self._parse_multipart(content_type)
            except Exception:
                pass
        elif "application/json" in content_type:
            try:
                self._json_data = json.loads(self.body.decode("utf-8", errors="replace"))
            except Exception:
                self._json_data = None

    def _parse_multipart(self, content_type_header: str) -> None:
        """Parse multipart/form-data body into form_data and files."""
        boundary = None
        for item in content_type_header.split(";"):
            item = item.strip()
            if item.lower().startswith("boundary="):
                boundary = item.split("=", 1)[1].strip().strip('"').strip("'")
                break

        if not boundary:
            raw_msg = (
                b"Content-Type: "
                + content_type_header.encode("latin1", errors="replace")
                + b"\r\n\r\n"
                + self.body
            )
            msg = email.message_from_bytes(raw_msg)
            for part in msg.walk():
                if part.is_multipart():
                    continue
                cd = part.get("Content-Disposition", "")
                if not cd:
                    continue
                name = part.get_param("name", header="content-disposition")
                filename = part.get_filename()
                payload = part.get_payload(decode=True) or b""
                if name:
                    if filename:
                        self.files[name] = {
                            "filename": filename,
                            "content": payload,
                            "content_type": part.get_content_type(),
                        }
                    else:
                        self.form_data[name] = payload.decode("utf-8", errors="replace")
            return

        delimiter = b"--" + boundary.encode("latin1")
        parts = self.body.split(delimiter)
        for part in parts:
            if not part or part.startswith(b"--"):
                continue
            if part.startswith(b"\r\n"):
                part = part[2:]
            elif part.startswith(b"\n"):
                part = part[1:]
            if part.endswith(b"\r\n"):
                part = part[:-2]
            elif part.endswith(b"\n"):
                part = part[:-1]

            if not part:
                continue

            if b"\r\n\r\n" in part:
                headers_raw, content = part.split(b"\r\n\r\n", 1)
            elif b"\n\n" in part:
                headers_raw, content = part.split(b"\n\n", 1)
            else:
                continue

            headers_text = headers_raw.decode("latin1", errors="replace")
            content_disposition = ""
            part_content_type = "application/octet-stream"
            for hline in headers_text.splitlines():
                if ":" in hline:
                    hname, hval = hline.split(":", 1)
                    if hname.strip().lower() == "content-disposition":
                        content_disposition = hval.strip()
                    elif hname.strip().lower() == "content-type":
                        part_content_type = hval.strip()

            if not content_disposition:
                continue

            field_name = None
            filename = None
            for param in content_disposition.split(";"):
                param = param.strip()
                if param.lower().startswith("name="):
                    field_name = param.split("=", 1)[1].strip().strip('"').strip("'")
                elif param.lower().startswith("filename="):
                    filename = param.split("=", 1)[1].strip().strip('"').strip("'")

            if field_name:
                if filename is not None and filename != "":
                    self.files[field_name] = {
                        "filename": filename,
                        "content": content,
                        "content_type": part_content_type,
                    }
                else:
                    text_val = content.decode("utf-8", errors="replace")
                    if field_name in self.form_data:
                        existing = self.form_data[field_name]
                        if isinstance(existing, list):
                            existing.append(text_val)
                        else:
                            self.form_data[field_name] = [existing, text_val]
                    else:
                        self.form_data[field_name] = text_val

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

    def get_form_list(self, name: str) -> list:
        """Get list of values for a given form key (handles single value, list, or missing)."""
        val = self.form_data.get(name)
        if val is None:
            val = self.form_data.get(f"{name}[]")
        if val is None:
            return []
        if isinstance(val, list):
            return [str(item) for item in val if item is not None]
        return [str(val)]

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
