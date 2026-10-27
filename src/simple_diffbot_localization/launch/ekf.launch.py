import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile
from nav2_common.launch import RewrittenYaml


def generate_launch_description():
    pkg_path = get_package_share_directory('simple_diffbot_localization')

    namespace = LaunchConfiguration('namespace')
    use_sim_time = LaunchConfiguration('use_sim_time')
    ekf_params_file = LaunchConfiguration('ekf_params_file')
    use_respawn = LaunchConfiguration('use_respawn')
    log_level = LaunchConfiguration('log_level')

    remappings = [('/tf', 'tf'),
                  ('/tf_static', 'tf_static')]

    configured_params = ParameterFile(
        RewrittenYaml(
            source_file=ekf_params_file,
            root_key=namespace,
            param_rewrites={'use_sim_time': use_sim_time},
            convert_types=True),
        allow_substs=True)

    ekf = Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        respawn=use_respawn,
        respawn_delay=2.0,
        parameters=[configured_params],
        arguments=['--ros-args', '--log-level', log_level],
        remappings=remappings)

    return LaunchDescription([
        DeclareLaunchArgument('namespace', default_value='',
                              description='Top-level namespace'),
        DeclareLaunchArgument('use_sim_time', default_value='true',
                              description='Use simulation (Gazebo) clock if true'),
        DeclareLaunchArgument(
            'ekf_params_file',
            default_value=os.path.join(pkg_path, 'config', 'ekf.yaml'),
            description='Full path to the EKF parameters file'),
        DeclareLaunchArgument('use_respawn', default_value='False',
                              description='Whether to respawn if the node crashes'),
        DeclareLaunchArgument('log_level', default_value='info',
                              description='log level'),
        ekf,
    ])
