#!/usr/bin/env python3

# json lets us turn JSON text back into Python dictionary data.
# The status publisher sends JSON text, so the subscriber needs to read it.
import json

# rclpy is the Python library for ROS 2.
# It lets us create ROS 2 nodes, publishers, subscribers, timers, etc.
import rclpy

# Node is the base class used to create our own ROS 2 node.
from rclpy.node import Node

# String is the ROS 2 message type used by the status publisher.
# The publisher sends the robot status as text inside this message type.
from std_msgs.msg import String


# This class defines our ROS 2 subscriber node.
# A subscriber node listens to a topic and reacts when messages arrive.
class StatusSubscriber(Node):
    def __init__(self):
        # This gives the node a name inside ROS 2.
        # You may see this name if you run ros2 node list.
        super().__init__("status_subscriber")

        # This creates a subscription.
        # It listens for String messages on the topic /medibot/robot_status.
        #
        # When a message arrives, ROS 2 automatically calls:
        # self.receive_status()
        #
        # The number 10 is the queue size.
        # It means ROS can keep a small queue of messages if needed.
        self.subscription = self.create_subscription(
            String,
            "/medibot/robot_status",
            self.receive_status,
            10
        )

        # This prints a message in the terminal when the node starts.
        self.get_logger().info("Status subscriber started.")
        self.get_logger().info("Listening on /medibot/robot_status")

    def receive_status(self, msg):
        # This function runs every time a message is received
        # on /medibot/robot_status.

        try:
            # msg.data contains the text sent by the publisher.
            #
            # Example:
            # {"robot_name": "jarvis", "floor": "floor_1", "state": "available", "handover_status": "none"}
            #
            # json.loads() converts that JSON text into a Python dictionary.
            status_data = json.loads(msg.data)

            # Get each piece of status information from the dictionary.
            # The second value, such as "unknown", is used if the field is missing.
            robot_name = status_data.get("robot_name", "unknown")
            floor = status_data.get("floor", "unknown")
            state = status_data.get("state", "unknown")
            handover_status = status_data.get("handover_status", "unknown")

            # Print the received status in a readable way.
            # This is easier to understand than raw JSON.
            self.get_logger().info(
                f"Received status from {robot_name}: "
                f"floor={floor}, "
                f"state={state}, "
                f"handover_status={handover_status}"
            )

        except json.JSONDecodeError:
            # This runs if the message was not valid JSON.
            # It helps us notice if something sends badly formatted data.
            self.get_logger().warn(
                f"Received a message, but it was not valid JSON: {msg.data}"
            )


# main() is the function ROS 2 will run when we start this node.
def main(args=None):
    # Start the ROS 2 Python system.
    rclpy.init(args=args)

    # Create one instance of our StatusSubscriber node.
    node = StatusSubscriber()

    try:
        # Keep the node running.
        # This allows it to keep listening for incoming messages.
        rclpy.spin(node)

    except KeyboardInterrupt:
        # This happens when you stop the node with Ctrl + C.
        node.get_logger().info("Status subscriber stopped.")

    finally:
        # Cleanly destroy the node and shut down ROS 2.
        node.destroy_node()
        rclpy.shutdown()


# This makes the file runnable as a Python script.
# It calls main() when the file is executed directly.
if __name__ == "__main__":
    main()
