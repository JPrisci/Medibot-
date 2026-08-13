#!/usr/bin/env python3

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "gblock_route_runner.py"

route_process = None
route_lock = threading.Lock()


def route_running():
    global route_process
    return route_process is not None and route_process.poll() is None


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type",
        )
        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS",
        )
        self.end_headers()

        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type",
        )
        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS",
        )
        self.end_headers()

    def do_GET(self):
        if self.path == "/status":
            self.send_json(
                200,
                {
                    "running": route_running(),
                    "destination": (
                        "ELEVATOR_2"
                        if route_running()
                        else None
                    ),
                },
            )
            return

        self.send_json(
            404,
            {"error": "Not found"},
        )

    def do_POST(self):
        global route_process

        if self.path == "/route/start":
            length = int(
                self.headers.get("Content-Length", "0")
            )

            raw_body = self.rfile.read(length)

            try:
                payload = (
                    json.loads(raw_body)
                    if raw_body
                    else {}
                )
            except json.JSONDecodeError:
                self.send_json(
                    400,
                    {"error": "Invalid JSON"},
                )
                return

            destination = payload.get(
                "destination",
                "ELEVATOR_2",
            )

            # First integration test is deliberately limited
            # to the route already tested on Gem.
            if destination != "ELEVATOR_2":
                self.send_json(
                    400,
                    {
                        "error": (
                            "Only ELEVATOR_2 is enabled "
                            "during initial integration."
                        )
                    },
                )
                return

            with route_lock:
                if route_running():
                    self.send_json(
                        409,
                        {
                            "error": (
                                "A navigation route is "
                                "already running."
                            )
                        },
                    )
                    return

                command = [
                    sys.executable,
                    str(RUNNER),
                    "--destination",
                    destination,
                    "--run",
                ]

                print(
                    "Starting route:",
                    " ".join(command),
                    flush=True,
                )

                route_process = subprocess.Popen(
                    command,
                    cwd=str(ROOT),
                )

            self.send_json(
                200,
                {
                    "started": True,
                    "destination": destination,
                    "pid": route_process.pid,
                },
            )
            return

        self.send_json(
            404,
            {"error": "Not found"},
        )

    def log_message(self, format, *args):
        print(
            f"[route_api] {self.address_string()} "
            f"- {format % args}"
        )


def main():
    address = ("0.0.0.0", 8082)

    print(
        "Medibot route API listening on "
        "http://0.0.0.0:8082",
        flush=True,
    )

    server = ThreadingHTTPServer(
        address,
        Handler,
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
