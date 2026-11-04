#!/usr/bin/env python3

# json lets us turn Python dictionary data into a text string.
# We are using JSON because std_msgs/String only sends text.
import json

# rclpy is the Python library for ROS 2.
import rclpy

# Node is the base class for creating ROS 2 nodes.
from rclpy.node import Node

# String is a simple ROS 2 message type that sends text.
from std_msgs.msg import String


class SimulatedMultiStatusPublisher(Node):
    def __init__(self):
        # This gives the node a name inside ROS 2.
        super().__init__("simulated_multi_status_publisher")

        # This publisher sends status messages to the MediBot status topic.
        self.publisher = self.create_publisher(
            String,
            "/medibot/robot_status",
            10
        )

        # This timer calls publish_status once every second.
        self.timer = self.create_timer(1.0, self.publish_status)

        # This list simulates two robots: Jarvis and Gem.
        # Both are being simulated from this one file on the Jarvis Pi.
        self.status_sequence = [
            {
                "robot_name": "jarvis",
                "floor": "floor_1",
                "state": "available",
                "handover_status": "none"
            },
            {
                "robot_name": "gem",
                "floor": "floor_2",
                "state": "available",
                "handover_status": "none"
            },
            {
                "robot_name": "jarvis",
                "floor": "floor_1",
                "state": "assigned",
                "handover_status": "none"
            },
            {
                "robot_name": "jarvis",
                "floor": "floor_1",
                "state": "guiding_to_transfer_point",
                "handover_status": "none"
            },
            {
                "robot_name": "jarvis",
                "floor": "floor_1",
                "state": "handover_requested",
                "handover_status": "pending"
            },
            {
                "robot_name": "gem",
                "floor": "floor_2",
                "state": "handover_ready",
                "handover_status": "ready"
            },
            {
                "robot_name": "jarvis",
                "floor": "floor_1",
                "state": "handover_complete",
                "handover_status": "complete"
            },
            {
                "robot_name": "gem",
                "floor": "floor_2",
                "state": "available",
                "handover_status": "none"
            },
        ]

        # This keeps track of which message in the list should be sent next.
        self.status_index = 0

        self.get_logger().info("Simulated multi-robot status publisher started.")
        self.get_logger().info("Publishing simulated Jarvis and Gem status messages.")

    def publish_status(self):
        # Pick the current status message from the list.
        status_data = self.status_sequence[self.status_index]

        # Convert the Python dictionary into JSON text.
        msg = String()
        msg.data = json.dumps(status_data)

        # Publish the message.
        self.publisher.publish(msg)

        # Print the message so we can see it in the terminal.
        self.get_logger().info(f"Published simulated status: {msg.data}")

        # Move to the next status.
        # The modulo (%) makes it loop back to the beginning after the final message.
        self.status_index = (self.status_index + 1) % len(self.status_sequence)


def main(args=None):
    rclpy.init(args=args)

    node = SimulatedMultiStatusPublisher()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        node.get_logger().info("Simulated multi-robot status publisher stopped.")

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()