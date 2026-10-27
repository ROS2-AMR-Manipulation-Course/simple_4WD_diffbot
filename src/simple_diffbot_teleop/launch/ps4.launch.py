from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    joy_node = Node(
        package='joy',
        executable='joy_node',
        name='joy_node',
        output='screen',
    )

    ps4_node = Node(
        package='simple_diffbot_teleop',
        executable='ps4_node',
        name='ps4_node',
        output='screen',
    )

    return LaunchDescription([
        joy_node,
        ps4_node,
    ])