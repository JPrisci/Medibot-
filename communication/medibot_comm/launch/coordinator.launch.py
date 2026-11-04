from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="medibot_comm",
            executable="task_coordinator",
            name="task_coordinator",
            output="screen",
        ),

        Node(
            package="medibot_comm",
            executable="ux_api_adapter",
            name="ux_api_adapter",
            output="screen",
        ),

        Node(
            package="medibot_comm",
            executable="navigation_status_adapter",
            name="navigation_status_adapter",
            output="screen",
        ),

        Node(
            package="medibot_comm",
            executable="status_monitor",
            name="status_monitor",
            output="screen",
        ),
    ])