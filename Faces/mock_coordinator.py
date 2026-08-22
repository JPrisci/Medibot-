#!/usr/bin/env python3
"""Small local substitute for the Coordinator API used to test Faces.

It begins at the handover state. Clicking Gem's Continue button sends
``POST /visitor-ready`` and this mock changes to ``gem_guidance_started``.
It does not require ROS or robots.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse


state = {
    "state": "handover_ready",
    "current_stage": "waiting_for_visitor_ready",
    "user_id": "demo_visitor",
}


class MockCoordinatorHandler(BaseHTTPRequestHandler):
    def send_json(self, status: HTTPStatus, data: dict) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path == "/ux-state/latest":
            self.send_json(HTTPStatus.OK, state)
        else:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/visitor-ready":
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self.send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON"})
            return

        if payload.get("user_id") != state["user_id"]:
            self.send_json(HTTPStatus.CONFLICT, {"error": "Wrong visitor"})
            return

        state.update(
            {"state": "gem_guidance_started", "current_stage": "gem_route_requested"}
        )
        self.send_json(HTTPStatus.OK, {"accepted": True, "task_state": state["state"]})

    def log_message(self, format: str, *args: object) -> None:
        print(format % args)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8000), MockCoordinatorHandler)
    print("Mock Coordinator listening on http://127.0.0.1:8000")
    server.serve_forever()
