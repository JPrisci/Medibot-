#!/usr/bin/env python3

# json lets us turn Python dictionary data into a text string.
# This is useful because std_msgs/String can only send text.
import json

# rclpy is the Python library for ROS 2.
import rclpy

# Node is the base class used to create our own ROS 2 node.
from rclpy.node import Node

# String is a simple ROS 2 message type that sends text.
from std_msgs.msg import String


class GemStatusPublisher(Node):
    def __init__(self):
        # This gives the node a name inside ROS 2.
        super().__init__("gem_status_publisher")

        # This publisher sends String messages on the MediBot status topic.
        self.publisher = self.create_publisher(
            String,
            "/medibot/robot_status",
            10
        )

        # This timer calls publish_status once every 1 second.
        self.timer = self.create_timer(1.0, self.publish_status)

        # These are the status values for Gem.
        self.robot_name = "gem"
        self.floor = "floor_2"

        # Simple Gem state sequence for testing.
        # This does not move the robot. It only changes the status message.
        self.state_sequence = [
            {"state": "available", "handover_status": "none"},
            {"state": "handover_ready", "handover_status": "ready"},
            {"state": "assigned", "handover_status": "none"},
            {"state": "guiding_to_destination", "handover_status": "none"},
            {"state": "handover_complete", "handover_status": "complete"},
        ]

        self.state_index = 0

        self.get_logger().info("Gem status publisher started.")

    def publish_status(self):
        # Pick the current state.
        current_state = self.state_sequence[self.state_index]

        status_data = {
            "robot_name": self.robot_name,
            "floor": self.floor,
            "state": current_state["state"],
            "handover_status": current_state["handover_status"]
        }

        # Move to the next state for the next timer tick.
        self.state_index = (self.state_index + 1) % len(self.state_sequence)

        # Convert the dictionary into JSON text.
        msg = String()
        msg.data = json.dumps(status_data)

        # Publish the message.
        self.publisher.publish(msg)

        # Print what was published.
        self.get_logger().info(f"Published Gem status: {msg.data}")


def main(args=None):
    rclpy.init(args=args)

    node = GemStatusPublisher()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        node.get_logger().info("Gem status publisher stopped.")

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()