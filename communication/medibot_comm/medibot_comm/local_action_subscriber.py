#!/usr/bin/env python3

# Robot-side subscriber for local MediBot actions.
#
# This node listens to a robot-specific local-action topic such as:
# /medibot/jarvis/local_action
# /medibot/gem/local_action
#
# It validates and interprets the action message, but it does not move the robot.
# Later, this node can become an interface to navigation or robot behaviour code.

import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class LocalActionSubscriber(Node):
    def __init__(self):
        super().__init__("local_action_subscriber")

        # Set the robot role when starting the node:
        #
        # Jarvis:
        # ros2 run medibot_comm local_action_subscriber \
        #   --ros-args -p robot_name:=jarvis
        #
        # Gem:
        # ros2 run medibot_comm local_action_subscriber \
        #   --ros-args -p robot_name:=gem
        self.declare_parameter("robot_name", "unknown")

        self.robot_name = (
            self.get_parameter("robot_name")
            .get_parameter_value()
            .string_value
            .lower()
            .strip()
        )

        # The same file is intended to be used for Jarvis and Gem.
        if self.robot_name not in ("jarvis", "gem"):
            self.get_logger().warn(
                "robot_name should normally be set to 'jarvis' or 'gem'."
            )

        # Each robot listens only to its own local-action topic.
        self.local_action_topic = (
            f"/medibot/{self.robot_name}/local_action"
        )

        # Store the previous action so an identical repeated message does not
        # repeatedly restart the same future behaviour.
        self.last_action = None

        self.subscription = self.create_subscription(
            String,
            self.local_action_topic,
            self.receive_local_action,
            10
        )

        self.get_logger().info("Local action subscriber started.")
        self.get_logger().info(
            f"Robot role set to: {self.robot_name}"
        )
        self.get_logger().info(
            f"Listening on {self.local_action_topic}"
        )
        self.get_logger().info(
            "This node only processes software actions. "
            "It does not publish robot movement commands."
        )

    def receive_local_action(self, msg):
        # Local actions are sent as JSON text inside std_msgs/String.
        try:
            action_data = json.loads(msg.data)

        except json.JSONDecodeError:
            self.get_logger().warn(
                f"Could not decode local action as JSON: {msg.data}"
            )
            return

        if not isinstance(action_data, dict):
            self.get_logger().warn(
                "Local action message was valid JSON, "
                "but it was not a JSON object."
            )
            return

        message_robot_name = (
            str(action_data.get("robot_name", "unknown"))
            .lower()
            .strip()
        )

        action = action_data.get("action", "unknown_action")
        source_decision = action_data.get(
            "source_decision",
            "unknown_decision"
        )
        reason = action_data.get(
            "reason",
            "no reason provided"
        )

        # A Jarvis listener should not process a message claiming to be for Gem,
        # and a Gem listener should not process a message claiming to be for Jarvis.
        if message_robot_name != self.robot_name:
            self.get_logger().warn(
                f"Ignoring local action for {message_robot_name}; "
                f"this node is configured for {self.robot_name}."
            )
            return

        # Ignore an immediately repeated action.
        if action == self.last_action:
            return

        self.last_action = action

        self.get_logger().info(
            f"New local action received: {action}"
        )
        self.get_logger().info(
            f"Source coordinator decision: {source_decision}"
        )
        self.get_logger().info(
            f"Reason: {reason}"
        )

        self.handle_local_action(action)

    def handle_local_action(self, action):
        # These remain software-only placeholders.
        # No navigation or movement command is sent here.

        if action == "prepare_handover":
            self.get_logger().info(
                "Behaviour interface placeholder: "
                "prepare to hand over the visitor."
            )

        elif action == "prepare_receive":
            self.get_logger().info(
                "Behaviour interface placeholder: "
                "prepare to receive the visitor."
            )

        elif action == "wait_for_partner":
            self.get_logger().info(
                "Behaviour interface placeholder: "
                "wait at the transfer point for the other robot."
            )

        elif action == "prepare_for_handover":
            self.get_logger().info(
                "Behaviour interface placeholder: "
                "continue preparing for the handover."
            )

        elif action == "normal_operation":
            self.get_logger().info(
                "Behaviour interface placeholder: "
                "remain in normal operation."
            )

        elif action == "waiting_for_statuses":
            self.get_logger().info(
                "Behaviour interface placeholder: "
                "wait until the coordinator has current robot statuses."
            )

        elif action == "block_handover_stale_status":
            self.get_logger().warn(
                "Behaviour interface placeholder: "
                "block the handover because robot status information is stale."
            )

        else:
            self.get_logger().warn(
                f"Unknown local action received: {action}"
            )


def main(args=None):
    rclpy.init(args=args)

    node = LocalActionSubscriber()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        node.get_logger().info(
            "Local action subscriber stopped."
        )

    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()