#!/usr/bin/env python3
"""Minimal shared route-request API for the NaviBot prototype.

Run on the machine that the route consumer can reach:
    python route_api.py
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock
from typing import Any

_route_requests: list[dict[str, str]] = []
_requests_lock = Lock()


class RouteRequestHandler(BaseHTTPRequestHandler):
    """Accept and expose confirmed route requests."""

    def _send_json(self, status: HTTPStatus, data: Any) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/route-requests":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(content_length))
            destination = payload["destination"]
            user_id = payload["user_id"]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "JSON must contain string fields: destination, user_id"},
            )
            return

        if not isinstance(destination, str) or not isinstance(user_id, str):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "destination and user_id must both be strings"},
            )
            return

        route_request = {
            "destination": destination,
            "user_id": user_id,
            "received_at": datetime.now(UTC).isoformat(),
        }
        with _requests_lock:
            _route_requests.append(route_request)
        self._send_json(HTTPStatus.CREATED, route_request)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/route-requests":
            with _requests_lock:
                requests = list(_route_requests)
            self._send_json(HTTPStatus.OK, requests)
        elif self.path == "/route-requests/latest":
            with _requests_lock:
                latest = _route_requests[-1] if _route_requests else None
            if latest is None:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "No route requests yet"})
            else:
                self._send_json(HTTPStatus.OK, latest)
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8000), RouteRequestHandler)
    print("Route API listening on http://0.0.0.0:8000/route-requests")
    server.serve_forever()
