"""HTTP Request handler bridging standard library server with AdminRouter."""

from http.server import BaseHTTPRequestHandler
from typing import Optional

from admin.server.request import AdminRequest
from admin.server.response import AdminResponse
from admin.server.router import AdminRouter


class AdminHttpHandler(BaseHTTPRequestHandler):
    """Custom HTTP request handler using AdminRouter for routing."""

    router: Optional[AdminRouter] = None

    def do_GET(self) -> None:
        self._process_request("GET")

    def do_POST(self) -> None:
        self._process_request("POST")

    def do_PUT(self) -> None:
        self._process_request("PUT")

    def do_DELETE(self) -> None:
        self._process_request("DELETE")

    def do_OPTIONS(self) -> None:
        self._process_request("OPTIONS")

    def _process_request(self, method: str) -> None:
        """Process incoming request through AdminRouter and send back AdminResponse."""
        if not self.router:
            self.send_error(500, "Router not initialized")
            return

        # Read body if present
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        # Convert headers to simple dict
        headers_dict = {k: v for k, v in self.headers.items()}

        request = AdminRequest(
            method=method,
            path=self.path,
            headers=headers_dict,
            body=body,
        )

        try:
            response: AdminResponse = self.router.route(request)
        except Exception as e:
            err_html = f"<h1>500 Internal Server Error</h1><p>{e}</p>"
            response = AdminResponse.html(err_html, status_code=500)

        # Send status
        self.send_response(response.status_code)

        # Send headers
        for header_name, header_val in response.headers.items():
            self.send_header(header_name, header_val)

        # Send cookies
        for cookie_str in response.cookies:
            self.send_header("Set-Cookie", cookie_str)

        self.end_headers()

        # Send body
        if response.body:
            self.wfile.write(response.body)

    def log_message(self, format: str, *args) -> None:
        """Suppress noisy default request logs in test/prod environments."""
        pass
