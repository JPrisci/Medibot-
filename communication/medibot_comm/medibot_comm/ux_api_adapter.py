#!/usr/bin/env python3

"""
MediBot Communication-side UX/API adapter.

This node bridges the external HTTP/Flutter UX interface to the ROS 2
interfaces used by the MediBot Communication TaskCoordinator.

External UX -> Communication:

POST /route-requests

{
    "destination": "DIGITAL_LIBRARY",
    "user_id": "..."
}

becomes:

/medibot/ux_event

{
    "event": "destination_selected",
    "destination": "DIGITAL_LIBRARY",
    "user_id": "..."
}


POST /visitor-ready

{
    "user_id": "..."
}

becomes:

/medibot/ux_event

{
    "event": "visitor_ready",
    "user_id": "..."
}


POST /task-reset

becomes:

/medibot/ux_event

{
    "event": "task_reset"
}


Communication -> external UX:

The adapter subscribes to:

/medibot/ux_state

and exposes the latest state through:

GET /ux-state/latest


The existing route-request GET endpoints are retained for simple
testing and compatibility:

GET /route-requests
GET /route-requests/latest


For task-changing requests, HTTP success means that the TaskCoordinator
has confirmed the expected Communication state transition rather than
only meaning that an event was queued for ROS publication.

This adapter does not perform task coordination, physical navigation,
route planning, Create3 control, or UX presentation.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class UxApiAdapter(Node):
    def __init__(self):
        super().__init__("ux_api_adapter")

        # ------------------------------------------------------------------
        # HTTP configuration
        # ------------------------------------------------------------------

        self.declare_parameter(
            "http_host",
            "0.0.0.0",
        )

        self.declare_parameter(
            "http_port",
            8000,
        )

        self.declare_parameter(
            "task_response_timeout_seconds",
            2.0,
        )

        self.http_host = (
            self.get_parameter("http_host")
            .get_parameter_value()
            .string_value
        )

        self.http_port = int(
            self.get_parameter("http_port")
            .get_parameter_value()
            .integer_value
        )

        self.task_response_timeout_seconds = float(
            self.get_parameter("task_response_timeout_seconds")
            .get_parameter_value()
            .double_value
        )

        # ------------------------------------------------------------------
        # Thread-safe shared data
        # ------------------------------------------------------------------

        # HTTP requests arrive on separate HTTP server threads.
        # They are queued and later published by the ROS node.
        self.pending_ux_events = queue.Queue()

        # Protect the latest UX state and allow HTTP requests to wait for
        # TaskCoordinator state confirmation.
        self.state_condition = threading.Condition()

        self.latest_ux_state = None

        # Serialise task-changing HTTP requests.
        self.task_request_lock = threading.Lock()

        # Retain accepted route requests for debugging/compatibility.
        self.route_requests = []

        # ------------------------------------------------------------------
        # External UX -> Communication
        # ------------------------------------------------------------------

        self.ux_event_publisher = self.create_publisher(
            String,
            "/medibot/ux_event",
            10,
        )

        # ------------------------------------------------------------------
        # Communication -> external UX
        # ------------------------------------------------------------------

        self.ux_state_subscription = self.create_subscription(
            String,
            "/medibot/ux_state",
            self.receive_ux_state,
            10,
        )

        # Process HTTP-generated UX events from the ROS thread.
        self.event_timer = self.create_timer(
            0.05,
            self.publish_pending_ux_events,
        )

        # ------------------------------------------------------------------
        # HTTP server
        # ------------------------------------------------------------------

        handler_class = type(
            "BoundUxApiRequestHandler",
            (UxApiRequestHandler,),
            {"adapter": self},
        )

        self.http_server = ThreadingHTTPServer(
            (
                self.http_host,
                self.http_port,
            ),
            handler_class,
        )

        self.http_server.daemon_threads = True

        self.http_thread = threading.Thread(
            target=self.http_server.serve_forever,
            name="medibot-ux-http-server",
            daemon=True,
        )

        self.http_thread.start()

        # ------------------------------------------------------------------
        # Startup information
        # ------------------------------------------------------------------

        self.get_logger().info(
            "UX/API adapter started."
        )

        self.get_logger().info(
            "Publishing external UX events on /medibot/ux_event"
        )

        self.get_logger().info(
            "Listening for Communication UX states on /medibot/ux_state"
        )

        self.get_logger().info(
            f"HTTP API listening on "
            f"{self.http_host}:{self.http_port}"
        )

        self.get_logger().info(
            "POST /route-requests -> destination_selected"
        )

        self.get_logger().info(
            "POST /visitor-ready -> visitor_ready"
        )

        self.get_logger().info(
            "POST /task-reset -> task_reset"
        )

        self.get_logger().info(
            "GET /ux-state/latest -> latest UX state"
        )

        self.get_logger().info(
            "HTTP task-changing requests wait for TaskCoordinator "
            "state confirmation before returning success."
        )

    def queue_ux_event(self, event_data):
        """
        Queue an HTTP-originated UX event for ROS publication.
        """

        self.pending_ux_events.put(event_data)

    def publish_pending_ux_events(self):
        """
        Publish HTTP-originated events onto /medibot/ux_event.
        """

        while True:
            try:
                event_data = (
                    self.pending_ux_events.get_nowait()
                )

            except queue.Empty:
                return

            msg = String()
            msg.data = json.dumps(event_data)

            self.ux_event_publisher.publish(msg)

            self.get_logger().info(
                "Published UX event on "
                f"/medibot/ux_event: {msg.data}"
            )

    def receive_ux_state(self, msg):
        """
        Store the latest TaskCoordinator UX state and wake HTTP requests
        waiting for a confirmed state transition.
        """

        try:
            state_data = json.loads(msg.data)

        except json.JSONDecodeError:
            self.get_logger().warn(
                "Ignoring invalid JSON on "
                f"/medibot/ux_state: {msg.data}"
            )
            return

        if not isinstance(state_data, dict):
            self.get_logger().warn(
                "Ignoring /medibot/ux_state because "
                "the message is not a JSON object."
            )
            return

        with self.state_condition:
            self.latest_ux_state = dict(state_data)
            self.state_condition.notify_all()

        self.get_logger().info(
            "Stored latest UX state: "
            f"{state_data.get('state', 'unknown')}"
        )

    def store_route_request(
        self,
        destination,
        user_id,
    ):
        """
        Retain a route request after TaskCoordinator acceptance is confirmed.
        """

        route_request = {
            "destination": destination,
            "user_id": user_id,
            "received_at": datetime.now(
                UTC
            ).isoformat(),
        }

        with self.state_condition:
            self.route_requests.append(
                route_request
            )

        return dict(route_request)

    def get_route_requests(self):
        with self.state_condition:
            return [
                dict(item)
                for item in self.route_requests
            ]

    def get_latest_route_request(self):
        with self.state_condition:
            if not self.route_requests:
                return None

            return dict(
                self.route_requests[-1]
            )

    def get_latest_ux_state(self):
        with self.state_condition:
            if self.latest_ux_state is None:
                return None

            return dict(
                self.latest_ux_state
            )

    def wait_for_ux_state(
        self,
        predicate,
        timeout_seconds=None,
    ):
        """
        Wait for TaskCoordinator to publish a UX state matching predicate.

        Returns a copy of the matching state, or None on timeout.
        """

        if timeout_seconds is None:
            timeout_seconds = self.task_response_timeout_seconds

        deadline = time.monotonic() + timeout_seconds

        with self.state_condition:
            while True:
                if (
                    self.latest_ux_state is not None
                    and predicate(self.latest_ux_state)
                ):
                    return dict(self.latest_ux_state)

                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    return None

                self.state_condition.wait(
                    timeout=remaining
                )

    def stop_http_server(self):
        """
        Stop the HTTP server cleanly.
        """

        if getattr(
            self,
            "http_server",
            None,
        ) is not None:
            self.http_server.shutdown()
            self.http_server.server_close()

        if getattr(
            self,
            "http_thread",
            None,
        ) is not None:
            self.http_thread.join(
                timeout=2.0
            )


class UxApiRequestHandler(
    BaseHTTPRequestHandler
):
    """
    HTTP endpoints used by the external UX.
    """

    adapter: UxApiAdapter

    def send_json(
        self,
        status,
        data,
    ):
        body = json.dumps(
            data
        ).encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )

        self.send_header(
            "Content-Length",
            str(len(body)),
        )

        self.send_header(
            "Access-Control-Allow-Origin",
            "*",
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS",
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type",
        )

        self.end_headers()

        self.wfile.write(body)

    def read_json_object(
        self,
        allow_empty=False,
    ):
        try:
            content_length = int(
                self.headers.get(
                    "Content-Length",
                    "0",
                )
            )

        except ValueError:
            self.send_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error":
                    "Invalid Content-Length header"
                },
            )
            return None

        if content_length == 0:
            if allow_empty:
                return {}

            self.send_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error":
                    "Request body must contain "
                    "a JSON object"
                },
            )
            return None

        try:
            payload = json.loads(
                self.rfile.read(
                    content_length
                )
            )

        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
        ):
            self.send_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error":
                    "Request body must be "
                    "valid JSON"
                },
            )
            return None

        if not isinstance(
            payload,
            dict,
        ):
            self.send_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error":
                    "JSON body must be an object"
                },
            )
            return None

        return payload

    def do_OPTIONS(self):
        """
        Allow browser/Flutter web requests.
        """

        self.send_response(
            HTTPStatus.NO_CONTENT
        )

        self.send_header(
            "Access-Control-Allow-Origin",
            "*",
        )

        self.send_header(
            "Access-Control-Allow-Methods",
            "GET, POST, OPTIONS",
        )

        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type",
        )

        self.send_header(
            "Content-Length",
            "0",
        )

        self.end_headers()

    def do_POST(self):
        path = urlparse(
            self.path
        ).path

        if path == "/route-requests":
            self.handle_route_request()
            return

        if path == "/visitor-ready":
            self.handle_visitor_ready()
            return

        if path == "/task-reset":
            self.handle_task_reset()
            return

        self.send_json(
            HTTPStatus.NOT_FOUND,
            {
                "error": "Not found"
            },
        )

    def handle_route_request(self):
        payload = self.read_json_object()

        if payload is None:
            return

        destination = payload.get(
            "destination"
        )

        user_id = payload.get(
            "user_id"
        )

        if (
            not isinstance(
                destination,
                str,
            )
            or not destination.strip()
        ):
            self.send_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error":
                    "destination must be a "
                    "non-empty string"
                },
            )
            return

        if (
            not isinstance(
                user_id,
                str,
            )
            or not user_id.strip()
        ):
            self.send_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error":
                    "user_id must be a "
                    "non-empty string"
                },
            )
            return

        destination = (
            destination
            .upper()
            .strip()
        )

        user_id = user_id.strip()

        if destination != "DIGITAL_LIBRARY":
            self.send_json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error":
                    "Unsupported destination for the current prototype",
                    "destination": destination,
                },
            )
            return

        with self.adapter.task_request_lock:
            current_state = (
                self.adapter.get_latest_ux_state()
            )

            if current_state is not None:
                current_stage = str(
                    current_state.get(
                        "current_stage",
                        "",
                    )
                ).strip()

                if current_stage != "waiting_for_destination":
                    self.send_json(
                        HTTPStatus.CONFLICT,
                        {
                            "accepted": False,
                            "error":
                            "A visitor task is already active",
                            "current_stage": current_stage,
                            "active_user_id":
                            current_state.get("user_id"),
                        },
                    )
                    return

            event_data = {
                "event": "destination_selected",
                "destination": destination,
                "user_id": user_id,
            }

            self.adapter.queue_ux_event(
                event_data
            )

            confirmed_state = (
                self.adapter.wait_for_ux_state(
                    lambda state: (
                        state.get("current_stage")
                        == "initial_guidance"
                        and state.get("destination")
                        == destination
                        and state.get("user_id")
                        == user_id
                    )
                )
            )

            if confirmed_state is None:
                self.send_json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {
                        "accepted": False,
                        "error":
                        "TaskCoordinator did not confirm the "
                        "route request in time",
                    },
                )
                return

            route_request = (
                self.adapter.store_route_request(
                    destination,
                    user_id,
                )
            )

            self.send_json(
                HTTPStatus.CREATED,
                {
                    "accepted": True,
                    **route_request,
                    "task_state":
                    confirmed_state.get("state"),
                },
            )

    def handle_visitor_ready(self):
        payload = self.read_json_object(
            allow_empty=True
        )

        if payload is None:
            return

        event_data = {
            "event": "visitor_ready"
        }

        user_id = payload.get(
            "user_id"
        )

        if user_id is not None:
            if (
                not isinstance(
                    user_id,
                    str,
                )
                or not user_id.strip()
            ):
                self.send_json(
                    HTTPStatus.BAD_REQUEST,
                    {
                        "error":
                        "user_id must be a "
                        "non-empty string "
                        "when supplied"
                    },
                )
                return

            user_id = user_id.strip()
            event_data["user_id"] = user_id

        with self.adapter.task_request_lock:
            current_state = (
                self.adapter.get_latest_ux_state()
            )

            if current_state is None:
                self.send_json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {
                        "accepted": False,
                        "error":
                        "No TaskCoordinator UX state is available yet",
                    },
                )
                return

            current_stage = str(
                current_state.get(
                    "current_stage",
                    "",
                )
            ).strip()

            if current_stage != "waiting_for_visitor_ready":
                self.send_json(
                    HTTPStatus.CONFLICT,
                    {
                        "accepted": False,
                        "error":
                        "visitor_ready is not valid at the current task stage",
                        "current_stage": current_stage,
                    },
                )
                return

            active_user_id = current_state.get(
                "user_id"
            )

            if (
                user_id is not None
                and active_user_id is not None
                and user_id != active_user_id
            ):
                self.send_json(
                    HTTPStatus.CONFLICT,
                    {
                        "accepted": False,
                        "error":
                        "visitor_ready user_id does not match the active visitor task",
                        "active_user_id": active_user_id,
                    },
                )
                return

            self.adapter.queue_ux_event(
                event_data
            )

            confirmed_state = (
                self.adapter.wait_for_ux_state(
                    lambda state: (
                        state.get("current_stage")
                        == "gem_route_requested"
                        and (
                            active_user_id is None
                            or state.get("user_id")
                            == active_user_id
                        )
                    )
                )
            )

            if confirmed_state is None:
                self.send_json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {
                        "accepted": False,
                        "error":
                        "TaskCoordinator did not confirm visitor_ready in time",
                    },
                )
                return

            self.send_json(
                HTTPStatus.OK,
                {
                    "accepted": True,
                    **event_data,
                    "task_state":
                    confirmed_state.get("state"),
                },
            )

    def handle_task_reset(self):
        """
        Reset the active visitor task through the existing TaskCoordinator
        task_reset event.

        The endpoint is intentionally idempotent. If Communication is already
        waiting for a new destination, HTTP 200 is returned without creating an
        unnecessary second reset event.
        """

        with self.adapter.task_request_lock:
            current_state = (
                self.adapter.get_latest_ux_state()
            )

            if (
                current_state is not None
                and current_state.get("current_stage")
                == "waiting_for_destination"
                and current_state.get("destination") is None
                and current_state.get("active_robot") is None
                and current_state.get("user_id") is None
            ):
                self.send_json(
                    HTTPStatus.OK,
                    {
                        "accepted": True,
                        "event": "task_reset",
                        "task_state":
                        "waiting_for_destination",
                        "already_reset": True,
                    },
                )
                return

            event_data = {
                "event": "task_reset"
            }

            self.adapter.queue_ux_event(
                event_data
            )

            confirmed_state = (
                self.adapter.wait_for_ux_state(
                    lambda state: (
                        state.get("current_stage")
                        == "waiting_for_destination"
                        and state.get("destination") is None
                        and state.get("active_robot") is None
                        and state.get("user_id") is None
                        and state.get("visitor_ready") is False
                    )
                )
            )

            if confirmed_state is None:
                self.send_json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {
                        "accepted": False,
                        "error":
                        "TaskCoordinator did not confirm task reset in time",
                    },
                )
                return

            self.send_json(
                HTTPStatus.OK,
                {
                    "accepted": True,
                    "event": "task_reset",
                    "task_state":
                    confirmed_state.get("state"),
                    "already_reset": False,
                },
            )

    def do_GET(self):
        path = urlparse(
            self.path
        ).path

        if path == "/health":
            self.send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service":
                    "medibot_ux_api_adapter",
                },
            )
            return

        if path == "/route-requests":
            self.send_json(
                HTTPStatus.OK,
                self.adapter.get_route_requests(),
            )
            return

        if path == "/route-requests/latest":
            latest = (
                self.adapter
                .get_latest_route_request()
            )

            if latest is None:
                self.send_json(
                    HTTPStatus.NOT_FOUND,
                    {
                        "error":
                        "No route requests yet"
                    },
                )
            else:
                self.send_json(
                    HTTPStatus.OK,
                    latest,
                )

            return

        if path == "/ux-state/latest":
            latest = (
                self.adapter
                .get_latest_ux_state()
            )

            if latest is None:
                self.send_json(
                    HTTPStatus.NOT_FOUND,
                    {
                        "error":
                        "No UX state has been "
                        "published yet"
                    },
                )
            else:
                self.send_json(
                    HTTPStatus.OK,
                    latest,
                )

            return

        self.send_json(
            HTTPStatus.NOT_FOUND,
            {
                "error": "Not found"
            },
        )

    def log_message(
        self,
        format,
        *args,
    ):
        print(
            f"{self.address_string()} - "
            f"{format % args}"
        )


def main(args=None):
    rclpy.init(args=args)

    node = None

    try:
        node = UxApiAdapter()

        rclpy.spin(node)

    except KeyboardInterrupt:
        if node is not None:
            node.get_logger().info(
                "UX/API adapter stopped."
            )

    finally:
        if node is not None:
            node.stop_http_server()
            node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()