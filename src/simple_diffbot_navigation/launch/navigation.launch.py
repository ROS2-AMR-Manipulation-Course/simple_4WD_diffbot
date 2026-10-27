import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, SetEnvironmentVariable
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LoadComposableNodes, Node
from launch_ros.descriptions import ComposableNode, ParameterFile
from nav2_common.launch import RewrittenYaml


def generate_launch_description():
    pkg_path = get_package_share_directory('simple_diffbot_navigation')

    # Launch configuration
    namespace = LaunchConfiguration('namespace')
    use_sim_time = LaunchConfiguration('use_sim_time')
    autostart = LaunchConfiguration('autostart')
    params_file = LaunchConfiguration('params_file')
    use_composition = LaunchConfiguration('use_composition')
    container_name = LaunchConfiguration('container_name')
    container_name_full = (namespace, '/', container_name)
    use_respawn = LaunchConfiguration('use_respawn')
    log_level = LaunchConfiguration('log_level')
    controller_type = LaunchConfiguration('controller_type')
    controller_params_file = LaunchConfiguration('controller_params_file')

    lifecycle_nodes = ['controller_server',
                       'smoother_server',
                       'planner_server',
                       'behavior_server',
                       'bt_navigator',
                       'waypoint_follower',
                       'velocity_smoother',
                       'collision_monitor']

    remappings = [('/tf', 'tf'),
                  ('/tf_static', 'tf_static')]

    param_substitutions = {
        'use_sim_time': use_sim_time,
        'autostart': autostart}

    configured_params = ParameterFile(
        RewrittenYaml(
            source_file=params_file,
            root_key=namespace,
            param_rewrites=param_substitutions,
            convert_types=True),
        allow_substs=True)

    # Controller-specific file (controller_server + FollowPath), loaded after
    # configured_params so it overrides the common controller_server settings.
    configured_controller_params = ParameterFile(
        RewrittenYaml(
            source_file=controller_params_file,
            root_key=namespace,
            param_rewrites=param_substitutions,
            convert_types=True),
        allow_substs=True)

    stdout_linebuf_envvar = SetEnvironmentVariable(
        'RCUTILS_LOGGING_BUFFERED_STREAM', '1')

    declare_namespace = DeclareLaunchArgument(
        'namespace', default_value='', description='Top level namespace')

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use simulation (Gazebo) clock if true')

    declare_autostart = DeclareLaunchArgument(
        'autostart', default_value='true',
        description='Automatically startup the nav2 stack')

    declare_params_file = DeclareLaunchArgument(
        'params_file',
        default_value=os.path.join(pkg_path, 'config', 'nav2_params.yaml'),
        description='Full path to the Nav2 parameters file used by all nodes')

    declare_controller_type = DeclareLaunchArgument(
        'controller_type',
        default_value='mppi',
        choices=['pure_pursuit', 'mppi', 'dwb'],
        description="Controller to test: 'pure_pursuit', 'mppi', or 'dwb'. "
                    "Selects config/controller_<controller_type>.yaml as the default "
                    "controller_params_file.")

    declare_controller_params_file = DeclareLaunchArgument(
        'controller_params_file',
        default_value=[
            os.path.join(pkg_path, 'config', 'controller_'),
            controller_type,
            '.yaml'
        ],
        description='Full path to the controller params file')

    declare_use_composition = DeclareLaunchArgument(
        'use_composition', default_value='false',
        description='Use composed bringup if true')

    declare_container_name = DeclareLaunchArgument(
        'container_name', default_value='nav2_container',
        description='Name of the container the nodes load into when composing')

    declare_use_respawn = DeclareLaunchArgument(
        'use_respawn', default_value='False',
        description='Respawn nodes if they crash (composition disabled only)')

    declare_log_level = DeclareLaunchArgument(
        'log_level', default_value='info', description='log level')

    def nav_node(package, executable, name, params, extra_remaps=()):
        return Node(
            package=package,
            executable=executable,
            name=name,
            output='screen',
            respawn=use_respawn,
            respawn_delay=2.0,
            parameters=params,
            arguments=['--ros-args', '--log-level', log_level],
            remappings=remappings + list(extra_remaps))

    # controller -> cmd_vel_nav -> velocity_smoother -> cmd_vel_smoothed
    # -> collision_monitor -> /cmd_vel
    cmd_vel_nav = [('cmd_vel', 'cmd_vel_nav')]

    load_nodes = GroupAction(
        condition=UnlessCondition(use_composition),
        actions=[
            nav_node('nav2_controller', 'controller_server', 'controller_server',
                     [configured_params, configured_controller_params], cmd_vel_nav),
            nav_node('nav2_smoother', 'smoother_server', 'smoother_server',
                     [configured_params]),
            nav_node('nav2_planner', 'planner_server', 'planner_server',
                     [configured_params]),
            nav_node('nav2_behaviors', 'behavior_server', 'behavior_server',
                     [configured_params], cmd_vel_nav),
            nav_node('nav2_bt_navigator', 'bt_navigator', 'bt_navigator',
                     [configured_params]),
            nav_node('nav2_waypoint_follower', 'waypoint_follower', 'waypoint_follower',
                     [configured_params]),
            nav_node('nav2_velocity_smoother', 'velocity_smoother', 'velocity_smoother',
                     [configured_params], cmd_vel_nav),
            nav_node('nav2_collision_monitor', 'collision_monitor', 'collision_monitor',
                     [configured_params]),
            Node(
                package='nav2_lifecycle_manager',
                executable='lifecycle_manager',
                name='lifecycle_manager_navigation',
                output='screen',
                arguments=['--ros-args', '--log-level', log_level],
                parameters=[{'use_sim_time': use_sim_time},
                            {'autostart': autostart},
                            {'node_names': lifecycle_nodes}]),
        ]
    )

    load_composable_nodes = LoadComposableNodes(
        condition=IfCondition(use_composition),
        target_container=container_name_full,
        composable_node_descriptions=[
            ComposableNode(
                package='nav2_controller',
                plugin='nav2_controller::ControllerServer',
                name='controller_server',
                parameters=[configured_params, configured_controller_params],
                remappings=remappings + cmd_vel_nav),
            ComposableNode(
                package='nav2_smoother',
                plugin='nav2_smoother::SmootherServer',
                name='smoother_server',
                parameters=[configured_params],
                remappings=remappings),
            ComposableNode(
                package='nav2_planner',
                plugin='nav2_planner::PlannerServer',
                name='planner_server',
                parameters=[configured_params],
                remappings=remappings),
            ComposableNode(
                package='nav2_behaviors',
                plugin='behavior_server::BehaviorServer',
                name='behavior_server',
                parameters=[configured_params],
                remappings=remappings + cmd_vel_nav),
            ComposableNode(
                package='nav2_bt_navigator',
                plugin='nav2_bt_navigator::BtNavigator',
                name='bt_navigator',
                parameters=[configured_params],
                remappings=remappings),
            ComposableNode(
                package='nav2_waypoint_follower',
                plugin='nav2_waypoint_follower::WaypointFollower',
                name='waypoint_follower',
                parameters=[configured_params],
                remappings=remappings),
            ComposableNode(
                package='nav2_velocity_smoother',
                plugin='nav2_velocity_smoother::VelocitySmoother',
                name='velocity_smoother',
                parameters=[configured_params],
                remappings=remappings + cmd_vel_nav),
            ComposableNode(
                package='nav2_collision_monitor',
                plugin='nav2_collision_monitor::CollisionMonitor',
                name='collision_monitor',
                parameters=[configured_params],
                remappings=remappings),
            ComposableNode(
                package='nav2_lifecycle_manager',
                plugin='nav2_lifecycle_manager::LifecycleManager',
                name='lifecycle_manager_navigation',
                parameters=[{'use_sim_time': use_sim_time,
                             'autostart': autostart,
                             'node_names': lifecycle_nodes}]),
        ]
    )

    ld = LaunchDescription()

    ld.add_action(stdout_linebuf_envvar)

    ld.add_action(declare_namespace)
    ld.add_action(declare_use_sim_time)
    ld.add_action(declare_params_file)
    ld.add_action(declare_controller_type)  # must come before controller_params_file
    ld.add_action(declare_controller_params_file)
    ld.add_action(declare_autostart)
    ld.add_action(declare_use_composition)
    ld.add_action(declare_container_name)
    ld.add_action(declare_use_respawn)
    ld.add_action(declare_log_level)

    ld.add_action(load_nodes)
    ld.add_action(load_composable_nodes)

    return ld
