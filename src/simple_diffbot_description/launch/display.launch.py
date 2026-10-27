import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    pkg = get_package_share_directory('simple_diffbot_description')
    xacro_file = os.path.join(pkg, 'urdf', 'simple_diffbot.urdf.xacro')
    rviz_file = os.path.join(pkg, 'rviz', 'display.rviz')

    wheel_track = LaunchConfiguration('wheel_track')
    robot_description = ParameterValue(
        Command(['xacro ', xacro_file, ' wheel_track:=', wheel_track]), value_type=str)

    return LaunchDescription([
        DeclareLaunchArgument('wheel_track', default_value='0.255'),
        DeclareLaunchArgument('use_gui', default_value='true',
                              description='Open joint_state_publisher_gui sliders'),
        DeclareLaunchArgument('rviz', default_value='true'),
        Node(package='robot_state_publisher', executable='robot_state_publisher',
             parameters=[{'robot_description': robot_description}]),
        Node(package='joint_state_publisher_gui', executable='joint_state_publisher_gui',
             condition=IfCondition(LaunchConfiguration('use_gui'))),
        Node(package='rviz2', executable='rviz2', arguments=['-d', rviz_file],
             condition=IfCondition(LaunchConfiguration('rviz'))),
    ])
