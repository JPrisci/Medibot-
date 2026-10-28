#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.executors import ExternalShutdownException
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
        self._readiness_reported_for_task = False
        self._task_ready_timer = None

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

        self.ux_state_subscription = self.create_subscription(
            String,
            "/medibot/ux_state",
            self.receive_ux_state,
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

        # Automatically confirm Gem's staged receiving position once
        # DDS has had time to discover the Coordinator.
        self._startup_ready_timer = None
        if self.robot_name == "gem" and self.run_robot:
            self.get_logger().info(
                "Gem receiving readiness will be reported automatically "
                "in 5 seconds."
            )
            self._startup_ready_timer = self.create_timer(
                5.0,
                self._report_startup_receiving_ready,
            )

    def _report_startup_receiving_ready(self):
        """Report Gem's receiving position once after bridge startup."""
        timer = self._startup_ready_timer
        if timer is None:
            return

        timer.cancel()
        self._startup_ready_timer = None

        self.get_logger().info(
            "Automatically reporting Gem ready at LEVEL2_ELEVATOR."
        )
        self.handle_receiving_ready()

    # GEM_RESET_READY_V1
    def receive_ux_state(self, msg):
        if self.robot_name != "gem" or not self.run_robot:
            return

        try:
            state_data = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        if not isinstance(state_data, dict):
            return

        stage = str(state_data.get("current_stage", "")).strip()
        destination = str(state_data.get("destination", "")).strip()

        if stage == "waiting_for_destination" or not destination:
            self._readiness_reported_for_task = False
            return

        if self._readiness_reported_for_task or self.route_active:
            return

        self._readiness_reported_for_task = True
        self.get_logger().info(
            "New task detected; Gem readiness will be reported "
            "automatically at LEVEL2_ELEVATOR."
        )
        self._task_ready_timer = self.create_timer(
            1.0,
            self._report_task_receiving_ready,
        )

    def _report_task_receiving_ready(self):
        timer = self._task_ready_timer
        if timer is None:
            return

        timer.cancel()
        self._task_ready_timer = None

        if self.route_active:
            self._readiness_reported_for_task = False
            return

        self.get_logger().info(
            "Automatically reporting Gem ready at LEVEL2_ELEVATOR "
            "for the current task."
        )
        self.handle_receiving_ready()

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

        if command == "report_receiving_ready":
            self.handle_receiving_ready()
            return

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

    def handle_receiving_ready(self):
        """Explicitly report that Gem is physically ready at Level 2."""

        if self.robot_name != "gem":
            self.get_logger().warn(
                "report_receiving_ready is only valid for Gem."
            )
            return

        if self.route_active:
            self.get_logger().warn(
                "Cannot report receiving readiness while a route is active."
            )
            return

        if self.run_robot:
            self.publish_navigation_event(
                "arrived_at_receiving_point",
                "LEVEL2_ELEVATOR",
            )
            return

        if self.publish_dry_run_events:
            self.get_logger().warn(
                "Publishing SIMULATED receiving-point readiness."
            )
            self.publish_navigation_event(
                "arrived_at_receiving_point",
                "LEVEL2_ELEVATOR",
                simulated=True,
            )
            return

        self.get_logger().info(
            "Dry-run receiving readiness accepted, but no event was "
            "published because --publish-dry-run-events is disabled."
        )

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

        # Jarvis uses the map's normal IOT_LAB default.
        # Gem is physically placed at the Level 2 receiving point.
        if self.robot_name == "gem":
            command.extend([
                "--start-node",
                "LEVEL2_ELEVATOR",
            ])

        if self.run_robot:
            command.append("--run")

        self.get_logger().info(
            "Starting GBlockRouteRunner: "
            + " ".join(command)
        )

        try:
            runner_env = os.environ.copy()

            if self.robot_name == "gem":
                runner_env["CYCLONEDDS_URI"] = (
                    '<CycloneDDS><Domain><General><Interfaces>'
                    '<NetworkInterface name="usb0" />'
                    '</Interfaces><AllowMulticast>true</AllowMulticast>'
                    '</General><Discovery><Peers>'
                    '<Peer Address="192.168.186.2"/>'
                    '</Peers></Discovery></Domain></CycloneDDS>'
                )

                self.get_logger().info(
                    "Gem route runner will use USB DDS on usb0."
                )

            self.current_process = subprocess.Popen(
                command,
                env=runner_env,
            )
            return_code = self.current_process.wait()

        except Exception as exc:
            self.get_logger().error(
                f"Could not execute route runner: {exc}"
            )
            self.publish_route_interruption(
                destination,
                "route_failed",
                f"Could not execute route runner: {exc}",
            )
            return

        finally:
            self.current_process = None
            self.route_active = False

        if return_code != 0:
            if return_code == 2 or return_code < 0:
                navigation_event = "route_aborted"
                reason = (
                    "Navigation runner was aborted "
                    f"(exit code {return_code})."
                )
            else:
                navigation_event = "route_failed"
                reason = (
                    "Navigation runner failed "
                    f"(exit code {return_code})."
                )

            self.get_logger().error(
                f"Route interruption for {destination}: "
                f"{navigation_event}, exit code={return_code}"
            )

            self.publish_route_interruption(
                destination,
                navigation_event,
                reason,
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

    def publish_navigation_event(
        self,
        navigation_event,
        destination,
        simulated=False,
        reason=None,
    ):
        event_data = {
            "robot_name": self.robot_name,
            "navigation_event": navigation_event,
            "destination": destination,
        }

        if simulated:
            event_data["simulated"] = True

        if reason is not None and str(reason).strip():
            event_data["reason"] = str(reason).strip()

        msg = String()
        msg.data = json.dumps(event_data)
        self.navigation_event_publisher.publish(msg)

        self.get_logger().info(
            f"Published navigation event: {msg.data}"
        )

    def publish_route_interruption(
        self,
        destination,
        navigation_event,
        reason,
    ):
        if self.run_robot:
            self.publish_navigation_event(
                navigation_event,
                destination,
                reason=reason,
            )
            return

        if self.publish_dry_run_events:
            self.publish_navigation_event(
                navigation_event,
                destination,
                simulated=True,
                reason=reason,
            )
            return

        self.get_logger().info(
            "Dry-run route interruption detected. No navigation event "
            "published because --publish-dry-run-events is disabled."
        )

    def publish_success_event(
        self,
        destination,
        simulated=False,
    ):
        navigation_event = None

        if (
            self.robot_name == "jarvis"
            and destination == "ELEVATOR_2"
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

        self.publish_navigation_event(
            navigation_event,
            destination,
            simulated=simulated,
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

    except ExternalShutdownException:
        # Normal ROS shutdown, for example when the bridge
        # process receives SIGTERM from a launcher or test.
        pass

    finally:
        node.stop_active_route()
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
