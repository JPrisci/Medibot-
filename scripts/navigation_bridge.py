#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
import threading
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class NavigationBridge(Node):
    def __init__(
        self,
        robot_name,
        run_robot=False,
        publish_dry_run_events=False,
    ):
        super().__init__(f"{robot_name}_navigation_bridge")

        self.robot_name = robot_name.lower().strip()
        self.namespace = f"/{self.robot_name}"

        self.run_robot = run_robot
        self.publish_dry_run_events = publish_dry_run_events

        self.route_active = False
        self.current_process = None

        repo_root = Path(__file__).resolve().parent.parent
        self.runner_path = repo_root / "scripts" / "gblock_route_runner.py"

        self.command_topic = (
            f"/medibot/{self.robot_name}/navigation_command"
        )

        self.command_subscription = self.create_subscription(
            String,
            self.command_topic,
            self.receive_navigation_command,
            10,
        )

        self.navigation_event_publisher = self.create_publisher(
            String,
            "/medibot/navigation_event",
            10,
        )

        mode = "REAL ROBOT MODE" if self.run_robot else "DRY-RUN MODE"

        self.get_logger().info(
            f"Navigation bridge started for {self.robot_name}."
        )
        self.get_logger().info(
            f"Listening on {self.command_topic}"
        )
        self.get_logger().info(
            "Publishing navigation results on "
            "/medibot/navigation_event"
        )
        self.get_logger().info(
            f"Bridge mode: {mode}"
        )

        if not self.run_robot:
            self.get_logger().warn(
                "Dry-run mode enabled. The robot will NOT move."
            )

    def receive_navigation_command(self, msg):
        try:
            command_data = json.loads(msg.data)

        except json.JSONDecodeError:
            self.get_logger().warn(
                f"Navigation command was not valid JSON: {msg.data}"
            )
            return

        if not isinstance(command_data, dict):
            self.get_logger().warn(
                "Navigation command must be a JSON object."
            )
            return

        command = (
            str(command_data.get("command", ""))
            .lower()
            .strip()
        )

        destination = (
            str(command_data.get("destination", ""))
            .upper()
            .strip()
        )

        if command != "start_route":
            self.get_logger().warn(
                f"Unsupported navigation command: {command}"
            )
            return

        if not destination:
            self.get_logger().warn(
                "start_route command is missing destination."
            )
            return

        if self.route_active:
            self.get_logger().warn(
                "Ignoring start_route because a route is already active."
            )
            return

        self.get_logger().info(
            f"Accepted route request: "
            f"robot={self.robot_name}, "
            f"destination={destination}"
        )

        worker = threading.Thread(
            target=self.execute_route,
            args=(destination,),
            daemon=True,
        )
        worker.start()

    def execute_route(self, destination):
        self.route_active = True

        command = [
            sys.executable,
            str(self.runner_path),
            "--namespace",
            self.namespace,
            "--destination",
            destination,
        ]

        if self.run_robot:
            command.append("--run")

        self.get_logger().info(
            "Starting GBlockRouteRunner: "
            + " ".join(command)
        )

        try:
            self.current_process = subprocess.Popen(command)
            return_code = self.current_process.wait()

        except Exception as exc:
            self.get_logger().error(
                f"Could not execute route runner: {exc}"
            )
            return

        finally:
            self.current_process = None
            self.route_active = False

        if return_code != 0:
            self.get_logger().error(
                f"Route failed for {destination}. "
                f"Runner exit code={return_code}"
            )
            return

        self.get_logger().info(
            f"Route runner reported success for {destination}."
        )

        if self.run_robot:
            self.publish_success_event(destination)

        elif self.publish_dry_run_events:
            self.get_logger().warn(
                "Publishing SIMULATED navigation event "
                "because --publish-dry-run-events is enabled."
            )
            self.publish_success_event(
                destination,
                simulated=True,
            )

        else:
            self.get_logger().info(
                "Dry run completed successfully. "
                "No arrival event published."
            )

    def publish_success_event(
        self,
        destination,
        simulated=False,
    ):
        navigation_event = None

        if (
            self.robot_name == "jarvis"
            and destination == "ELEVATOR_1"
        ):
            navigation_event = "arrived_at_transfer_point"

        elif (
            self.robot_name == "gem"
            and destination == "DIGITAL_LIBRARY"
        ):
            navigation_event = "arrived_at_destination"

        if navigation_event is None:
            self.get_logger().warn(
                "Route succeeded, but there is currently no "
                "navigation-event mapping for "
                f"robot={self.robot_name}, "
                f"destination={destination}."
            )
            return

        event_data = {
            "robot_name": self.robot_name,
            "navigation_event": navigation_event,
            "destination": destination,
        }

        if simulated:
            event_data["simulated"] = True

        msg = String()
        msg.data = json.dumps(event_data)

        self.navigation_event_publisher.publish(msg)

        self.get_logger().info(
            f"Published navigation event: {msg.data}"
        )

    def stop_active_route(self):
        if (
            self.current_process is not None
            and self.current_process.poll() is None
        ):
            self.get_logger().warn(
                "Stopping active route subprocess."
            )
            self.current_process.terminate()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Bridge MediBot navigation commands to "
            "gblock_route_runner.py"
        )
    )

    parser.add_argument(
        "--robot",
        required=True,
        choices=["jarvis", "gem"],
        help="Robot handled by this bridge.",
    )

    parser.add_argument(
        "--run",
        action="store_true",
        help=(
            "Actually move the robot. "
            "Without this flag the route runner dry-runs."
        ),
    )

    parser.add_argument(
        "--publish-dry-run-events",
        action="store_true",
        help=(
            "Publish simulated navigation events after "
            "successful dry runs. Intended for integration testing."
        ),
    )

    args = parser.parse_args()

    rclpy.init()

    node = NavigationBridge(
        robot_name=args.robot,
        run_robot=args.run,
        publish_dry_run_events=args.publish_dry_run_events,
    )

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        node.get_logger().info(
            "Navigation bridge stopped by user."
        )

    finally:
        node.stop_active_route()
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
