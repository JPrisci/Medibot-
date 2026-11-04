#!/usr/bin/env python3

# Robot-side subscriber for coordinator handover decisions.
# This node listens to /medibot/handover_decision and reacts only when the decision changes.
# It also uses a robot_name parameter so Jarvis and Gem can respond differently.
# In addition to printing placeholder behaviour, it publishes a local robot action topic.

import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class HandoverDecisionSubscriber(Node):
    def __init__(self):
        super().__init__("handover_decision_subscriber")

        # Robot name can be set when running the node:
        # ros2 run medibot_comm handover_decision_subscriber --ros-args -p robot_name:=jarvis
        self.declare_parameter("robot_name", "unknown")
        self.robot_name = (
            self.get_parameter("robot_name")
            .get_parameter_value()
            .string_value
            .lower()
            .strip()
        )

        # Store the last decision so the robot does not repeatedly react to the same command.
        self.last_decision = None

        # Subscribe to the coordinator's handover decision topic.
        self.subscription = self.create_subscription(
            String,
            "/medibot/handover_decision",
            self.receive_decision,
            10
        )

        # Publish local robot action messages.
        # These are still software placeholders, but they create the next layer that
        # future navigation or robot behaviour code could subscribe to.
        self.local_action_topic = f"/medibot/{self.robot_name}/local_action"

        self.local_action_publisher = self.create_publisher(
            String,
            self.local_action_topic,
            10
        )

        self.get_logger().info("Handover decision subscriber started.")
        self.get_logger().info("Listening on /medibot/handover_decision")
        self.get_logger().info("Only reacting when the handover decision changes.")
        self.get_logger().info(f"Robot role set to: {self.robot_name}")
        self.get_logger().info(f"Publishing local actions on {self.local_action_topic}")

    def receive_decision(self, msg):
        # The coordinator publishes the decision as a JSON string.
        try:
            decision_data = json.loads(msg.data)

            decision = decision_data.get("decision", "unknown")
            reason = decision_data.get("reason", "no reason provided")
            jarvis_state = decision_data.get("jarvis_state", "unknown")
            gem_state = decision_data.get("gem_state", "unknown")

            # Ignore repeated decisions so the robot-side logic is cleaner.
            if decision == self.last_decision:
                return

            self.last_decision = decision

            self.get_logger().info(f"New handover decision received: {decision}")
            self.get_logger().info(f"Reason: {reason}")
            self.get_logger().info(
                f"Coordinator context: jarvis_state={jarvis_state}, gem_state={gem_state}"
            )

            self.handle_decision(decision, reason)

        except json.JSONDecodeError:
            self.get_logger().warn(
                f"Received decision message, but it was not valid JSON: {msg.data}"
            )

    def handle_decision(self, decision, reason):
        # These are still placeholders. Later, movement/navigation code could listen
        # to the local action topic and perform real robot behaviours.

        action = "unknown_action"

        if decision == "handover_possible":
            if self.robot_name == "jarvis":
                action = "prepare_handover"
                self.get_logger().info(
                    "Jarvis action placeholder: prepare to hand over the visitor."
                )

            elif self.robot_name == "gem":
                action = "prepare_receive"
                self.get_logger().info(
                    "Gem action placeholder: prepare to receive the visitor."
                )

            else:
                action = "prepare_handover"
                self.get_logger().info(
                    "Robot action placeholder: handover is possible."
                )

        elif decision == "handover_not_ready":
            if self.robot_name == "jarvis":
                action = "wait_for_partner"
                self.get_logger().info(
                    "Jarvis action placeholder: wait at the transfer point until Gem is ready."
                )

            elif self.robot_name == "gem":
                action = "prepare_for_handover"
                self.get_logger().info(
                    "Gem action placeholder: not ready yet, continue preparing for handover."
                )

            else:
                action = "wait_for_partner"
                self.get_logger().info(
                    "Robot action placeholder: wait, handover is not ready."
                )

        elif decision == "handover_blocked_stale_status":
            action = "block_handover_stale_status"
            self.get_logger().warn(
                "Robot action placeholder: do not continue handover because a robot status is stale."
            )

        elif decision == "handover_not_requested":
            action = "normal_operation"
            self.get_logger().info(
                "Robot action placeholder: no handover currently requested, remain in normal state."
            )

        elif decision == "waiting_for_robot_statuses":
            action = "waiting_for_statuses"
            self.get_logger().info(
                "Robot action placeholder: coordinator is waiting for robot statuses."
            )

        else:
            action = "unknown_decision"
            self.get_logger().warn(
                f"Robot action placeholder: unknown decision received: {decision}"
            )

        self.publish_local_action(action, decision, reason)

    def publish_local_action(self, action, source_decision, reason):
        action_message = {
            "robot_name": self.robot_name,
            "action": action,
            "source_decision": source_decision,
            "reason": reason
        }

        msg = String()
        msg.data = json.dumps(action_message)

        self.local_action_publisher.publish(msg)

        self.get_logger().info(
            f"Published local action on {self.local_action_topic}: {action}"
        )


def main(args=None):
    rclpy.init(args=args)

    node = HandoverDecisionSubscriber()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        node.get_logger().info("Handover decision subscriber stopped.")

    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()