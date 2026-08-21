from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    robot_name = LaunchConfiguration("robot_name")

    return LaunchDescription([
        DeclareLaunchArgument(
            "robot_name",
            default_value="jarvis",
            choices=["jarvis", "gem"],
            description="Robot role for the robot-side Communication nodes.",
        ),

        Node(
            package="medibot_comm",
            executable="handover_decision_subscriber",
            namespace=robot_name,
            output="screen",
            parameters=[
                {"robot_name": robot_name},
            ],
        ),

        Node(
            package="medibot_comm",
            executable="local_action_subscriber",
            namespace=robot_name,
            output="screen",
            parameters=[
                {"robot_name": robot_name},
            ],
        ),
    ])