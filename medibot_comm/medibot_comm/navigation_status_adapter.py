#!/usr/bin/env python3

"""
Convert high-level navigation events into MediBot robot statuses.

Currently supported conversions:

1. Jarvis navigation event:
   arrived_at_transfer_point

   becomes:

       state = handover_requested
       handover_status = pending

2. Gem navigation event:
   arrived_at_receiving_point

   becomes:

       state = handover_ready
       handover_status = ready

Converted statuses are published on:

    /medibot/robot_status
"""

import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class NavigationStatusAdapter(Node):
    def __init__(self):
        super().__init__("navigation_status_adapter")

        # Listen for high-level events from the navigation component.
        self.navigation_subscription = self.create_subscription(
            String,
            "/medibot/navigation_event",
            self.receive_navigation_event,
            10,
        )

        # Publish statuses in the format already used by the coordinator.
        self.status_publisher = self.create_publisher(
            String,
            "/medibot/robot_status",
            10,
        )

        # Store the latest converted status for each robot.
        #
        # The coordinator treats statuses as stale if it stops receiving them,
        # so the adapter republishes the latest known status once per second.
        self.latest_statuses = {}

        self.status_timer = self.create_timer(
            1.0,
            self.publish_latest_statuses,
        )

        self.get_logger().info("Navigation status adapter started.")
        self.get_logger().info(
            "Listening on /medibot/navigation_event"
        )
        self.get_logger().info(
            "Publishing converted statuses on /medibot/robot_status"
        )

    def receive_navigation_event(self, msg):
        """Process one incoming navigation event."""

        try:
            event_data = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warn(
                f"Navigation event was not valid JSON: {msg.data}"
            )
            return

        if not isinstance(event_data, dict):
            self.get_logger().warn(
                "Navigation event was valid JSON, "
                "but it was not a JSON object."
            )
            return

        robot_name = (
            str(event_data.get("robot_name", ""))
            .lower()
            .strip()
        )

        navigation_event = (
            str(event_data.get("navigation_event", ""))
            .lower()
            .strip()
        )

        destination = str(
            event_data.get("destination", "unknown")
        ).strip()

        if robot_name not in ("jarvis", "gem"):
            self.get_logger().warn(
                f"Unknown robot_name in navigation event: {robot_name}"
            )
            return

        self.get_logger().info(
            "Received navigation event: "
            f"robot={robot_name}, "
            f"event={navigation_event}, "
            f"destination={destination}"
        )

        status_data = self.convert_event_to_status(
            robot_name,
            navigation_event,
        )

        if status_data is None:
            self.get_logger().warn(
                "Navigation event is not supported yet: "
                f"robot={robot_name}, "
                f"event={navigation_event}"
            )
            return

        # Remember the converted state for this robot.
        self.latest_statuses[robot_name] = status_data

        # Publish immediately instead of waiting for the next timer tick.
        self.publish_status(status_data)

    def convert_event_to_status(self, robot_name, navigation_event):
        """Translate navigation language into communication language."""

        # Jarvis reaches the first-floor transfer point and requests handover.
        if (
            robot_name == "jarvis"
            and navigation_event == "arrived_at_transfer_point"
        ):
            return {
                "robot_name": "jarvis",
                "floor": "floor_1",
                "state": "handover_requested",
                "handover_status": "pending",
            }

        # Gem reaches the receiving point and is ready for handover.
        if (
            robot_name == "gem"
            and navigation_event == "arrived_at_receiving_point"
        ):
            return {
                "robot_name": "gem",
                "floor": "floor_2",
                "state": "handover_ready",
                "handover_status": "ready",
            }

        # Other navigation events can be added and tested later.
        return None

    def publish_status(self, status_data):
        """Publish one converted MediBot status."""

        msg = String()
        msg.data = json.dumps(status_data)

        self.status_publisher.publish(msg)

        self.get_logger().info(
            f"Published converted robot status: {msg.data}"
        )

    def publish_latest_statuses(self):
        """Republish current statuses so they remain fresh."""

        for status_data in self.latest_statuses.values():
            self.publish_status(status_data)


def main(args=None):
    rclpy.init(args=args)

    node = NavigationStatusAdapter()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        node.get_logger().info(
            "Navigation status adapter stopped."
        )

    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()