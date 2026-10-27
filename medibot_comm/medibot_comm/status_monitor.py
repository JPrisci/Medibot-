#!/usr/bin/env python3

import json
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class StatusMonitor(Node):
    def __init__(self):
        super().__init__("status_monitor")

        # Store the latest status received from each robot.
        # Expected robot names are "jarvis" and "gem".
        self.latest_status = {}

        # Mark a robot's status as STALE if no new status message
        # has been received for this many seconds.
        # This does not check whether the Navigation process is still running.
        self.stale_timeout_seconds = 5.0

        # Store the previous decision so changes are easy to see
        # in the terminal.
        self.last_decision = None

        # Listen for status messages from Jarvis and Gem.
        self.subscription = self.create_subscription(
            String,
            "/medibot/robot_status",
            self.receive_status,
            10,
        )

        # Listen for task_reset so statuses from the previous visitor
        # cannot affect the next visitor task.
        self.ux_event_subscription = self.create_subscription(
            String,
            "/medibot/ux_event",
            self.receive_ux_event,
            10,
        )

        # Publish coordinator handover decisions on a ROS 2 topic.
        self.decision_publisher = self.create_publisher(
            String,
            "/medibot/handover_decision",
            10,
        )

        # Every 2 seconds, print the latest robot statuses
        # and publish a decision.
        self.timer = self.create_timer(
            2.0,
            self.print_summary_and_publish_decision,
        )

        self.get_logger().info("Status monitor started.")

        self.get_logger().info(
            "Listening on /medibot/robot_status"
        )

        self.get_logger().info(
            "Listening for task_reset on /medibot/ux_event"
        )

        self.get_logger().info(
            "Publishing coordinator decisions on "
            "/medibot/handover_decision"
        )

        self.get_logger().info(
            f"Stale timeout set to "
            f"{self.stale_timeout_seconds} seconds."
        )

    def receive_ux_event(self, msg):
        """
        Observe UX events that affect coordinator status state.

        Only task_reset is handled here. Other UX events remain the
        responsibility of the TaskCoordinator.
        """

        try:
            event_data = json.loads(msg.data)

        except json.JSONDecodeError:
            return

        if not isinstance(event_data, dict):
            return

        event = (
            str(event_data.get("event", ""))
            .lower()
            .strip()
        )

        if event != "task_reset":
            return

        # Remove robot statuses left over from the previous visitor task.
        self.latest_status.clear()

        # Clear the previous decision so the reset state is treated
        # as a new coordinator decision.
        self.last_decision = None

        self.get_logger().info(
            "Task reset received. Cleared cached robot statuses "
            "and previous handover decision."
        )

        # Immediately publish the clean post-reset state rather than
        # waiting for the next 2-second timer tick.
        self.publish_handover_decision()

    def receive_status(self, msg):
        # This runs whenever a robot status message is received.
        try:
            status_data = json.loads(msg.data)

            if not isinstance(status_data, dict):
                self.get_logger().warn(
                    "Robot status was valid JSON, "
                    "but it was not a JSON object."
                )
                return

            robot_name = status_data.get(
                "robot_name",
                "unknown",
            )

            # Record the time the coordinator received this message.
            # This is used for FRESH/STALE detection.
            status_data["last_received_time"] = time.time()

            # Update the stored latest status for this robot.
            self.latest_status[robot_name] = status_data

            floor = status_data.get(
                "floor",
                "unknown",
            )

            state = status_data.get(
                "state",
                "unknown",
            )

            handover_status = status_data.get(
                "handover_status",
                "unknown",
            )

            self.get_logger().info(
                f"Updated {robot_name}: "
                f"floor={floor}, "
                f"state={state}, "
                f"handover_status={handover_status}"
            )

            # Re-evaluate the coordinator decision whenever
            # a new status arrives.
            self.publish_handover_decision()

        except json.JSONDecodeError:
            self.get_logger().warn(
                f"Could not decode status message as JSON: {msg.data}"
            )

    def get_status_age_and_freshness(
        self,
        status_data,
    ):
        # Work out how old a robot's latest status message is.
        current_time = time.time()

        last_received_time = status_data.get(
            "last_received_time",
            0.0,
        )

        age_seconds = (
            current_time - last_received_time
        )

        if age_seconds > self.stale_timeout_seconds:
            freshness = "STALE"

        else:
            freshness = "FRESH"

        return age_seconds, freshness

    def make_handover_decision(self):
        # Get the latest known status for Jarvis and Gem.
        jarvis = self.latest_status.get("jarvis")
        gem = self.latest_status.get("gem")

        # If the coordinator has not seen both robots yet,
        # it cannot decide.
        if jarvis is None or gem is None:
            return {
                "decision":
                "waiting_for_robot_statuses",
                "reason":
                "Coordinator has not received both "
                "Jarvis and Gem statuses yet.",
            }

        (
            jarvis_age,
            jarvis_freshness,
        ) = self.get_status_age_and_freshness(
            jarvis
        )

        (
            gem_age,
            gem_freshness,
        ) = self.get_status_age_and_freshness(
            gem
        )

        # Do not allow handover decisions using stale
        # robot information.
        if (
            jarvis_freshness == "STALE"
            or gem_freshness == "STALE"
        ):
            return {
                "decision":
                "handover_blocked_stale_status",
                "reason":
                "At least one robot status is stale, "
                "so the coordinator should not trust "
                "the handover state.",
                "jarvis_status":
                jarvis_freshness,
                "gem_status":
                gem_freshness,
                "jarvis_age_seconds":
                round(jarvis_age, 1),
                "gem_age_seconds":
                round(gem_age, 1),
            }

        jarvis_state = jarvis.get(
            "state",
            "unknown",
        )

        jarvis_handover_status = jarvis.get(
            "handover_status",
            "unknown",
        )

        gem_state = gem.get(
            "state",
            "unknown",
        )

        gem_handover_status = gem.get(
            "handover_status",
            "unknown",
        )

        jarvis_requesting_handover = (
            jarvis_state == "handover_requested"
            or jarvis_handover_status == "pending"
        )

        gem_ready_for_handover = (
            gem_state == "handover_ready"
            or gem_handover_status == "ready"
        )

        # Main successful handover condition.
        if (
            jarvis_requesting_handover
            and gem_ready_for_handover
        ):
            return {
                "decision":
                "handover_possible",
                "reason":
                "Jarvis has requested handover "
                "and Gem is ready.",
                "jarvis_state":
                jarvis_state,
                "gem_state":
                gem_state,
            }

        # Jarvis needs handover, but Gem is not ready yet.
        if (
            jarvis_requesting_handover
            and not gem_ready_for_handover
        ):
            return {
                "decision":
                "handover_not_ready",
                "reason":
                "Jarvis has requested handover, "
                "but Gem is not ready yet.",
                "jarvis_state":
                jarvis_state,
                "gem_state":
                gem_state,
            }

        # Normal condition when there is no current
        # handover request.
        return {
            "decision":
            "handover_not_requested",
            "reason":
            "No active handover request is "
            "currently detected.",
            "jarvis_state":
            jarvis_state,
            "gem_state":
            gem_state,
        }

    def publish_handover_decision(self):
        # Create the decision dictionary.
        decision_data = (
            self.make_handover_decision()
        )

        # Convert the decision dictionary into JSON text.
        msg = String()
        msg.data = json.dumps(
            decision_data
        )

        # Publish the decision on /medibot/handover_decision.
        self.decision_publisher.publish(msg)

        current_decision = decision_data.get(
            "decision",
            "unknown",
        )

        # Only print a clear log when the decision changes.
        if current_decision != self.last_decision:
            self.last_decision = current_decision

            self.get_logger().info(
                "Coordinator decision changed: "
                f"{msg.data}"
            )

    def print_summary_and_publish_decision(self):
        # If no statuses have arrived yet,
        # still publish a waiting decision.
        if not self.latest_status:
            self.get_logger().info(
                "No robot statuses received yet."
            )

            self.publish_handover_decision()
            return

        self.get_logger().info(
            "----- Latest robot statuses -----"
        )

        for (
            robot_name,
            status_data,
        ) in self.latest_status.items():

            floor = status_data.get(
                "floor",
                "unknown",
            )

            state = status_data.get(
                "state",
                "unknown",
            )

            handover_status = status_data.get(
                "handover_status",
                "unknown",
            )

            (
                age_seconds,
                freshness,
            ) = self.get_status_age_and_freshness(
                status_data
            )

            self.get_logger().info(
                f"{robot_name}: "
                f"floor={floor}, "
                f"state={state}, "
                f"handover_status={handover_status}, "
                f"age={age_seconds:.1f}s, "
                f"status={freshness}"
            )

        self.publish_handover_decision()


def main(args=None):
    rclpy.init(args=args)

    node = StatusMonitor()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        node.get_logger().info(
            "Status monitor stopped."
        )

    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
