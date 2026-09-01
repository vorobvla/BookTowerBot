"""HTTP Response representation for the admin console server."""

import json
from typing import Any, Dict, List, Optional


class AdminResponse:
    """Encapsulates an outgoing HTTP response."""

    def __init__(
        self,
        body: bytes = b"",
        status_code: int = 200,
        content_type: str = "text/html; charset=utf-8",
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[List[str]] = None,
    ):
        self.body = body
        self.status_code = status_code
        self.headers: Dict[str, str] = headers or {}
        self.headers["Content-Type"] = content_type
        self.headers["Content-Length"] = str(len(body))
        self.cookies: List[str] = cookies or []

    @classmethod
    def html(
        cls,
        html_content: str,
        status_code: int = 200,
        cookies: Optional[List[str]] = None,
    ) -> "AdminResponse":
        """Construct an HTML response."""
        body = html_content.encode("utf-8")
        return cls(
            body=body,
            status_code=status_code,
            content_type="text/html; charset=utf-8",
            cookies=cookies,
        )

    @classmethod
    def json(
        cls,
        data: Any,
        status_code: int = 200,
        cookies: Optional[List[str]] = None,
    ) -> "AdminResponse":
        """Construct a JSON response."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        return cls(
            body=body,
            status_code=status_code,
            content_type="application/json; charset=utf-8",
            cookies=cookies,
        )

    @classmethod
    def redirect(
        cls,
        location: str,
        status_code: int = 302,
        cookies: Optional[List[str]] = None,
    ) -> "AdminResponse":
        """Construct a redirect response."""
        headers = {"Location": location}
        return cls(
            body=b"",
            status_code=status_code,
            headers=headers,
            cookies=cookies,
        )

    @classmethod
    def unauthorized(
        cls,
        message: str = "Unauthorized",
        as_json: bool = False,
    ) -> "AdminResponse":
        """Construct a 401 Unauthorized response."""
        if as_json:
            return cls.json({"error": message}, status_code=401)
        return cls.html(f"<h1>401 Unauthorized</h1><p>{message}</p>", status_code=401)
