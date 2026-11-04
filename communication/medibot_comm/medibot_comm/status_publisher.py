#!/usr/bin/env python3

# json lets us turn Python dictionary data into a text string.
# This is useful because std_msgs/String can only send text.
import json

# rclpy is the Python library for ROS 2.
# It lets us create ROS 2 nodes, publishers, subscribers, timers, etc.
import rclpy

# Node is the base class used to create our own ROS 2 node.
from rclpy.node import Node

# String is a simple ROS 2 message type that sends text.
# We are using it for the first prototype because it is simple.
from std_msgs.msg import String


# This class defines our ROS 2 node.
# A node is basically one small ROS 2 program.
class StatusPublisher(Node):
    def __init__(self):
        # This gives the node a name inside ROS 2.
        # You may see this name if you run ros2 node list.
        super().__init__("jarvis_status_publisher")

        # This creates a publisher.
        # It will publish String messages on the topic /medibot/robot_status.
        #
        # The number 10 is the queue size.
        # It means ROS can keep a small queue of messages if needed.
        self.publisher = self.create_publisher(
            String,
            "/medibot/robot_status",
            10
        )

        # This creates a timer.
        # It calls self.publish_status() once every 1.0 seconds.
        self.timer = self.create_timer(1.0, self.publish_status)

        # These are the status values we want Jarvis to report.
        # Later, these could change depending on what the robot is doing.
        self.robot_name = "jarvis"
        self.floor = "floor_1"

        # A simple first communication state sequence for testing.
        # This does not move the robot. It only changes the status message.
        self.state_sequence = [
            {"state": "available", "handover_status": "none"},
            {"state": "assigned", "handover_status": "none"},
            {"state": "guiding_to_transfer_point", "handover_status": "none"},
            {"state": "handover_requested", "handover_status": "pending"},
            {"state": "handover_ready", "handover_status": "ready"},
            {"state": "handover_complete", "handover_status": "complete"},
        ]

        self.state_index = 0

        # This prints a message in the terminal when the node starts.
        self.get_logger().info("Jarvis status publisher started.")

    def publish_status(self):
        # This dictionary stores the robot status information.
        # A dictionary is a Python structure with key-value pairs.
        current_state = self.state_sequence[self.state_index]

        status_data = {
            "robot_name": self.robot_name,
            "floor": self.floor,
            "state": current_state["state"],
            "handover_status": current_state["handover_status"]
        }

        # Move to the next state for the next timer tick.
        # The % makes it loop back to the start after the final state.
        self.state_index = (self.state_index + 1) % len(self.state_sequence)

        # Create an empty ROS 2 String message.
        msg = String()

        # Convert the dictionary into a JSON text string.
        # Example output:
        # {"robot_name": "jarvis", "floor": "floor_1", "state": "available", "handover_status": "none"}
        msg.data = json.dumps(status_data)

        # Publish the message on /medibot/robot_status.
        self.publisher.publish(msg)

        # Print what was published so we can see it in the terminal.
        self.get_logger().info(f"Published status: {msg.data}")


# main() is the function ROS 2 will run when we start this node.
def main(args=None):
    # Start the ROS 2 Python system.
    rclpy.init(args=args)

    # Create one instance of our StatusPublisher node.
    node = StatusPublisher()

    try:
        # Keep the node running.
        # This allows the timer to keep calling publish_status().
        rclpy.spin(node)

    except KeyboardInterrupt:
        # This happens when you stop the node with Ctrl + C.
        node.get_logger().info("Jarvis status publisher stopped.")

    finally:
        # Cleanly destroy the node and shut down ROS 2.
        node.destroy_node()
        rclpy.shutdown()


# This makes the file runnable as a Python script.
# It calls main() when the file is executed directly.
if __name__ == "__main__":
    main()
