#!/usr/bin/env python3
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (AppendEnvironmentVariable, DeclareLaunchArgument,
                            ExecuteProcess, IncludeLaunchDescription, TimerAction)
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution


def generate_launch_description():
    gz_share = get_package_share_directory('simple_diffbot_gazebo')
    ros_gz_sim_share = get_package_share_directory('ros_gz_sim')

    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim_share, 'launch', 'gz_sim.launch.py')),
        launch_arguments={
            'gz_args': ['-r -v 3 ',
                        PathJoinSubstitution([gz_share, 'worlds',
                                              LaunchConfiguration('world')])],
            'on_exit_shutdown': 'true',
        }.items(),
        condition=UnlessCondition(LaunchConfiguration('gui_after_spawn')),
    )

    # Alternative start-up: headless server first, GUI only after the robot is spawned, so the
    # GUI builds its scene with the robot already in the world.
    gz_server = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim_share, 'launch', 'gz_sim.launch.py')),
        launch_arguments={
            'gz_args': ['-s -r -v 3 ',
                        PathJoinSubstitution([gz_share, 'worlds',
                                              LaunchConfiguration('world')])],
            'on_exit_shutdown': 'true',
        }.items(),
        condition=IfCondition(LaunchConfiguration('gui_after_spawn')),
    )
    gz_gui = TimerAction(
        period=LaunchConfiguration('gui_delay'),
        actions=[ExecuteProcess(cmd=['gz', 'sim', '-g', '-v', '3'], output='screen')],
        condition=IfCondition(LaunchConfiguration('gui_after_spawn')),
    )

    spawn = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gz_share, 'launch', 'spawn.launch.py')),
        launch_arguments={
            'x': LaunchConfiguration('x'),
            'y': LaunchConfiguration('y'),
            'yaw': LaunchConfiguration('yaw'),
        }.items(),
    )

    return LaunchDescription([
        AppendEnvironmentVariable('GZ_SIM_RESOURCE_PATH',
                                  os.path.join(gz_share, 'worlds')),
        DeclareLaunchArgument('world', default_value='classroom.sdf',
                              description='World file in simple_diffbot_gazebo/worlds'),
        DeclareLaunchArgument('gui_after_spawn', default_value='true',
                              description='Start the GUI only after the robot is spawned'),
        DeclareLaunchArgument('gui_delay', default_value='12.0',
                              description='Seconds to wait before starting the GUI'),
        DeclareLaunchArgument('x', default_value='0.0'),
        DeclareLaunchArgument('y', default_value='0.0'),
        DeclareLaunchArgument('yaw', default_value='0.0'),
        spawn,
        gz_sim,
        gz_server,
        gz_gui,
        
    ])
