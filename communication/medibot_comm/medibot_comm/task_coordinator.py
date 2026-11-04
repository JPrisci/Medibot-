#!/usr/bin/env python3

"""
MediBot task coordinator.

This node performs high-level coordination of the MediBot visitor task.

UX-originated events are received on:

/medibot/ux_event

High-level Communication -> UX states are published on:

/medibot/ux_state

The coordinator observes:

/medibot/handover_decision
/medibot/navigation_event

Physical route requests are published on:

/medibot/jarvis/navigation_command
/medibot/gem/navigation_command

Current successful task flow:

destination_selected
    ->
Jarvis start_route -> ELEVATOR_2
    ->
handover_possible
    ->
wait for visitor_ready
    ->
Gem start_route -> retained final destination
    ->
arrived_at_destination
    ->
task_complete

Visitor identity is represented using user_id.

The user_id is retained only as temporary task/session context.
It does not determine navigation routing.

Reliability behaviour includes:
- rejecting destination selections while another task is active;
- rejecting visitor_ready at the wrong task stage;
- checking a supplied visitor_ready user_id against the active task;
- handling route_failed and route_aborted navigation results safely;
- publishing route failure/abort state to UX;
- and supporting an explicit task_reset event.

A route failure or abort does not automatically retry navigation. The active task
is placed into a failure/abort stage and remains there until an explicit task reset
or later recovery behaviour is deliberately implemented.

This node performs high-level coordination only.
It does not perform A* planning, odometry, obstacle avoidance,
cmd_vel control, direct Create3 control, or UX presentation.
"""

import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class TaskCoordinator(Node):
    def __init__(self):
        super().__init__("task_coordinator")

        # ------------------------------------------------------------------
        # Current high-level task state
        # ------------------------------------------------------------------

        self.final_destination = None
        self.user_id = None
        self.current_stage = "waiting_for_destination"
        self.active_robot = None
        self.transfer_point = "ELEVATOR_2"
        self.visitor_ready = False

        # ------------------------------------------------------------------
        # UX -> Communication
        # ------------------------------------------------------------------

        self.ux_event_subscription = self.create_subscription(
            String,
            "/medibot/ux_event",
            self.receive_ux_event,
            10,
        )

        # ------------------------------------------------------------------
        # Communication -> UX
        # ------------------------------------------------------------------

        self.ux_state_publisher = self.create_publisher(
            String,
            "/medibot/ux_state",
            10,
        )

        # ------------------------------------------------------------------
        # Communication handover decision -> TaskCoordinator
        # ------------------------------------------------------------------

        self.handover_decision_subscription = self.create_subscription(
            String,
            "/medibot/handover_decision",
            self.receive_handover_decision,
            10,
        )

        # ------------------------------------------------------------------
        # Navigation -> Communication task-level results
        # ------------------------------------------------------------------

        self.navigation_event_subscription = self.create_subscription(
            String,
            "/medibot/navigation_event",
            self.receive_navigation_event,
            10,
        )

        # ------------------------------------------------------------------
        # Communication -> Navigation
        # ------------------------------------------------------------------

        self.jarvis_navigation_publisher = self.create_publisher(
            String,
            "/medibot/jarvis/navigation_command",
            10,
        )

        self.gem_navigation_publisher = self.create_publisher(
            String,
            "/medibot/gem/navigation_command",
            10,
        )

        # ------------------------------------------------------------------
        # Startup information
        # ------------------------------------------------------------------

        self.get_logger().info("Task coordinator started.")

        self.get_logger().info(
            "Listening for UX events on /medibot/ux_event"
        )

        self.get_logger().info(
            "Publishing UX states on /medibot/ux_state"
        )

        self.get_logger().info(
            "Listening for handover decisions on "
            "/medibot/handover_decision"
        )

        self.get_logger().info(
            "Listening for task-level navigation results on "
            "/medibot/navigation_event"
        )

        self.get_logger().info(
            "Jarvis navigation commands will be published on "
            "/medibot/jarvis/navigation_command"
        )

        self.get_logger().info(
            "Gem navigation commands will be published on "
            "/medibot/gem/navigation_command"
        )

        self.get_logger().info(
            f"Initial task stage: {self.current_stage}"
        )

    def receive_ux_event(self, msg):
        """
        Process one incoming UX event.
        """

        try:
            event_data = json.loads(msg.data)

        except json.JSONDecodeError:
            self.get_logger().warn(
                f"UX event was not valid JSON: {msg.data}"
            )
            return

        if not isinstance(event_data, dict):
            self.get_logger().warn(
                "UX event was valid JSON, but it was not a JSON object."
            )
            return

        event = (
            str(event_data.get("event", ""))
            .lower()
            .strip()
        )

        if not event:
            self.get_logger().warn(
                "UX event is missing the 'event' field."
            )
            return

        self.get_logger().info(
            f"Received UX event: {event}"
        )

        if event == "destination_selected":
            self.handle_destination_selected(event_data)
            return

        if event == "visitor_ready":
            self.handle_visitor_ready(event_data)
            return

        if event == "task_reset":
            self.handle_task_reset()
            return

        self.get_logger().warn(
            f"UX event is not supported yet: {event}"
        )

    def handle_destination_selected(self, event_data):
        """
        Handle the initial visitor destination selection.
        """

        if self.current_stage != "waiting_for_destination":
            self.get_logger().warn(
                "Ignoring destination_selected because a visitor task "
                f"is already active at stage: {self.current_stage}"
            )
            return

        destination = (
            str(event_data.get("destination", ""))
            .upper()
            .strip()
        )

        user_id = (
            str(event_data.get("user_id", ""))
            .strip()
        )

        if not destination:
            self.get_logger().warn(
                "destination_selected event is missing the "
                "'destination' field."
            )
            return

        if destination != "DIGITAL_LIBRARY":
            self.get_logger().warn(
                f"Unsupported destination for the current prototype: "
                f"{destination}"
            )
            return

        if not user_id:
            self.get_logger().warn(
                "destination_selected event did not include user_id. "
                "The task can still continue."
            )
            self.user_id = None

        else:
            self.user_id = user_id

        self.final_destination = destination
        self.current_stage = "initial_guidance"
        self.active_robot = "jarvis"
        self.visitor_ready = False

        self.get_logger().info(
            "Destination selection accepted."
        )

        self.print_task_state()

        self.publish_navigation_command(
            robot_name="jarvis",
            destination=self.transfer_point,
        )

        self.publish_ux_state(
            state="initial_guidance"
        )

    def receive_handover_decision(self, msg):
        """
        Observe the existing coordinator handover decision.
        """

        try:
            decision_data = json.loads(msg.data)

        except json.JSONDecodeError:
            self.get_logger().warn(
                f"Handover decision was not valid JSON: {msg.data}"
            )
            return

        if not isinstance(decision_data, dict):
            self.get_logger().warn(
                "Handover decision was valid JSON, "
                "but it was not a JSON object."
            )
            return

        decision = (
            str(decision_data.get("decision", ""))
            .lower()
            .strip()
        )

        if not decision:
            self.get_logger().warn(
                "Handover decision is missing the 'decision' field."
            )
            return

        if decision == "handover_possible":
            if (
                self.final_destination is not None
                and self.active_robot == "jarvis"
                and self.current_stage == "initial_guidance"
            ):
                self.current_stage = "waiting_for_visitor_ready"

                self.get_logger().info(
                    "Handover is possible."
                )

                self.get_logger().info(
                    "Task stage changed to "
                    "waiting_for_visitor_ready."
                )

                self.print_task_state()

                self.publish_ux_state(
                    state="handover_ready"
                )

    def handle_visitor_ready(self, event_data):
        """
        Handle the visitor confirming that the handover has physically
        completed and that they are ready for Gem to continue guidance.
        """

        if self.current_stage != "waiting_for_visitor_ready":
            self.get_logger().warn(
                "Ignoring visitor_ready because the task is not "
                "waiting for post-handover visitor confirmation."
            )
            return

        if self.final_destination is None:
            self.get_logger().warn(
                "Cannot continue with Gem because no final destination "
                "is stored."
            )
            return

        supplied_user_id = event_data.get("user_id")

        if supplied_user_id is not None:
            if (
                not isinstance(supplied_user_id, str)
                or not supplied_user_id.strip()
            ):
                self.get_logger().warn(
                    "Ignoring visitor_ready because the supplied "
                    "user_id is invalid."
                )
                return

            supplied_user_id = supplied_user_id.strip()

            if (
                self.user_id is not None
                and supplied_user_id != self.user_id
            ):
                self.get_logger().warn(
                    "Ignoring visitor_ready because its user_id does "
                    "not match the active visitor task."
                )
                return

        self.visitor_ready = True
        self.active_robot = "gem"
        self.current_stage = "gem_route_requested"

        self.get_logger().info(
            "Visitor-ready confirmation accepted."
        )

        self.print_task_state()

        self.publish_navigation_command(
            robot_name="gem",
            destination=self.final_destination,
        )

        self.publish_ux_state(
            state="gem_guidance_started"
        )

    def receive_navigation_event(self, msg):
        """
        Observe high-level Navigation results that affect the overall task.
        """

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

        destination = (
            str(event_data.get("destination", ""))
            .upper()
            .strip()
        )

        reason = event_data.get("reason")

        if navigation_event == "arrived_at_destination":
            self.handle_arrived_at_destination(
                robot_name,
                destination,
            )
            return

        if navigation_event in (
            "route_failed",
            "route_aborted",
        ):
            self.handle_navigation_interruption(
                robot_name=robot_name,
                destination=destination,
                navigation_event=navigation_event,
                reason=reason,
            )

    def handle_arrived_at_destination(
        self,
        robot_name,
        destination,
    ):
        """
        Mark the active visitor task complete after Gem reaches the
        retained final destination.
        """

        if self.current_stage == "task_complete":
            self.get_logger().warn(
                "Ignoring arrived_at_destination because this task "
                "is already complete."
            )
            return

        if (
            self.current_stage != "gem_route_requested"
            or self.active_robot != "gem"
        ):
            self.get_logger().warn(
                "Ignoring arrived_at_destination because Gem is not "
                "currently responsible for the final guidance stage."
            )
            return

        if robot_name != "gem":
            self.get_logger().warn(
                f"Ignoring final destination arrival from unexpected "
                f"robot: {robot_name}"
            )
            return

        if not destination:
            self.get_logger().warn(
                "arrived_at_destination event is missing the "
                "'destination' field."
            )
            return

        if destination != self.final_destination:
            self.get_logger().warn(
                "Ignoring arrived_at_destination because the reported "
                f"destination {destination} does not match the active "
                f"task destination {self.final_destination}."
            )
            return

        self.current_stage = "task_complete"
        self.active_robot = None

        self.get_logger().info(
            f"Gem arrived at final destination: {destination}"
        )

        self.get_logger().info(
            "Visitor task marked complete."
        )

        self.print_task_state()

        self.publish_ux_state(
            state="task_complete"
        )

    def handle_navigation_interruption(
        self,
        robot_name,
        destination,
        navigation_event,
        reason=None,
    ):
        """
        Handle route_failed and route_aborted for the currently active route.

        The event must match the robot and destination currently expected by
        Communication. A valid failure/abort places the task into a blocked
        terminal stage. No automatic retry is issued.
        """

        if robot_name not in ("jarvis", "gem"):
            self.get_logger().warn(
                "Ignoring navigation interruption from unknown robot: "
                f"{robot_name}"
            )
            return

        if not destination:
            self.get_logger().warn(
                f"Ignoring {navigation_event} because the event is "
                "missing the 'destination' field."
            )
            return

        expected_robot = None
        expected_destination = None

        if (
            self.current_stage == "initial_guidance"
            and self.active_robot == "jarvis"
        ):
            expected_robot = "jarvis"
            expected_destination = self.transfer_point

        elif (
            self.current_stage == "gem_route_requested"
            and self.active_robot == "gem"
        ):
            expected_robot = "gem"
            expected_destination = self.final_destination

        else:
            self.get_logger().warn(
                f"Ignoring {navigation_event} because there is no "
                "matching active navigation route at task stage: "
                f"{self.current_stage}"
            )
            return

        if robot_name != expected_robot:
            self.get_logger().warn(
                f"Ignoring {navigation_event} from {robot_name} because "
                f"the active navigation robot is {expected_robot}."
            )
            return

        if destination != expected_destination:
            self.get_logger().warn(
                f"Ignoring {navigation_event} because destination "
                f"{destination} does not match the active route "
                f"destination {expected_destination}."
            )
            return

        self.current_stage = navigation_event

        self.get_logger().error(
            f"Navigation reported {navigation_event} for "
            f"robot={robot_name}, destination={destination}."
        )

        if reason is not None and str(reason).strip():
            self.get_logger().error(
                f"Navigation reason: {str(reason).strip()}"
            )

        self.get_logger().warn(
            "The visitor task has been stopped. No automatic route retry "
            "will be issued; use task_reset before starting a new task."
        )

        self.print_task_state()

        self.publish_ux_state(
            state=navigation_event,
            navigation_event=navigation_event,
            route_destination=destination,
            reason=reason,
        )

    def handle_task_reset(self):
        """
        Clear the current visitor task and return Communication to the
        initial waiting state.

        This can be used between user-study participants or after a
        task needs to be restarted.
        """

        previous_stage = self.current_stage

        self.final_destination = None
        self.user_id = None
        self.current_stage = "waiting_for_destination"
        self.active_robot = None
        self.visitor_ready = False

        self.get_logger().info(
            f"Visitor task reset from stage: {previous_stage}"
        )

        self.print_task_state()

        self.publish_ux_state(
            state="waiting_for_destination"
        )

    def publish_navigation_command(self, robot_name, destination):
        """
        Publish one high-level physical route request to Navigation.
        """

        robot_name = str(robot_name).lower().strip()
        destination = str(destination).upper().strip()

        command_data = {
            "command": "start_route",
            "destination": destination,
        }

        msg = String()
        msg.data = json.dumps(command_data)

        if robot_name == "jarvis":
            topic_name = "/medibot/jarvis/navigation_command"
            self.jarvis_navigation_publisher.publish(msg)

        elif robot_name == "gem":
            topic_name = "/medibot/gem/navigation_command"
            self.gem_navigation_publisher.publish(msg)

        else:
            self.get_logger().warn(
                f"Cannot publish navigation command for unknown robot: "
                f"{robot_name}"
            )
            return

        self.get_logger().info(
            f"Published navigation command on {topic_name}: "
            f"{msg.data}"
        )

    def publish_ux_state(
        self,
        state,
        navigation_event=None,
        route_destination=None,
        reason=None,
    ):
        """
        Publish one high-level Communication state for the UX component.
        """

        state_data = {
            "state": str(state).strip(),
            "current_stage": self.current_stage,
            "destination": self.final_destination,
            "active_robot": self.active_robot,
            "user_id": self.user_id,
            "visitor_ready": self.visitor_ready,
        }

        if navigation_event is not None:
            state_data["navigation_event"] = str(
                navigation_event
            ).strip()

        if route_destination is not None:
            state_data["route_destination"] = str(
                route_destination
            ).upper().strip()

        if reason is not None and str(reason).strip():
            state_data["reason"] = str(reason).strip()

        msg = String()
        msg.data = json.dumps(state_data)

        self.ux_state_publisher.publish(msg)

        self.get_logger().info(
            f"Published UX state on /medibot/ux_state: {msg.data}"
        )

    def print_task_state(self):
        """
        Print the currently stored high-level task state.
        """

        displayed_user_id = (
            self.user_id
            if self.user_id is not None
            else "not supplied"
        )

        displayed_active_robot = (
            self.active_robot
            if self.active_robot is not None
            else "none"
        )

        displayed_destination = (
            self.final_destination
            if self.final_destination is not None
            else "none"
        )

        self.get_logger().info(
            "----- Current MediBot task state -----"
        )

        self.get_logger().info(
            f"final_destination={displayed_destination}"
        )

        self.get_logger().info(
            f"user_id={displayed_user_id}"
        )

        self.get_logger().info(
            f"current_stage={self.current_stage}"
        )

        self.get_logger().info(
            f"active_robot={displayed_active_robot}"
        )

        self.get_logger().info(
            f"transfer_point={self.transfer_point}"
        )

        self.get_logger().info(
            f"visitor_ready={self.visitor_ready}"
        )

        self.get_logger().info(
            "--------------------------------------"
        )


def main(args=None):
    rclpy.init(args=args)

    node = TaskCoordinator()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        node.get_logger().info(
            "Task coordinator stopped."
        )

    finally:
        node.destroy_node()

        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()