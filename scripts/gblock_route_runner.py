#!/usr/bin/env python3

import argparse
import heapq
import json
import math
import socket
import threading
import time
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from irobot_create_msgs.action import DriveDistance, RotateAngle, WallFollow
from irobot_create_msgs.msg import (
    HazardDetection,
    HazardDetectionVector,
    IrIntensityVector,
)
from action_msgs.msg import GoalStatus


def normalize_angle(angle):
    while angle > math.pi:
        angle -= 2.0 * math.pi

    while angle < -math.pi:
        angle += 2.0 * math.pi

    return angle

def normalize_degrees(angle):
    """Normalise an angle to the range (-180, 180]."""

    while angle > 180.0:
        angle -= 360.0

    while angle <= -180.0:
        angle += 360.0

    return angle


def quaternion_to_yaw(x, y, z, w):
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    return math.atan2(siny_cosp, cosy_cosp)


class GBlockRouteRunner(Node):
    def __init__(self, namespace="/gem", map_file=None):
        super().__init__("gblock_route_runner")

        self.namespace = namespace.rstrip("/")

        self.abort_requested = False
        self.web_server = None
        self.web_thread = None

        # Phone page is status-only. It does not start or resume movement.
        self.route_status = "Initialising"
        self.current_location = "Not started"
        self.current_action = "Waiting"
        self.status_lock = threading.Lock()

        self.wall_engaged_seen = False
        self.last_wall_engaged = False

        self.cmd_pub = self.create_publisher(
            Twist,
            f"{self.namespace}/cmd_vel",
            10
        )

        self.rotate_client = ActionClient(
            self,
            RotateAngle,
            f"{self.namespace}/rotate_angle"
        )

        self.drive_action_client = ActionClient(
            self,
            DriveDistance,
            f"{self.namespace}/drive_distance"
        )

        # Latest built-in sensor readings.
        self.odom_x = None
        self.odom_y = None
        self.odom_yaw = None
        self.last_odom_time = None

        self.ir_values = {}
        self.have_ir = False
        self.ir_sample_id = 0
        self.ir_callback_time = None
        self.blocking_hazard = None
        self.last_cmd_publish_time = None
        self.last_cmd_command = None

        # Guarded odometry drive settings, based on initial sensor tests.
        self.drive_speed = 0.30
        self.side_threshold = 6
        self.heading_kp = 1.2
        self.cross_track_kp = 0.8
        self.wall_gain = 0.025

        # Side-wall IR is only a gentle correction.
        # It must not overpower heading/cross-track control.
        self.max_wall_correction = 0.05

        self.max_turn_correction = 0.25

        # Stop a straight guarded drive before a steering
        # divergence becomes unsafe.
        self.max_heading_error_deg = 20.0

        # Adaptive doorway settings. These are only used at the known
        # offset doorway after G1.14.
        self.doorway_approach_speed = 0.07
        self.doorway_cross_speed = 0.06
        self.doorway_trigger_threshold = 18
        self.doorway_clear_threshold = 10
        self.doorway_scan_step_deg = 2.0
        self.doorway_max_scan_deg = 30.0
        self.doorway_max_approach = 1.80
        self.doorway_cross_distance = 0.80

        # Global local-obstacle recovery. Every normal "drive" step uses
        # this behaviour when a persistent front obstacle is detected.
        # Gem first waits in case the obstacle is a person, then scans for
        # a nearby clear direction, makes a short low-speed bypass, restores
        # the original corridor heading, and continues the same drive.
        self.obstacle_wait_seconds = 2.5

        # Calibrated front-obstacle evidence.
        self.front_adjacent_threshold = 17

        self.front_single_thresholds = {
            "FL": 15,
            "FCL": 20,
            "FCR": 27,
            "FR": 15,
        }

        self.front_trigger_confirmations = 3
        self.front_clear_confirmations = 5

        # Time-based IR debounce. The Create 3 publishes IR at ~62.5 Hz,
        # so sample-count debounce alone can trigger in only ~30-50 ms.
        self.front_trigger_duration = 0.15
        self.front_clear_duration = 0.20

        self.obstacle_scan_step_deg = 5.0
        self.obstacle_max_scan_deg = 60.0
        self.obstacle_min_bypass_angle_deg = 15.0
        self.obstacle_min_clear_band_points = 2
        self.obstacle_bypass_distance = 0.20
        self.obstacle_rejoin_clear_threshold = 14
        self.obstacle_bypass_speed = 0.05
        self.obstacle_rejoin_delay = 0.60
        # Obstacle recoveries are not limited by a fixed count.
        # The normal guarded-drive timeout still prevents an
        # edge from recovering indefinitely.
        self.obstacle_retry_backup_distance = 0.15
        self.obstacle_retry_backup_speed = 0.05
        self.obstacle_max_backup_attempts = 3
        self.obstacle_retry_pause = 0.75
        self.action_front_threshold = 18
        self.action_front_confirmations = 3

        self.create_subscription(
            Odometry,
            f"{self.namespace}/odom",
            self.odom_callback,
            qos_profile_sensor_data
        )

        self.create_subscription(
            IrIntensityVector,
            f"{self.namespace}/ir_intensity",
            self.ir_callback,
            qos_profile_sensor_data
        )

        self.create_subscription(
            HazardDetectionVector,
            f"{self.namespace}/hazard_detection",
            self.hazard_callback,
            qos_profile_sensor_data
        )

        self.wall_client = ActionClient(
            self,
            WallFollow,
            f"{self.namespace}/wall_follow"
        )

        # Route definitions.
        # Distances are based on current G Block odometry measurements.
        self.routes = {
            "TURN_DRIVE_TEST": [
                ("say", "Starting short turn and guarded drive test."),
                ("turn_deg", -90),
                ("drive", 1.0),
                ("say", "Short test complete."),
            ],

            "G1.04": [
                ("say", "Starting route to G1.04."),
                ("turn_deg", -90),
                ("drive", 9.18),
                ("say", "Arrived near G1.04."),
            ],

            "SLIGHT_TURN": [
                ("say", "Starting route to the slight turn area."),
                ("turn_deg", -90),
                ("drive", 6.11),
                ("say", "Arrived near the slight turn area."),
            ],

            "ELEVATOR_1": [
                ("say", "Starting route to Elevator 1."),
                ("turn_deg", -90),
                ("drive", 6.11),
                ("turn_deg", 20),
                ("drive", 12.02),
                ("say", "Arrived near Elevator 1."),
            ],

            # Wall-follow calibration routes.
            "WALL_RIGHT_10": [
                ("say", "Starting right wall-follow test for 10 seconds."),
                ("wall_follow_right", 10),
                ("say", "Right wall-follow test complete."),
            ],

            "WALL_RIGHT_15": [
                ("say", "Starting right wall-follow test for 15 seconds."),
                ("wall_follow_right", 15),
                ("say", "Right wall-follow test complete."),
            ],

            "WALL_RIGHT_20": [
                ("say", "Starting right wall-follow test for 20 seconds."),
                ("wall_follow_right", 20),
                ("say", "Right wall-follow test complete."),
            ],

            "WALL_LEFT_15": [
                ("say", "Starting left wall-follow test for 15 seconds."),
                ("wall_follow_left", 15),
                ("say", "Left wall-follow test complete."),
            ],

            # Automatic full-lap route.
            # The phone page only displays route progress and provides Abort.
            "FULL_LAP_CHECKPOINT": [
                ("say", "Full G Block lap armed."),
                ("checkpoint", "IoT Lab start"),
                # Start outside IoT Lab, facing out of the lab.
                ("turn_deg", -90),
                ("drive", 9.18),      # IoT Lab -> G1.04
                ("say", "Reached G1.04 area."),
                ("checkpoint", "G1.04"),

                ("turn_deg", -90),
                ("drive", 7.17),      # G1.04 -> G1.08
                ("say", "Reached G1.08 area."),
                ("checkpoint", "G1.08"),

                ("drive_action", 8.49, 0.15),  # G1.08 -> G1.11
                ("say", "Reached G1.11 area."),
                ("checkpoint", "G1.11 / Colin's office"),

                ("turn_deg", -90),
                ("drive_action", 6.71, 0.15),  # G1.11 -> G1.14
                ("say", "Reached G1.14 area."),
                ("checkpoint", "G1.14"),

                # Normal drive with global obstacle recovery. The same
                # scan-and-bypass behaviour is available here and on every
                # other normal drive segment.
                ("doorway_right", 9.61),
                ("say", "Reached G1.23 area."),
                ("checkpoint", "G1.23"),

                ("turn_deg", -90),
                ("drive", 10.24),     # G1.23 -> G1.29
                ("say", "Reached G1.29 area."),
                ("checkpoint", "G1.29"),

                ("turn_deg", -90),
                ("drive", 6.62),      # G1.29 -> IoT Lab
                ("say", "Returned near IoT Lab."),

                ("say", "Automatic full lap complete."),
            ],

            # Start Gem at the G1.14 checkpoint, facing toward the
            # offset doorway. This tests only the doorway behaviour.
            "DOORWAY_RIGHT_TEST": [
                ("say", "Doorway test armed. Move Gem to G1.14 and face it toward the doorway."),
                ("checkpoint", "G1.14 doorway test start"),
                ("say", "Starting global obstacle-recovery test."),
                ("drive", 2.60),
                ("say", "Global obstacle-recovery test complete."),
            ],

            # Early wall-follow route prototype.
            # This is NOT final. It is for testing whether wall-follow can replace long blind drives.
            "WALL_ROUTE_TEST": [
                ("say", "Starting wall-follow route test."),

                # Start near a right-side wall, facing down the hallway.
                ("wall_follow_right", 15),
                ("checkpoint", "Check how far Gem moved during right wall-follow."),

                ("wall_follow_right", 15),
                ("checkpoint", "Check second wall-follow segment."),

                ("say", "Wall-follow route test complete."),
            ],

            "IOT_TO_G104_WALL_TEST": [
                ("say", "Starting IoT to G1.04 wall-assisted test."),

                # Start outside IoT Lab, facing out of the lab.
                ("turn_deg", -90),

                # Short blind drive to enter the hallway before wall-follow starts.
                ("drive", 1.5),

                # Now Gem should have a wall on one side.
                ("wall_follow_right", 15),

                ("checkpoint", "Check position after first wall-follow segment."),

                ("say", "IoT to G1.04 wall-assisted test complete."),
            ],
            "IOT_TO_G104_ACQUIRE_RIGHT": [
                ("say", "Starting IoT to G1.04 right wall acquisition test."),

                # Start outside IoT Lab, facing out of the lab.
                ("turn_deg", -90),

                # Move into the hallway.
                ("drive", 1.5),

                # Move more clearly toward the right wall.
                ("turn_deg", -35),
                ("drive", 0.6),
                ("turn_deg", 35),

                # Try wall-follow once Gem is closer and roughly parallel.
                ("wall_follow_right", 10),

                ("checkpoint", "Check whether right wall-follow engaged and how far Gem moved."),
                ("say", "Right wall acquisition test complete."),
            ],
            "IOT_TO_G104_ACQUIRE_LEFT": [
                ("say", "Starting IoT to G1.04 left wall acquisition test."),

                # Start outside IoT Lab, facing out of the lab.
                ("turn_deg", -90),

                # Move into the hallway.
                ("drive", 1.5),

                # Move slightly closer to the left wall.
                ("turn_deg", 15),
                ("drive", 0.4),
                ("turn_deg", -15),

                # Try wall-follow once Gem is closer and roughly parallel.
                ("wall_follow_left", 15),

                ("checkpoint", "Check whether left wall-follow engaged and how far Gem moved."),
                ("say", "Left wall acquisition test complete."),
            ],
        }
        self.load_topological_map(map_file)


    def load_topological_map(self, map_file=None):
        """Load nodes and weighted corridor connections from JSON."""

        if map_file is None:
            map_path = (
                Path(__file__).resolve().parents[1]
                / "config"
                / "gblock_topological_map.json"
            )
        else:
            map_path = Path(map_file).expanduser().resolve()

        if not map_path.is_file():
            raise FileNotFoundError(
                f"Topological map file not found: {map_path}"
            )

        with map_path.open("r", encoding="utf-8") as handle:
            map_data = json.load(handle)

        self.map_file = str(map_path)

        self.default_start_node = map_data.get(
            "default_start_node",
            "IOT_LAB",
        )

        self.default_start_heading_deg = float(
            map_data.get("default_start_heading_deg", 0.0)
        )

        self.node_labels = {
            node_id: node_data.get("label", node_id)
            for node_id, node_data in map_data["nodes"].items()
        }

        self.topological_graph = {
            node_id: {}
            for node_id in self.node_labels
        }

        def add_directed_edge(
            source,
            target,
            distance,
            heading_deg,
            mode,
            offset=None,
            recovery_side=None,
        ):
            if source not in self.topological_graph:
                raise ValueError(
                    f"Unknown edge source node: {source}"
                )

            if target not in self.topological_graph:
                raise ValueError(
                    f"Unknown edge destination node: {target}"
                )

            self.topological_graph[source][target] = {
                "distance": float(distance),
                "heading_deg": normalize_degrees(
                    float(heading_deg)
                ),
                "mode": mode,
                "offset": offset,
                "recovery_side": recovery_side,
            }

        enabled_edge_count = 0

        for edge in map_data["edges"]:
            if not edge.get("enabled", True):
                continue

            source = edge["from"]
            target = edge["to"]
            distance = float(edge["distance"])
            heading_deg = edge.get("heading_deg")

            if heading_deg is None:
                raise ValueError(
                    f"Enabled edge {source} -> {target} "
                    "does not have a heading_deg value."
                )

            mode = edge.get("mode", "guarded")
            offset = edge.get("offset")
            recovery_side = edge.get("recovery_side")

            add_directed_edge(
                source,
                target,
                distance,
                heading_deg,
                mode,
                offset,
                recovery_side,
            )
            enabled_edge_count += 1

            if edge.get("bidirectional", False):
                reverse_offset = offset
                reverse_recovery_side = recovery_side

                if offset == "right":
                    reverse_offset = "left"
                elif offset == "left":
                    reverse_offset = "right"

                if recovery_side == "right":
                    reverse_recovery_side = "left"
                elif recovery_side == "left":
                    reverse_recovery_side = "right"

                add_directed_edge(
                    target,
                    source,
                    distance,
                    normalize_degrees(
                        float(heading_deg) + 180.0
                    ),
                    mode,
                    reverse_offset,
                    reverse_recovery_side,
                )
                enabled_edge_count += 1

        requested_landmarks = map_data.get(
            "landmarks",
            [self.default_start_node],
        )

        self.landmarks = [
            node
            for node in requested_landmarks
            if node in self.topological_graph
        ]

        self.landmark_distances = {
            landmark: self.shortest_distances_from(landmark)
            for landmark in self.landmarks
        }

        self.get_logger().info(
            f"Loaded topological map from {map_path} "
            f"with {len(self.node_labels)} nodes and "
            f"{enabled_edge_count} directed edges."
        )

    def get_topological_nodes(self):
        return set(self.topological_graph)

    def shortest_distances_from(self, start):
        """Calculate minimum graph distance from one landmark."""

        frontier = [(0.0, start)]
        distances = {start: 0.0}

        while frontier:
            current_distance, current = heapq.heappop(frontier)

            if current_distance > distances[current]:
                continue

            for neighbour, edge in self.topological_graph[
                current
            ].items():
                candidate = (
                    current_distance
                    + edge["distance"]
                )

                if candidate >= distances.get(
                    neighbour,
                    math.inf,
                ):
                    continue

                distances[neighbour] = candidate

                heapq.heappush(
                    frontier,
                    (candidate, neighbour),
                )

        return distances

    def heuristic_cost(self, current, goal):
        """
        Landmark-based admissible A* heuristic.

        It uses only measured graph distances. No x/y coordinates or
        destination-specific routes are required.
        """

        lower_bounds = []

        for distances in self.landmark_distances.values():
            if current not in distances or goal not in distances:
                continue

            lower_bounds.append(
                abs(
                    distances[goal]
                    - distances[current]
                )
            )

        return max(lower_bounds, default=0.0)

    def a_star_path(self, start, goal):
        """Return the lowest-distance node path."""

        nodes = self.get_topological_nodes()

        if start not in nodes:
            self.get_logger().error(
                f"A* start node does not exist: {start}"
            )
            return None

        if goal not in nodes:
            self.get_logger().error(
                f"A* destination node does not exist: {goal}"
            )
            return None

        frontier = [
            (
                self.heuristic_cost(start, goal),
                0.0,
                start,
            )
        ]

        came_from = {start: None}
        best_cost = {start: 0.0}

        while frontier:
            _, current_cost, current = heapq.heappop(frontier)

            if current_cost > best_cost.get(
                current,
                math.inf,
            ):
                continue

            if current == goal:
                break

            for neighbour, edge in self.topological_graph[
                current
            ].items():
                new_cost = (
                    current_cost
                    + edge["distance"]
                )

                if new_cost >= best_cost.get(
                    neighbour,
                    math.inf,
                ):
                    continue

                best_cost[neighbour] = new_cost
                came_from[neighbour] = current

                estimated_total = (
                    new_cost
                    + self.heuristic_cost(
                        neighbour,
                        goal,
                    )
                )

                heapq.heappush(
                    frontier,
                    (
                        estimated_total,
                        new_cost,
                        neighbour,
                    ),
                )

        if goal not in came_from:
            self.get_logger().error(
                f"No route exists from {start} to {goal}."
            )
            return None

        path = []
        current = goal

        while current is not None:
            path.append(current)
            current = came_from[current]

        path.reverse()
        return path

    def build_planned_route(self, start, destination):
        """
        Convert the selected A* path into generic edge traversals.

        Distances, headings and movement modes all come from JSON.
        """

        node_path = self.a_star_path(
            start,
            destination,
        )

        if node_path is None:
            return None, None

        steps = [
            (
                "say",
                f"Starting planned route from "
                f"{self.node_labels[start]} to "
                f"{self.node_labels[destination]}.",
            ),
            (
                "checkpoint",
                self.node_labels[start],
            ),
        ]

        for current_node, next_node in zip(
            node_path,
            node_path[1:],
        ):
            edge = self.topological_graph[
                current_node
            ][next_node]

            steps.append(
                (
                    "navigate_edge",
                    current_node,
                    next_node,
                    edge["distance"],
                    edge["heading_deg"],
                    edge["mode"],
                    edge.get("offset"),
                    edge.get("recovery_side"),
                )
            )

            steps.append(
                (
                    "say",
                    f"Reached "
                    f"{self.node_labels[next_node]}.",
                )
            )

            steps.append(
                (
                    "checkpoint",
                    self.node_labels[next_node],
                )
            )

        steps.append(
            (
                "say",
                f"Arrived at "
                f"{self.node_labels[destination]}.",
            )
        )

        return steps, node_path



    def odom_callback(self, msg):
        self.odom_x = msg.pose.pose.position.x
        self.odom_y = msg.pose.pose.position.y
        self.last_odom_time = time.monotonic()

        q = msg.pose.pose.orientation
        self.odom_yaw = quaternion_to_yaw(q.x, q.y, q.z, q.w)

    def ir_callback(self, msg):
        values = {}

        for reading in msg.readings:
            name = (reading.header.frame_id or "unknown").split("/")[-1]
            values[name] = int(reading.value)

        self.ir_values = values
        self.have_ir = True
        self.ir_sample_id += 1
        self.ir_callback_time = time.monotonic()

    def hazard_callback(self, msg):
        blocking = []

        for detection in msg.detections:
            # BACKUP_LIMIT is ignored for these forward-only route drives.
            if detection.type == HazardDetection.BUMP:
                blocking.append("BUMP")
            elif detection.type == HazardDetection.CLIFF:
                blocking.append("CLIFF")
            elif detection.type == HazardDetection.STALL:
                blocking.append("STALL")
            elif detection.type == HazardDetection.WHEEL_DROP:
                blocking.append("WHEEL_DROP")

        self.blocking_hazard = blocking[0] if blocking else None

    def get_ir(self, name):
        return self.ir_values.get(name, 0)

    def wait_for_sensor_data(self, timeout=5.0):
        deadline = time.monotonic() + timeout

        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.1)

            if self.odom_yaw is not None and self.have_ir:
                return True

        self.get_logger().error(
            "Timed out waiting for odometry and IR data."
        )
        return False

    def status_name(self, status):
        names = {
            GoalStatus.STATUS_UNKNOWN: "UNKNOWN",
            GoalStatus.STATUS_ACCEPTED: "ACCEPTED",
            GoalStatus.STATUS_EXECUTING: "EXECUTING",
            GoalStatus.STATUS_CANCELING: "CANCELING",
            GoalStatus.STATUS_SUCCEEDED: "SUCCEEDED",
            GoalStatus.STATUS_CANCELED: "CANCELED",
            GoalStatus.STATUS_ABORTED: "ABORTED",
        }
        return names.get(status, f"STATUS_{status}")

    def stop(self, reason=None):
        msg = Twist()
        msg.linear.x = 0.0
        msg.angular.z = 0.0

        if reason is not None:
            self.get_logger().warn(
                f"STOP COMMAND reason={reason} "
                f"time={time.monotonic():.6f}"
            )

        for _ in range(5):
            self.publish_cmd_vel(
                msg,
                source=(
                    f"stop:{reason}"
                    if reason is not None
                    else "stop"
                ),
            )
            time.sleep(0.02)

    def publish_cmd_vel(self, command, source="drive"):
        now = time.monotonic()
        current_command = (
            float(command.linear.x),
            float(command.angular.z),
        )

        if self.last_cmd_publish_time is not None:
            dt = now - self.last_cmd_publish_time

            if dt > 0.20:
                self.get_logger().warn(
                    f"CMD_VEL GAP WARNING: dt={dt:.3f} sec | "
                    f"last_command={self.last_cmd_command} | "
                    f"current_command={current_command} | "
                    f"source={source}"
                )

        self.cmd_pub.publish(command)
        self.last_cmd_publish_time = now
        self.last_cmd_command = current_command

    def get_ip_address(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        except Exception:
            ip = "localhost"
        finally:
            s.close()

        return ip

    def update_phone_status(self, route_status=None, location=None, action=None):
        """Update the information shown on the phone status page."""

        with self.status_lock:
            if route_status is not None:
                self.route_status = route_status
            if location is not None:
                self.current_location = location
            if action is not None:
                self.current_action = action

    def get_phone_status(self):
        if self.last_odom_time is None:
            robot_link = "Waiting for odometry"
            odom_age = None
        else:
            odom_age = max(0.0, time.monotonic() - self.last_odom_time)
            if odom_age <= 1.0:
                robot_link = "Connected"
            else:
                robot_link = f"Odometry stale ({odom_age:.1f} s)"

        with self.status_lock:
            return {
                "route_status": self.route_status,
                "location": self.current_location,
                "action": self.current_action,
                "robot_link": robot_link,
                "odom_age": odom_age,
                "aborted": self.abort_requested,
            }

    def start_phone_checkpoint_server(self, port=8081):
        if self.web_server is not None:
            return

        node = self

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Gem Route Status</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {
                    font-family: Arial, sans-serif;
                    text-align: center;
                    margin: 24px;
                    background: #f3f4f6;
                }
                h1 {
                    font-size: 28px;
                }
                .card {
                    background: white;
                    margin: 14px auto;
                    padding: 18px;
                    max-width: 420px;
                    border-radius: 12px;
                    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
                }
                .label {
                    font-size: 15px;
                    color: #555;
                    margin-bottom: 6px;
                }
                .value {
                    font-size: 24px;
                    font-weight: bold;
                }
                button {
                    font-size: 24px;
                    padding: 22px;
                    margin: 18px;
                    width: 280px;
                    border-radius: 12px;
                    border: 1px solid #333;
                }
                .abort {
                    background: #ffcccc;
                }
            </style>
        </head>
        <body>
            <h1>Gem Route Status</h1>

            <div class="card">
                <div class="label">Route status</div>
                <div class="value" id="route_status">Loading...</div>
            </div>

            <div class="card">
                <div class="label">Current location</div>
                <div class="value" id="location">Loading...</div>
            </div>

            <div class="card">
                <div class="label">Current action</div>
                <div class="value" id="action">Loading...</div>
            </div>

            <div class="card">
                <div class="label">Robot link</div>
                <div class="value" id="robot_link">Loading...</div>
            </div>

            <button class="abort" onclick="abortRoute()">
                Abort / Stop
            </button>

            <script>
                function updateStatus() {
                    fetch('/status', {cache: 'no-store'})
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById('route_status').textContent = data.route_status;
                            document.getElementById('location').textContent = data.location;
                            document.getElementById('action').textContent = data.action;
                            document.getElementById('robot_link').textContent = data.robot_link;
                        })
                        .catch(() => {
                            document.getElementById('route_status').textContent = 'Connection lost';
                        });
                }

                function abortRoute() {
                    fetch('/abort').then(() => updateStatus());
                }

                updateStatus();
                setInterval(updateStatus, 500);
            </script>
        </body>
        </html>
        """

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path.startswith("/status"):
                    payload = json.dumps(node.get_phone_status()).encode()
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return

                if self.path.startswith("/abort") or self.path.startswith("/stop"):
                    node.abort_requested = True
                    node.update_phone_status(
                        route_status="Aborted",
                        action="Stopping",
                    )
                    node.stop()
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"Abort pressed")
                    return

                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(html.encode())

            def log_message(self, format, *args):
                return

        self.web_server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
        self.web_thread = threading.Thread(
            target=self.web_server.serve_forever,
            daemon=True
        )
        self.web_thread.start()

        ip = self.get_ip_address()
        self.get_logger().info(f"Phone route status page: http://{ip}:{port}")

    def shutdown_phone_checkpoint_server(self):
        if self.web_server is not None:
            self.web_server.shutdown()
            self.web_server.server_close()
            self.web_server = None

    def report_checkpoint(self, text):
        """Report a checkpoint without stopping or waiting for phone input."""

        self.current_location = text
        self.update_phone_status(
            route_status="Running",
            location=text,
            action="Checkpoint reached",
        )
        self.get_logger().info(f"STATUS CHECKPOINT: {text}")
        return not self.abort_requested

    def wait_for_servers(self):
        self.get_logger().info("Waiting for Create 3 action servers...")

        rotate_ready = self.rotate_client.wait_for_server(timeout_sec=10.0)
        drive_ready = self.drive_action_client.wait_for_server(timeout_sec=10.0)
        wall_ready = self.wall_client.wait_for_server(timeout_sec=10.0)

        if not rotate_ready:
            raise RuntimeError(
                f"Rotate action server not available: "
                f"{self.namespace}/rotate_angle"
            )

        if not drive_ready:
            raise RuntimeError(
                f"DriveDistance action server not available: "
                f"{self.namespace}/drive_distance"
            )

        if not wall_ready:
            raise RuntimeError(
                f"Wall-follow action server not available: "
                f"{self.namespace}/wall_follow"
            )

        self.get_logger().info("Action servers ready.")

    def rotate_degrees(self, degrees, speed=0.25):
        angle_rad = math.radians(degrees)

        self.get_logger().info(
            f"Rotating {degrees:.1f} degrees "
            f"({angle_rad:.3f} rad)."
        )

        if not self.rotate_client.wait_for_server(
            timeout_sec=8.0
        ):
            self.get_logger().error(
                "Rotate action server unavailable."
            )
            self.stop()
            return False

        goal = RotateAngle.Goal()
        goal.angle = angle_rad
        goal.max_rotation_speed = speed

        send_future = self.rotate_client.send_goal_async(
            goal
        )

        accept_deadline = time.monotonic() + 8.0

        while rclpy.ok() and not send_future.done():
            if self.abort_requested:
                self.get_logger().error(
                    "Rotation aborted before goal acceptance."
                )
                self.stop()
                return False

            if time.monotonic() >= accept_deadline:
                self.get_logger().error(
                    "Timed out waiting for rotate goal "
                    "acceptance."
                )
                self.stop()
                return False

            rclpy.spin_once(self, timeout_sec=0.1)

        goal_handle = send_future.result()

        if (
            goal_handle is None
            or not goal_handle.accepted
        ):
            self.get_logger().error(
                "Rotate goal rejected."
            )
            self.stop()
            return False

        result_future = goal_handle.get_result_async()

        expected_time = (
            abs(angle_rad) / max(speed, 0.05)
        )
        result_deadline = (
            time.monotonic()
            + max(12.0, expected_time + 8.0)
        )

        while rclpy.ok() and not result_future.done():
            if self.abort_requested:
                self.get_logger().error(
                    "Rotation aborted."
                )
                goal_handle.cancel_goal_async()
                self.stop()
                return False

            if time.monotonic() >= result_deadline:
                self.get_logger().error(
                    "Timed out waiting for rotate result."
                )
                goal_handle.cancel_goal_async()
                self.stop()
                return False

            rclpy.spin_once(self, timeout_sec=0.1)

        result_response = result_future.result()

        if result_response is None:
            self.get_logger().error(
                "No rotate result received."
            )
            self.stop()
            return False

        status = result_response.status

        self.stop()
        time.sleep(0.5)

        if status != GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().error(
                f"Rotate did not succeed. "
                f"Status: {self.status_name(status)}"
            )
            return False

        self.get_logger().info("Rotate complete.")
        return True


    def drive_distance_action(
        self,
        distance,
        speed=0.15,
        recovery_count=0,
    ):
        """
        Use Create 3 DriveDistance with proactive IR monitoring.

        If a persistent front obstacle is detected, cancel the onboard
        action, run the existing scan-and-bypass recovery, then continue
        only the remaining mapped distance.
        """

        if not self.wait_for_sensor_data():
            return False

        start_x = self.odom_x
        start_y = self.odom_y
        start_yaw = self.odom_yaw

        self.get_logger().info(
            f"Built-in DriveDistance: {distance:.2f} m "
            f"at {speed:.2f} m/s."
        )

        goal = DriveDistance.Goal()
        goal.distance = float(distance)
        goal.max_translation_speed = float(speed)

        send_future = self.drive_action_client.send_goal_async(goal)

        # Do not wait forever for the goal to be accepted.
        accept_deadline = time.monotonic() + 10.0

        while rclpy.ok() and not send_future.done():
            if self.abort_requested:
                self.get_logger().error(
                    "DriveDistance aborted before goal acceptance."
                )
                self.stop()
                return False

            if time.monotonic() >= accept_deadline:
                self.get_logger().error(
                    "Timed out waiting for DriveDistance goal acceptance."
                )
                self.stop()
                return False

            rclpy.spin_once(self, timeout_sec=0.1)

        goal_handle = send_future.result()

        if goal_handle is None or not goal_handle.accepted:
            self.get_logger().error("DriveDistance goal rejected.")
            self.stop()
            return False

        result_future = goal_handle.get_result_async()

        # Give the action plenty of time, but do not allow an infinite wait.
        result_deadline = time.monotonic() + max(
            30.0,
            (abs(distance) / max(abs(speed), 0.01)) * 4.0,
        )

        last_status_update = 0.0
        target_reached_since = None
        distance_tolerance = 0.10
        front_high_count = 0

        while rclpy.ok() and not result_future.done():
            rclpy.spin_once(self, timeout_sec=0.05)

            if self.abort_requested:
                self.get_logger().error(
                    "DriveDistance canceled from phone."
                )
                goal_handle.cancel_goal_async()
                self.stop()
                return False

            if self.blocking_hazard is not None:
                self.get_logger().error(
                    f"DriveDistance stopped by hazard: "
                    f"{self.blocking_hazard}"
                )
                goal_handle.cancel_goal_async()
                self.stop()
                return False

            dx = self.odom_x - start_x
            dy = self.odom_y - start_y

            # Distance travelled along the original corridor heading.
            progress = (
                dx * math.cos(start_yaw)
                + dy * math.sin(start_yaw)
            )

            # Monitor all four forward IR sensors while the onboard
            # DriveDistance action controls smooth forward movement.
            front_value = self.front_ir_value(
                center_only=False
            )

            if front_value >= self.action_front_threshold:
                front_high_count += 1
            else:
                front_high_count = 0

            if (
                front_high_count
                >= self.action_front_confirmations
            ):
                self.get_logger().warn(
                    f"Persistent front obstacle during "
                    f"DriveDistance at "
                    f"{progress:.2f}/{distance:.2f} m. "
                    f"IR reading={front_value}."
                )

                # Stop the onboard action before running the local
                # scan-and-bypass controller.
                cancel_future = (
                    goal_handle.cancel_goal_async()
                )

                rclpy.spin_until_future_complete(
                    self,
                    cancel_future,
                    timeout_sec=2.0,
                )

                cancel_deadline = (
                    time.monotonic() + 5.0
                )

                while (
                    rclpy.ok()
                    and not result_future.done()
                    and time.monotonic()
                    < cancel_deadline
                ):
                    rclpy.spin_once(
                        self,
                        timeout_sec=0.05,
                    )

                self.stop()

                if not result_future.done():
                    self.get_logger().error(
                        "DriveDistance did not finish "
                        "cancelling."
                    )
                    return False

                if not self.recover_from_front_obstacle():
                    return False

                # Calculate how much mapped forward distance was
                # completed, including the diagonal bypass.
                dx = self.odom_x - start_x
                dy = self.odom_y - start_y

                recovered_progress = (
                    dx * math.cos(start_yaw)
                    + dy * math.sin(start_yaw)
                )

                remaining = max(
                    0.0,
                    distance - recovered_progress,
                )

                if remaining <= distance_tolerance:
                    self.get_logger().info(
                        "Obstacle bypass completed the "
                        "drive segment."
                    )
                    return True

                self.get_logger().info(
                    f"Obstacle bypass complete. "
                    f"Continuing remaining "
                    f"{remaining:.2f} m with "
                    "DriveDistance."
                )

                return self.drive_distance_action(
                    remaining,
                    speed=speed,
                    recovery_count=(
                        recovery_count + 1
                    ),
                )

            now = time.monotonic()

            # Update the phone page while the action is running.
            if now - last_status_update >= 0.5:
                last_status_update = now

                shown_progress = min(
                    max(progress, 0.0),
                    distance,
                )

                self.update_phone_status(
                    route_status="Running",
                    action=(
                        f"Driving {shown_progress:.2f}/"
                        f"{distance:.2f} m"
                    ),
                )

            odom_age = (
                math.inf
                if self.last_odom_time is None
                else now - self.last_odom_time
            )

            # Gem has physically reached the requested distance, but the
            # Create 3 action result may have been lost.
            if (
                progress >= distance - distance_tolerance
                and odom_age <= 1.0
            ):
                if target_reached_since is None:
                    target_reached_since = now

                elif now - target_reached_since >= 0.75:
                    self.get_logger().warn(
                        f"Odometry reached DriveDistance target "
                        f"({progress:.2f}/{distance:.2f} m), but the "
                        "action result did not arrive. Continuing route."
                    )

                    goal_handle.cancel_goal_async()
                    self.stop()
                    time.sleep(0.5)
                    return True

            else:
                target_reached_since = None

            if now >= result_deadline:
                self.get_logger().error(
                    f"DriveDistance timed out at "
                    f"{progress:.2f}/{distance:.2f} m."
                )

                goal_handle.cancel_goal_async()
                self.stop()

                self.update_phone_status(
                    route_status="Stopped",
                    action=(
                        f"Drive timed out at "
                        f"{progress:.2f}/{distance:.2f} m"
                    ),
                )

                return False

        result_response = result_future.result()

        if result_response is None:
            self.get_logger().error(
                "No DriveDistance result received."
            )
            self.stop()
            return False

        status = result_response.status

        self.stop()
        time.sleep(0.5)

        if status != GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().error(
                f"DriveDistance did not succeed. "
                f"Status: {self.status_name(status)}"
            )
            return False

        self.get_logger().info(
            "Built-in DriveDistance complete."
        )
        return True

    def front_ir_snapshot(self):
        """Return one consistent snapshot of the four forward IR channels."""

        values = self.ir_values.copy()

        return {
            "FL": values.get(
                "ir_intensity_front_left",
                0,
            ),
            "FCL": values.get(
                "ir_intensity_front_center_left",
                0,
            ),
            "FCR": values.get(
                "ir_intensity_front_center_right",
                0,
            ),
            "FR": values.get(
                "ir_intensity_front_right",
                0,
            ),
        }

    def front_ir_value(
        self,
        center_only=False,
        readings=None,
    ):
        """Return the maximum value from one forward IR snapshot."""

        if readings is None:
            readings = self.front_ir_snapshot()

        names = (
            ("FCL", "FCR")
            if center_only
            else ("FL", "FCL", "FCR", "FR")
        )

        return max(
            readings[name]
            for name in names
        )

    def front_obstacle_evidence(
        self,
        readings=None,
        center_only=False,
    ):
        """
        Return calibrated obstacle evidence for one IR snapshot.

        An obstacle is indicated by either:
        - a moderately high adjacent sensor pair; or
        - a sensor-specific strong return.
        """

        if readings is None:
            readings = self.front_ir_snapshot()

        active_names = (
            ("FCL", "FCR")
            if center_only
            else ("FL", "FCL", "FCR", "FR")
        )

        single_hits = [
            name
            for name in active_names
            if (
                readings[name]
                >= self.front_single_thresholds[name]
            )
        ]

        pairs = (
            (("FCL", "FCR"),)
            if center_only
            else (
                ("FL", "FCL"),
                ("FCL", "FCR"),
                ("FCR", "FR"),
            )
        )

        adjacent_hits = [
            f"{left}+{right}"
            for left, right in pairs
            if (
                readings[left]
                >= self.front_adjacent_threshold
                and readings[right]
                >= self.front_adjacent_threshold
            )
        ]

        return (
            bool(single_hits or adjacent_hits),
            single_hits,
            adjacent_hits,
        )

    def sample_front_ir_snapshot(
        self,
        samples=5,
    ):
        """Return per-sensor medians from several IR samples."""

        collected = {
            "FL": [],
            "FCL": [],
            "FCR": [],
            "FR": [],
        }

        for _ in range(samples):
            rclpy.spin_once(
                self,
                timeout_sec=0.06,
            )

            readings = self.front_ir_snapshot()

            for name in collected:
                collected[name].append(
                    readings[name]
                )

        medians = {}

        for name, values in collected.items():
            values.sort()
            medians[name] = (
                values[len(values) // 2]
            )

        return medians

    def sample_front_ir(
        self,
        samples=5,
        center_only=True,
    ):
        """Take several IR samples and return the median value."""

        values = []

        for _ in range(samples):
            rclpy.spin_once(
                self,
                timeout_sec=0.06,
            )

            values.append(
                self.front_ir_value(
                    center_only=center_only
                )
            )

        values.sort()

        return values[
            len(values) // 2
        ]

    def approach_until_front_or_distance(
        self,
        max_distance,
        speed,
        trigger_threshold,
    ):
        """
        Approach a known doorway while holding the current heading.

        Returns (result, progress), where result is either "clear" when
        max_distance was completed or "blocked" when a persistent front
        return was detected. Errors return ("error", progress).
        """

        if not self.wait_for_sensor_data():
            return "error", 0.0

        start_x = self.odom_x
        start_y = self.odom_y
        target_yaw = self.odom_yaw

        front_high_count = 0
        progress = 0.0
        last_log = 0.0
        deadline = time.monotonic() + max(
            15.0,
            (max_distance / max(speed, 0.01)) * 3.0,
        )

        self.get_logger().info(
            f"Adaptive doorway approach: up to {max_distance:.2f} m "
            f"at {speed:.2f} m/s."
        )

        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)

            if self.abort_requested:
                self.get_logger().error("Doorway approach aborted from phone.")
                self.stop()
                return "error", progress

            if self.blocking_hazard is not None:
                self.get_logger().error(
                    f"Doorway approach stopped by hazard: "
                    f"{self.blocking_hazard}"
                )
                self.stop()
                return "error", progress

            if (
                self.odom_x is None
                or self.odom_y is None
                or self.odom_yaw is None
            ):
                continue

            dx = self.odom_x - start_x
            dy = self.odom_y - start_y

            progress = (
                dx * math.cos(target_yaw)
                + dy * math.sin(target_yaw)
            )

            lateral_error = (
                -dx * math.sin(target_yaw)
                + dy * math.cos(target_yaw)
            )

            heading_error = normalize_angle(target_yaw - self.odom_yaw)

            if progress >= max_distance:
                self.stop()
                self.get_logger().info(
                    "Doorway path stayed clear; continuing without a scan."
                )
                return "clear", progress

            front_value = self.front_ir_value(center_only=True)

            if front_value >= trigger_threshold:
                front_high_count += 1
            else:
                front_high_count = 0

            if front_high_count >= 3:
                self.stop()
                self.get_logger().warn(
                    f"Doorway obstruction detected after {progress:.2f} m. "
                    f"Centre-front IR={front_value}."
                )
                return "blocked", max(0.0, progress)

            left_value = max(
                self.get_ir("ir_intensity_side_left"),
                self.get_ir("ir_intensity_left"),
            )
            right_value = self.get_ir("ir_intensity_right")

            angular_command = (
                self.heading_kp * heading_error
                - self.cross_track_kp * lateral_error
            )

            if right_value > self.side_threshold:
                angular_command += self.wall_gain * (
                    right_value - self.side_threshold
                )

            if left_value > self.side_threshold:
                angular_command -= self.wall_gain * (
                    left_value - self.side_threshold
                )

            angular_command = max(
                -0.15,
                min(0.15, angular_command),
            )

            command = Twist()
            command.linear.x = speed
            command.angular.z = angular_command
            self.cmd_pub.publish(command)

            now = time.monotonic()
            if now - last_log >= 0.5:
                last_log = now
                self.get_logger().info(
                    f"door approach={progress:.2f}/{max_distance:.2f} m | "
                    f"centre-front={front_value} | "
                    f"heading={math.degrees(heading_error):+.2f} deg | "
                    f"turn={angular_command:+.3f} rad/s"
                )

        self.stop()
        self.get_logger().error("Adaptive doorway approach timed out.")
        return "error", progress

    def navigate_right_offset_doorway(self, total_distance):
        """
        Pass the known slightly-right offset doorway after G1.14.

        Gem approaches slowly. If the opening is already aligned, it
        continues straight. Otherwise it scans right in small increments,
        crosses the opening, restores the original corridor heading, and
        then drives the remaining segment distance.
        """

        result, approach_progress = self.approach_until_front_or_distance(
            max_distance=self.doorway_max_approach,
            speed=self.doorway_approach_speed,
            trigger_threshold=self.doorway_trigger_threshold,
        )

        if result == "error":
            return False

        scanned_angle = 0.0
        crossing_projection = 0.0

        if result == "blocked":
            self.get_logger().warn(
                "Scanning right for the doorway opening."
            )

            consecutive_clear = 0
            opening_found = False

            while scanned_angle < self.doorway_max_scan_deg:
                if self.abort_requested:
                    self.get_logger().error("Doorway scan aborted from phone.")
                    self.stop()
                    return False

                if not self.rotate_degrees(-self.doorway_scan_step_deg):
                    return False

                scanned_angle += self.doorway_scan_step_deg
                centre_front = self.sample_front_ir(
                    samples=5,
                    center_only=True,
                )

                self.get_logger().info(
                    f"Doorway scan: right {scanned_angle:.1f} deg | "
                    f"centre-front IR={centre_front}"
                )

                if centre_front <= self.doorway_clear_threshold:
                    consecutive_clear += 1
                else:
                    consecutive_clear = 0

                # Two adjacent clear scan positions reduce the chance of
                # selecting one noisy reading or only seeing the door edge.
                if consecutive_clear >= 2:
                    opening_found = True
                    break

            if not opening_found:
                self.get_logger().error(
                    f"No clear doorway opening found within "
                    f"{self.doorway_max_scan_deg:.0f} degrees to the right."
                )
                self.stop()
                return False

            self.get_logger().info(
                f"Doorway opening found at approximately "
                f"{scanned_angle:.1f} degrees right."
            )

            if not self.drive_distance(
                self.doorway_cross_distance,
                speed=self.doorway_cross_speed,
                allow_obstacle_recovery=False,
                use_side_wall_correction=False,
                restricted_center_only=True,
            ):
                return False

            crossing_projection = (
                self.doorway_cross_distance
                * math.cos(math.radians(scanned_angle))
            )

            if not self.rotate_degrees(scanned_angle):
                return False

            self.get_logger().info(
                "Doorway crossed; original corridor heading restored."
            )

        remaining_distance = max(
            0.0,
            total_distance - approach_progress - crossing_projection,
        )

        self.get_logger().info(
            f"Adaptive doorway segment remaining distance: "
            f"{remaining_distance:.2f} m."
        )

        if remaining_distance > 0.05:
            return self.drive_distance(remaining_distance)

        return True

    def reverse_for_obstacle_retry(self):
        """Back away slightly to create room for another local scan."""

        if not self.wait_for_sensor_data():
            return False

        start_x = self.odom_x
        start_y = self.odom_y

        self.get_logger().warn(
            f"Backing up "
            f"{self.obstacle_retry_backup_distance:.2f} m "
            "before retrying obstacle avoidance."
        )

        while rclpy.ok():
            rclpy.spin_once(self, timeout_sec=0.05)

            if self.abort_requested:
                self.stop()
                return False

            # BUMP is allowed while reversing away from contact.
            # These hazards still stop all movement.
            if self.blocking_hazard in (
                "CLIFF",
                "STALL",
                "WHEEL_DROP",
            ):
                self.get_logger().error(
                    f"Reverse retry stopped by hazard: "
                    f"{self.blocking_hazard}"
                )
                self.stop()
                return False

            travelled = math.hypot(
                self.odom_x - start_x,
                self.odom_y - start_y,
            )

            if (
                travelled
                >= self.obstacle_retry_backup_distance
            ):
                self.stop()

                clear_deadline = time.monotonic() + 1.5

                while (
                    rclpy.ok()
                    and self.blocking_hazard == "BUMP"
                    and time.monotonic() < clear_deadline
                ):
                    rclpy.spin_once(
                        self,
                        timeout_sec=0.05,
                    )

                time.sleep(0.25)
                return True

            command = Twist()
            command.linear.x = (
                -self.obstacle_retry_backup_speed
            )
            command.angular.z = 0.0
            self.cmd_pub.publish(command)

        self.stop()
        return False

    def wait_for_front_to_clear(self):
        """
        Wait briefly for a temporary obstacle, such as a person, to move.

        Returns True when the path becomes consistently clear. Returns
        False when the obstacle remains or the route is aborted.
        """

        self.stop()
        deadline = time.monotonic() + self.obstacle_wait_seconds
        clear_count = 0
        last_clear_eval_ir_sample_id = None
        clear_since = None

        self.get_logger().warn(
            f"Front obstacle detected. Waiting "
            f"{self.obstacle_wait_seconds:.1f} seconds for it to clear."
        )

        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.10)

            if self.abort_requested:
                self.get_logger().error(
                    "Obstacle wait aborted from phone."
                )
                return False

            if self.blocking_hazard in (
                "CLIFF",
                "STALL",
                "WHEEL_DROP",
            ):
                self.get_logger().error(
                    f"Obstacle wait stopped by hazard: "
                    f"{self.blocking_hazard}"
                )
                return False

            if self.blocking_hazard == "BUMP":
                return False

            current_ir_sample_id = self.ir_sample_id

            if current_ir_sample_id == last_clear_eval_ir_sample_id:
                time.sleep(0.08)
                continue

            last_clear_eval_ir_sample_id = current_ir_sample_id
            readings = self.front_ir_snapshot()

            blocked, _, _ = (
                self.front_obstacle_evidence(
                    readings=readings,
                    center_only=False,
                )
            )

            clear_now = time.monotonic()

            if blocked:
                clear_count = 0
                clear_since = None
            else:
                clear_count += 1

                if clear_since is None:
                    clear_since = clear_now

                clear_for = clear_now - clear_since

                if (
                    clear_for
                    >= self.front_clear_duration
                ):
                    self.get_logger().info(
                        f"Front path continuously clear for "
                        f"{clear_for:.3f} sec across "
                        f"{clear_count} distinct IR samples; "
                        "resuming the original drive. "
                        f"ir_sample_id={current_ir_sample_id}"
                    )
                    return True

            time.sleep(0.08)

        self.get_logger().warn(
            "Obstacle remained in place; starting a local opening scan."
        )
        return False

    def preferred_scan_directions(self):
        """
        Decide which side to scan first from the current IR pattern.

        A stronger return on the left suggests trying right first, and a
        stronger return on the right suggests trying left first.
        """

        front_left = max(
            self.get_ir("ir_intensity_front_left"),
            self.get_ir("ir_intensity_front_center_left"),
        )
        front_right = max(
            self.get_ir("ir_intensity_front_center_right"),
            self.get_ir("ir_intensity_front_right"),
        )

        if front_left > front_right:
            return (-1, 1)   # right, then left

        if front_right > front_left:
            return (1, -1)   # left, then right

        side_left = max(
            self.get_ir("ir_intensity_side_left"),
            self.get_ir("ir_intensity_left"),
        )
        side_right = max(
            self.get_ir("ir_intensity_side_right"),
            self.get_ir("ir_intensity_right"),
        )

        if side_left >= side_right:
            return (-1, 1)

        return (1, -1)

    def scan_for_clear_opening(self, direction):
        """
        Scan one side in small increments.

        direction = -1 scans right.
        direction = +1 scans left.

        The robot remains pointing at the returned signed angle when an
        opening is found. If no opening is found, it remains at the maximum
        scan angle so the caller can restore the original heading.
        """

        side_name = "right" if direction < 0 else "left"
        scanned = 0.0
        consecutive_clear = 0

        self.get_logger().warn(
            f"Scanning {side_name} for a clear local path."
        )

        while scanned < self.obstacle_max_scan_deg:
            if self.abort_requested:
                self.get_logger().error(
                    "Obstacle scan aborted from phone."
                )
                return None

            step = min(
                self.obstacle_scan_step_deg,
                self.obstacle_max_scan_deg - scanned,
            )

            if not self.rotate_degrees(direction * step):
                return None

            scanned += step
            signed_angle = direction * scanned

            readings = (
                self.sample_front_ir_snapshot(
                    samples=5,
                )
            )

            centre_front = self.front_ir_value(
                center_only=True,
                readings=readings,
            )

            (
                blocked,
                single_hits,
                adjacent_hits,
            ) = self.front_obstacle_evidence(
                readings=readings,
                center_only=True,
            )

            self.get_logger().info(
                f"Obstacle scan: "
                f"{side_name} "
                f"{scanned:.1f} deg | "
                f"centre-front IR="
                f"{centre_front} | "
                f"IR={readings} | "
                f"blocked={blocked} | "
                f"single="
                f"{single_hits or '-'} | "
                f"adjacent="
                f"{adjacent_hits or '-'}"
            )

            if blocked:
                consecutive_clear = 0
            else:
                consecutive_clear += 1

            # Two adjacent clear positions reduce false positives caused by
            # a single noisy reading or looking only along an object edge.
            # Reject shallow openings that provide very little lateral
            # clearance during the short bypass.
            if (
                consecutive_clear >= 2
                and scanned
                >= self.obstacle_min_bypass_angle_deg
            ):
                self.get_logger().info(
                    f"Clear local path found at approximately "
                    f"{abs(signed_angle):.1f} degrees {side_name}."
                )
                return signed_angle

        return None

    def recover_from_front_obstacle(
        self,
        preferred_side=None,
    ):
        """
        Use the limited recovery behaviour from the known-good
        G Block runner while retaining the map's preferred side.

        The robot waits briefly, scans one side at a time, uses
        the first confirmed clear opening, performs one short
        bypass, and restores the original corridor heading.
        """

        self.stop()

        if self.wait_for_front_to_clear():
            return True

        if self.abort_requested:
            return False

        if self.blocking_hazard in (
            "CLIFF",
            "STALL",
            "WHEEL_DROP",
        ):
            self.get_logger().error(
                f"Obstacle recovery stopped by hard hazard: "
                f"{self.blocking_hazard}"
            )
            self.stop()
            return False

        if self.blocking_hazard == "BUMP":
            self.get_logger().error(
                "Obstacle recovery stopped after BUMP contact."
            )
            self.stop()
            return False

        if preferred_side == "right":
            scan_directions = (-1, 1)

        elif preferred_side == "left":
            scan_directions = (1, -1)

        else:
            scan_directions = (
                self.preferred_scan_directions()
            )

        # Save Gem's measured corridor heading before scanning.
        pre_scan_yaw = self.odom_yaw

        for direction in scan_directions:
            signed_angle = (
                self.scan_for_clear_opening(direction)
            )

            if signed_angle is not None:
                if not self.drive_distance(
                    self.obstacle_bypass_distance,
                    speed=self.obstacle_bypass_speed,
                    allow_obstacle_recovery=False,
                    use_side_wall_correction=False,
                    restricted_center_only=True,
                ):
                    self.get_logger().error(
                        "Could not complete the local "
                        "obstacle bypass."
                    )
                    return False

                restore_deg = math.degrees(
                    normalize_angle(
                        pre_scan_yaw - self.odom_yaw
                    )
                )

                if (
                    abs(restore_deg) >= 1.0
                    and not self.rotate_degrees(
                        restore_deg
                    )
                ):
                    return False

                self.get_logger().info(
                    "Local obstacle bypass complete; "
                    "original corridor heading restored."
                )
                return True

            # An unsuccessful scan finishes at the maximum
            # scan angle. Return to the corridor heading
            # before checking the other side.
            restore_angle = (
                -direction
                * self.obstacle_max_scan_deg
            )

            if not self.rotate_degrees(
                restore_angle
            ):
                return False

        self.get_logger().error(
            "No clear local path found on either side. "
            "Route stopped."
        )
        self.stop()
        return False

    def drive_distance(
        self,
        distance,
        speed=None,
        allow_obstacle_recovery=True,
        use_side_wall_correction=True,
        preferred_recovery_side=None,
        restricted_center_only=False,
    ):
        """
        Drive while holding the starting odometry heading.

        The controller:
        - corrects sideways odometry error;
        - steers away from nearby side walls when enabled;
        - attempts limited local recovery for persistent front obstacles;
        - stops for blocking hazards or a phone abort.

        Local recovery is not map-based navigation. It only performs a
        bounded scan and short bypass, then returns to the original heading.
        """

        if distance <= 0.0:
            self.get_logger().error(
                "Drive distance must be greater than zero."
            )
            return False

        if not self.wait_for_sensor_data():
            return False

        if speed is None:
            speed = self.drive_speed

        start_x = self.odom_x
        start_y = self.odom_y
        target_yaw = self.odom_yaw

        front_high_count = 0
        last_front_eval_ir_sample_id = None
        front_blocked_since = None
        recovery_count = 0
        heading_recovery_count = 0
        side_wall_correction_active = use_side_wall_correction
        cross_track_ramp_start = -math.inf
        cross_track_ramp_end = -math.inf
        last_log = 0.0

        timeout = max(
            20.0,
            (distance / max(speed, 0.01)) * 3.0
        )
        deadline = time.monotonic() + timeout

        self.get_logger().info(
            f"Guarded odometry drive: "
            f"{distance:.2f} m at {speed:.2f} m/s."
        )

        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)

            if self.abort_requested:
                self.get_logger().error("Drive aborted from phone.")
                self.stop(reason="abort")
                return False

            if (
                self.odom_x is None
                or self.odom_y is None
                or self.odom_yaw is None
            ):
                continue

            if self.blocking_hazard in (
                "CLIFF",
                "STALL",
                "WHEEL_DROP",
            ):
                self.get_logger().error(
                    f"Drive stopped by hard hazard: "
                    f"{self.blocking_hazard}"
                )
                self.stop(reason="blocking_hazard")
                return False

            bump_detected = (
                self.blocking_hazard == "BUMP"
            )

            dx = self.odom_x - start_x
            dy = self.odom_y - start_y

            # Forward progress along the intended route direction.
            progress = (
                dx * math.cos(target_yaw)
                + dy * math.sin(target_yaw)
            )

            # Positive means Gem is left of the intended route line.
            lateral_error = (
                -dx * math.sin(target_yaw)
                + dy * math.cos(target_yaw)
            )

            heading_error = normalize_angle(
                target_yaw - self.odom_yaw
            )

            heading_error_deg = math.degrees(
                heading_error
            )

            if (
                abs(heading_error_deg)
                > self.max_heading_error_deg
            ):
                self.stop(reason="heading_recovery")

                self.get_logger().warn(
                    f"Heading error "
                    f"{heading_error_deg:+.1f} degrees "
                    f"exceeds the safety limit of "
                    f"{self.max_heading_error_deg:.1f} degrees. "
                    "Forward motion stopped; re-aligning "
                    "to the intended corridor heading."
                )

                self.update_phone_status(
                    route_status="Running",
                    action=(
                        f"Re-aligning heading by "
                        f"{heading_error_deg:+.1f} degrees"
                    ),
                )

                if not self.rotate_degrees(
                    heading_error_deg
                ):
                    self.get_logger().error(
                        "Heading recovery rotation failed. "
                        "Route stopped."
                    )
                    return False

                heading_recovery_count += 1

                # The side-wall term is the likely source of this
                # divergence. Once a heading recovery is required,
                # disable it for the remainder of this edge.
                side_wall_correction_active = False

                front_high_count = 0
                front_blocked_since = None
                last_front_eval_ir_sample_id = self.ir_sample_id

                # Refresh position after the in-place correction.
                rclpy.spin_once(
                    self,
                    timeout_sec=0.05,
                )

                dx = self.odom_x - start_x
                dy = self.odom_y - start_y

                progress = (
                    dx * math.cos(target_yaw)
                    + dy * math.sin(target_yaw)
                )

                # Reintroduce route-line correction gradually rather
                # than applying the full cross-track term immediately.
                cross_track_ramp_start = progress
                cross_track_ramp_end = (
                    progress + self.obstacle_rejoin_delay
                )

                self.get_logger().info(
                    "Heading recovery complete. "
                    "Side-wall correction disabled for the "
                    "remainder of this drive edge."
                )

                continue

            if progress >= distance - 0.05:
                self.stop(reason="edge_complete")
                self.get_logger().info(
                    f"Drive complete. "
                    f"Progress={progress:.3f} m, "
                    f"lateral error={lateral_error:+.3f} m, "
                    f"heading error="
                    f"{math.degrees(heading_error):+.2f} degrees."
                )
                return True

            left_value = max(
                self.get_ir("ir_intensity_side_left"),
                self.get_ir("ir_intensity_left")
            )

            right_value = max(
                self.get_ir("ir_intensity_side_right"),
                self.get_ir("ir_intensity_right"),
            )

            # Use the same IR snapshot for the decision and log.
            readings = self.front_ir_snapshot()

            center_only_detection = (
                not allow_obstacle_recovery
                and restricted_center_only
            )

            front_value = self.front_ir_value(
                center_only=center_only_detection,
                readings=readings,
            )

            (
                front_detected,
                single_hits,
                adjacent_hits,
            ) = self.front_obstacle_evidence(
                readings=readings,
                center_only=center_only_detection,
            )

            current_ir_sample_id = self.ir_sample_id
            front_ir_confirmed = False

            if (
                current_ir_sample_id
                != last_front_eval_ir_sample_id
            ):
                last_front_eval_ir_sample_id = current_ir_sample_id
                ir_now = time.monotonic()

                if front_detected:
                    front_high_count += 1

                    if front_blocked_since is None:
                        front_blocked_since = ir_now

                    blocked_for = (
                        ir_now - front_blocked_since
                    )

                    self.get_logger().warn(
                        f"FRONT DEBOUNCE: "
                        f"blocked_for={blocked_for:.3f}/"
                        f"{self.front_trigger_duration:.3f} sec | "
                        f"samples={front_high_count} | "
                        f"ir_sample_id={current_ir_sample_id} | "
                        f"IR={readings} | "
                        f"single={single_hits or '-'} | "
                        f"adjacent={adjacent_hits or '-'}"
                    )

                    if (
                        blocked_for
                        >= self.front_trigger_duration
                    ):
                        front_ir_confirmed = True

                else:
                    front_high_count = 0
                    front_blocked_since = None

            if (
                bump_detected
                or front_ir_confirmed
            ):
                stop_reason = (
                    "bump_detected"
                    if bump_detected
                    else "front_ir_confirmed"
                )
                self.stop(reason=stop_reason)

                if not allow_obstacle_recovery:
                    self.get_logger().error(
                        f"Drive stopped for front obstacle during a "
                        f"restricted manoeuvre. "
                        f"IR={readings} | "
                        f"single={single_hits or '-'} | "
                        f"adjacent={adjacent_hits or '-'}"
                    )
                    return False

                reason = (
                    "BUMP contact"
                    if bump_detected
                    else (
                        f"persistent calibrated IR evidence: "
                        f"{readings} | "
                        f"single={single_hits or '-'} | "
                        f"adjacent={adjacent_hits or '-'}"
                    )
                )

                self.get_logger().warn(
                    f"Obstacle at progress "
                    f"{progress:.2f}/"
                    f"{distance:.2f} m: "
                    f"{reason}."
                )

                if not self.recover_from_front_obstacle(
                    preferred_side=preferred_recovery_side,
                ):
                    return False

                recovery_count += 1
                front_high_count = 0
                front_blocked_since = None
                last_front_eval_ir_sample_id = self.ir_sample_id

                # Recalculate the projected position after the bypass.
                dx = self.odom_x - start_x
                dy = self.odom_y - start_y
                progress = (
                    dx * math.cos(target_yaw)
                    + dy * math.sin(target_yaw)
                )

                # Bring route-line correction back gradually after
                # the bypass. Switching immediately from zero to full
                # correction caused a steering oscillation in testing.
                cross_track_ramp_start = progress
                cross_track_ramp_end = (
                    progress + self.obstacle_rejoin_delay
                )

                # Keep the original per-segment deadline. Recoveries
                # are unlimited by count, but the edge cannot loop forever.
                continue

            cross_track_term = 0.0

            if progress >= cross_track_ramp_end:
                cross_track_term = (
                    -self.cross_track_kp * lateral_error
                )

            elif progress > cross_track_ramp_start:
                ramp_fraction = (
                    (progress - cross_track_ramp_start)
                    / max(
                        self.obstacle_rejoin_delay,
                        0.01,
                    )
                )

                cross_track_term = (
                    ramp_fraction
                    * -self.cross_track_kp
                    * lateral_error
                )

            # Odometry heading and route-line correction.
            angular_command = (
                self.heading_kp * heading_error
                + cross_track_term
            )

            if side_wall_correction_active:
                wall_correction = 0.0

                # Positive angular.z turns left.
                # Close to right wall -> gently steer left.
                if right_value > self.side_threshold:
                    wall_correction += self.wall_gain * (
                        right_value - self.side_threshold
                    )

                # Close to left wall -> gently steer right.
                if left_value > self.side_threshold:
                    wall_correction -= self.wall_gain * (
                        left_value - self.side_threshold
                    )

                # Do not allow the side-wall sensors to take control
                # of the robot's overall steering.
                wall_correction = max(
                    -self.max_wall_correction,
                    min(
                        self.max_wall_correction,
                        wall_correction,
                    ),
                )

                angular_command += wall_correction

            angular_command = max(
                -self.max_turn_correction,
                min(self.max_turn_correction, angular_command)
            )

            command = Twist()
            command.linear.x = speed
            command.angular.z = angular_command
            self.publish_cmd_vel(command, source="drive_distance")

            now = time.monotonic()
            if now - last_log >= 0.5:
                last_log = now
                self.get_logger().info(
                    f"progress={progress:.2f}/{distance:.2f} m | "
                    f"lateral={lateral_error:+.3f} m | "
                    f"heading="
                    f"{math.degrees(heading_error):+.2f} deg | "
                    f"left={left_value} "
                    f"right={right_value} | "
                    f"IR={readings} | "
                    f"front_detected="
                    f"{front_detected} | "
                    f"recoveries={recovery_count} | "
                    f"heading_recoveries="
                    f"{heading_recovery_count} | "
                    f"wall_correction="
                    f"{'on' if side_wall_correction_active else 'off'} | "
                    f"turn={angular_command:+.3f} rad/s"
                )

        self.stop(reason="drive_timeout")
        self.get_logger().error("Guarded drive timed out.")
        return False

    def wall_feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        self.last_wall_engaged = feedback.engaged

        if feedback.engaged:
            self.wall_engaged_seen = True

        self.get_logger().info(f"Wall-follow engaged: {feedback.engaged}")

    def wall_follow(self, side="right", seconds=15):
        if side == "right":
            follow_side = -1
        elif side == "left":
            follow_side = 1
        else:
            self.get_logger().error(f"Invalid wall-follow side: {side}")
            return False

        self.wall_engaged_seen = False
        self.last_wall_engaged = False

        self.get_logger().info(f"Wall-following {side} wall for {seconds} seconds.")

        goal = WallFollow.Goal()
        goal.follow_side = follow_side
        goal.max_runtime.sec = int(seconds)
        goal.max_runtime.nanosec = 0

        send_future = self.wall_client.send_goal_async(
            goal,
            feedback_callback=self.wall_feedback_callback
        )
        rclpy.spin_until_future_complete(self, send_future)

        goal_handle = send_future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Wall-follow goal rejected.")
            return False

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)

        result_response = result_future.result()
        status = result_response.status

        self.stop()
        time.sleep(0.5)

        if status != GoalStatus.STATUS_SUCCEEDED:
            self.get_logger().error(
                f"Wall-follow did not succeed. Status: {self.status_name(status)}"
            )
            return False

        if not self.wall_engaged_seen:
            self.get_logger().warn(
                "Wall-follow completed, but it never reported engaged=True. "
                "Gem may have been too far from the wall."
            )
            return False

        self.get_logger().info("Wall-follow complete.")
        return True

    def run_route(
        self,
        destination,
        dry_run=True,
        start_node=None,
    ):
        # Use the map default unless the caller explicitly supplies
        # a different physical starting node.
        if start_node is None:
            start_node = self.default_start_node

        current_map_heading_deg = self.default_start_heading_deg

        graph_nodes = self.get_topological_nodes()

        if destination in graph_nodes:
            steps, node_path = self.build_planned_route(
                start_node,
                destination,
            )

            if steps is None:
                return False

            readable_path = " -> ".join(
                self.node_labels.get(node, node)
                for node in node_path
            )

            self.get_logger().info(
                f"A* selected path: {readable_path}"
            )

            selected_route_name = (
                f"A* {start_node} to {destination}"
            )

        elif destination in self.routes:
            # Keep the full-lap and diagnostic test routes available.
            steps = self.routes[destination]
            selected_route_name = destination

        else:
            graph_destinations = sorted(graph_nodes)
            test_routes = sorted(self.routes.keys())

            self.get_logger().error(
                f"Unknown destination: {destination}"
            )

            self.get_logger().info(
                f"Map destinations: {graph_destinations}"
            )

            self.get_logger().info(
                f"Test routes: {test_routes}"
            )

            return False

        self.get_logger().info(
            f"Selected route: {selected_route_name}"
        )
        self.update_phone_status(
            route_status="Dry run" if dry_run else "Starting",
            location="IoT Lab start",
            action="Preparing route",
        )

        if dry_run:
            self.get_logger().info("DRY RUN ONLY. Robot will not move.")
        else:
            for seconds_left in range(5, 0, -1):
                self.update_phone_status(
                    route_status="Starting",
                    location="IoT Lab start",
                    action=f"Starting automatically in {seconds_left} seconds",
                )
                self.get_logger().info(
                    f"Automatic route start in {seconds_left} seconds."
                )
                time.sleep(1.0)
                if self.abort_requested:
                    self.update_phone_status(
                        route_status="Aborted",
                        action="Stopped before route start",
                    )
                    self.stop()
                    return False

        for step in steps:
            action = step[0]

            if self.abort_requested:
                self.get_logger().error("Route aborted from phone.")
                self.update_phone_status(route_status="Aborted", action="Stopped")
                self.stop()
                return False

            if action == "say":
                text = step[1]
                self.get_logger().info(f"SAY: {text}")
                self.update_phone_status(action=text)

            elif action == "checkpoint":
                text = step[1]

                if dry_run:
                    self.get_logger().info(f"DRY RUN CHECKPOINT: {text}")
                else:
                    ok = self.report_checkpoint(text)
                    if not ok:
                        return False

            elif action == "navigate_edge":
                current_node = step[1]
                next_node = step[2]
                distance = step[3]
                target_heading_deg = step[4]
                movement_mode = step[5]
                doorway_offset = step[6]
                recovery_side = step[7]

                required_turn_deg = normalize_degrees(
                    target_heading_deg
                    - current_map_heading_deg
                )

                self.get_logger().info(
                    f"MAP EDGE: {current_node} -> {next_node} | "
                    f"distance={distance:.2f} m | "
                    f"heading={target_heading_deg:+.1f} deg | "
                    f"turn={required_turn_deg:+.1f} deg | "
                    f"mode={movement_mode} | "
                    f"recovery_side={recovery_side or '-'}"
                )

                if dry_run:
                    if abs(required_turn_deg) >= 1.0:
                        self.get_logger().info(
                            f"DRY RUN: calculated turn "
                            f"{required_turn_deg:+.1f} degrees"
                        )

                    self.get_logger().info(
                        f"DRY RUN: {movement_mode} drive "
                        f"{distance:.2f} m"
                    )

                    current_map_heading_deg = target_heading_deg
                    continue

                if abs(required_turn_deg) >= 1.0:
                    self.update_phone_status(
                        route_status="Running",
                        action=(
                            f"Turning "
                            f"{required_turn_deg:+.0f} degrees"
                        ),
                    )

                    if not self.rotate_degrees(
                        required_turn_deg
                    ):
                        return False

                current_map_heading_deg = target_heading_deg

                self.update_phone_status(
                    route_status="Running",
                    action=(
                        f"Travelling {distance:.2f} m "
                        f"to {self.node_labels[next_node]}"
                    ),
                )

                if movement_mode == "guarded":
                    ok = self.drive_distance(
                        distance,
                        preferred_recovery_side=recovery_side,
                    )

                elif movement_mode == "drive_action":
                    # Use the same obstacle-aware controller on
                    # every map edge.
                    ok = self.drive_distance(
                        distance,
                        speed=self.drive_speed,
                        preferred_recovery_side=(
                            recovery_side
                        ),
                    )

                elif movement_mode == "offset_doorway":
                    if doorway_offset != "right":
                        self.get_logger().error(
                            "Left-offset doorway traversal is not "
                            "implemented yet. Route stopped safely."
                        )
                        return False

                    ok = self.navigate_right_offset_doorway(
                        distance
                    )

                else:
                    self.get_logger().error(
                        f"Unsupported movement mode: "
                        f"{movement_mode}"
                    )
                    return False

                if not ok:
                    return False

            elif action == "turn_deg":
                degrees = step[1]

                if dry_run:
                    self.get_logger().info(f"DRY RUN: turn {degrees} degrees")
                else:
                    self.update_phone_status(
                        route_status="Running",
                        action=f"Turning {degrees:.0f} degrees",
                    )
                    ok = self.rotate_degrees(degrees)
                    if not ok:
                        return False

            elif action == "drive":
                distance = step[1]

                if dry_run:
                    self.get_logger().info(f"DRY RUN: drive {distance:.2f} m")
                else:
                    self.update_phone_status(
                        route_status="Running",
                        action=f"Driving {distance:.2f} m",
                    )
                    ok = self.drive_distance(distance)
                    if not ok:
                        return False

            elif action == "drive_action":
                distance = step[1]
                speed = step[2] if len(step) > 2 else self.drive_speed

                if dry_run:
                    self.get_logger().info(
                        f"DRY RUN: built-in DriveDistance {distance:.2f} m "
                        f"at {speed:.2f} m/s"
                    )
                else:
                    self.update_phone_status(
                        route_status="Running",
                        action=f"Driving {distance:.2f} m at {speed:.2f} m/s",
                    )
                    ok = self.drive_distance(
                        distance,
                        speed=speed,
                    )
                    if not ok:
                        return False

            elif action == "doorway_right":
                total_distance = step[1]

                if dry_run:
                    self.get_logger().info(
                        f"DRY RUN: adaptive right-offset doorway over "
                        f"{total_distance:.2f} m"
                    )
                else:
                    self.update_phone_status(
                        route_status="Running",
                        action="Navigating right-offset doorway",
                    )
                    ok = self.navigate_right_offset_doorway(total_distance)
                    if not ok:
                        return False

            elif action == "wall_follow_right":
                seconds = step[1]

                if dry_run:
                    self.get_logger().info(f"DRY RUN: wall-follow right for {seconds} seconds")
                else:
                    ok = self.wall_follow(side="right", seconds=seconds)
                    if not ok:
                        return False

            elif action == "wall_follow_left":
                seconds = step[1]

                if dry_run:
                    self.get_logger().info(f"DRY RUN: wall-follow left for {seconds} seconds")
                else:
                    ok = self.wall_follow(side="left", seconds=seconds)
                    if not ok:
                        return False

            elif action == "stop":
                self.stop()
                self.get_logger().info("Stopped.")

            else:
                self.get_logger().warn(f"Unknown route step: {step}")

        self.stop()
        self.update_phone_status(
            route_status="Complete",
            action="Route finished",
        )
        self.get_logger().info("Route finished.")
        return True


def main():
    parser = argparse.ArgumentParser(description="Run predefined G Block routes for Gem.")

    parser.add_argument(
        "--destination",
        default="G1.04",
        help=(
            "Map destination or diagnostic route. "
            "Examples: G1.04, G1.11, G1.23, "
            "FULL_LAP_CHECKPOINT"
        ),
    )

    parser.add_argument(
        "--start-node",
        default=None,
        help=(
            "Optional topological map node where this route begins. "
            "If omitted, the map default_start_node is used."
        ),
    )

    parser.add_argument(
        "--namespace",
        default="/gem",
        help="Robot namespace. Default: /gem"
    )

    parser.add_argument(
        "--run",
        action="store_true",
        help="Actually move the robot. Without this, script only dry-runs."
    )

    parser.add_argument(
        "--phone-port",
        type=int,
        default=8081,
        help="Phone checkpoint web page port. Default: 8081"
    )

    parser.add_argument(
        "--map-file",
        default=None,
        help=(
            "Path to the external topological map JSON file. "
            "Defaults to config/gblock_topological_map.json"
        ),
    )
    args = parser.parse_args()

    rclpy.init()
    node = GBlockRouteRunner(
        namespace=args.namespace,
        map_file=args.map_file,
    )

    try:
        if args.run:
            node.wait_for_servers()
            node.start_phone_checkpoint_server(port=args.phone_port)

        route_success = node.run_route(
            destination=args.destination,
            dry_run=not args.run,
            start_node=args.start_node,
        )

    except KeyboardInterrupt:
        node.get_logger().warn("Interrupted by user.")
        node.abort_requested = True
        node.stop()
        route_success = False

    except Exception as e:
        node.get_logger().error(str(e))
        node.stop()
        route_success = False

    finally:
        node.stop()
        node.shutdown_phone_checkpoint_server()
        node.destroy_node()
        rclpy.shutdown()

    if route_success:
        return 0

    if node.abort_requested:
        return 2

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
