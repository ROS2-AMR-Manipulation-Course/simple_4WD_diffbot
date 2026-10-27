# simple_diffbot_gazebo

Gazebo Harmonic worlds, robot spawning and the `ros_gz_bridge` configuration for `simple_diffbot`
(ROS 2 Jazzy). The robot model, plugins and sensors come from `simple_diffbot_description`; this package
starts the simulator, spawns the robot and bridges Gazebo topics to ROS 2.

## Contents
- [Package layout](#package-layout)
- [Build and launch](#build-and-launch)
- [Launch files and arguments](#launch-files-and-arguments)
- [Worlds](#worlds)
- [Topic bridge](#topic-bridge)
- [TF and odometry](#tf-and-odometry)
- [Dynamic obstacles](#dynamic-obstacles)
- [Driving the robot](#driving-the-robot)
- [Troubleshooting](#troubleshooting)
- [Dependencies](#dependencies)

## Package layout
```
simple_diffbot_gazebo/
├── config/bridge_config.yaml       # ros_gz_bridge topic list
├── launch/
│   ├── gazebo.launch.py            # Gazebo server + GUI + spawn (main entry point)
│   └── spawn.launch.py             # robot_state_publisher + create + parameter_bridge
├── worlds/
│   ├── classroom.sdf               # furnished 10 x 8 m classroom with two moving obstacles
│   └── empty.sdf                   # ground plane, a box and a cylinder
└── scripts/patrol_obstacle.sh      # moves the classroom's dynamic obstacles back and forth
```
`launch`, `worlds` and `config` are installed to `share/simple_diffbot_gazebo`
(`scripts/` is not installed; run it from the source tree).

## Build and launch
```bash
cd ~/work_ros2/simple_diffbot_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select simple_diffbot_description simple_diffbot_gazebo
source install/setup.bash
ros2 launch simple_diffbot_gazebo gazebo.launch.py
```
Examples:
```bash
ros2 launch simple_diffbot_gazebo gazebo.launch.py world:=empty.sdf
ros2 launch simple_diffbot_gazebo gazebo.launch.py x:=-2.0 y:=1.0 yaw:=1.57
ros2 launch simple_diffbot_gazebo gazebo.launch.py gui_after_spawn:=false   # normal single-process start
```

## Launch files and arguments
### `gazebo.launch.py`
Starts Gazebo with the chosen world and includes `spawn.launch.py`. It appends the package's `worlds`
directory to `GZ_SIM_RESOURCE_PATH`.

| Argument | Default | Description |
|---|---|---|
| `world` | `classroom.sdf` | World file in `simple_diffbot_gazebo/worlds` |
| `gui_after_spawn` | `true` | Run the server headless (`-s -r`) and start the GUI (`gz sim -g`) after a delay, so the GUI builds its scene with the robot already present. `false` runs server and GUI together (`-r`) |
| `gui_delay` | `12.0` | Seconds to wait before starting the GUI (only with `gui_after_spawn:=true`) |
| `x`, `y` | `0.0` | Spawn position (m) |
| `yaw` | `0.0` | Spawn heading (rad) |

The simulation starts running immediately (`-r`) and Gazebo exits when it is shut down
(`on_exit_shutdown`).

### `spawn.launch.py`
Use this on its own to add the robot to an already running Gazebo.
It starts three nodes:
- `robot_state_publisher` – processes the xacro and publishes `robot_description` (`use_sim_time: true`)
- `ros_gz_sim create` – spawns the model `simple_diffbot` from the `robot_description` topic
- `ros_gz_bridge parameter_bridge` – loads `config/bridge_config.yaml`

| Argument | Default | Description |
|---|---|---|
| `x`, `y` | `0.0` | Spawn position (m) |
| `z` | `0.1` | Spawn height (m); drops onto the ground |
| `yaw` | `0.0` | Spawn heading (rad) |

## Worlds
Both worlds use 1 ms physics steps (`classroom.sdf` also sets real-time factor 1.0) and load the
Physics, UserCommands, SceneBroadcaster, Sensors (`ogre2`) and Imu systems, which the robot's LiDAR,
camera and IMU need.

| World | Description |
|---|---|
| `classroom.sdf` (`classroom_world`) | Closed room of about 10 x 8 m with four walls, three rows of student desks and chairs on each side, a teacher's desk, whiteboard, bookshelf, cabinet, storage box, trash bin, a pillar and two dynamic obstacles. Good for SLAM and navigation |
| `empty.sdf` (`empty_world`) | Ground plane with a box and a cylinder. Good for quick sensor and drive tests |

## Topic bridge
Configured in `config/bridge_config.yaml`.

| ROS topic | ROS type | Gazebo type | Direction |
|---|---|---|---|
| `/clock` | `rosgraph_msgs/Clock` | `gz.msgs.Clock` | Gazebo -> ROS |
| `/cmd_vel` | `geometry_msgs/Twist` | `gz.msgs.Twist` | ROS -> Gazebo |
| `/odom` | `nav_msgs/Odometry` | `gz.msgs.Odometry` | Gazebo -> ROS |
| `/tf` | `tf2_msgs/TFMessage` | `gz.msgs.Pose_V` | Gazebo -> ROS |
| `/joint_states` | `sensor_msgs/JointState` | `gz.msgs.Model` | Gazebo -> ROS |
| `/imu` | `sensor_msgs/Imu` | `gz.msgs.IMU` | Gazebo -> ROS |
| `/scan` | `sensor_msgs/LaserScan` | `gz.msgs.LaserScan` | Gazebo -> ROS |
| `/camera/image_raw` (Gazebo `/camera/image`) | `sensor_msgs/Image` | `gz.msgs.Image` | Gazebo -> ROS |
| `/camera/depth_image` | `sensor_msgs/Image` | `gz.msgs.Image` | Gazebo -> ROS |
| `/camera/points` | `sensor_msgs/PointCloud2` | `gz.msgs.PointCloudPacked` | Gazebo -> ROS |
| `/camera/camera_info` | `sensor_msgs/CameraInfo` | `gz.msgs.CameraInfo` | Gazebo -> ROS |
| `/dynamic_obstacle/cmd_vel` | `geometry_msgs/Twist` | `gz.msgs.Twist` | ROS -> Gazebo |
| `/dynamic_obstacle_2/cmd_vel` | `geometry_msgs/Twist` | `gz.msgs.Twist` | ROS -> Gazebo |

The point cloud is in `camera_optical_frame` and is intended for a Nav2 voxel layer.
To bridge another topic, add an entry to `bridge_config.yaml` (and rebuild, or use `--symlink-install`).

## TF and odometry
- `robot_state_publisher` provides the static robot tree (`base_footprint` -> `base_link` -> links and sensors)
  and the wheel transforms from `/joint_states`.
- The DiffDrive plugin publishes `/odom` but **not** the `odom -> base_footprint` TF
  (`publish_odom_tf=false`). That TF comes from the EKF in `simple_diffbot_localization`
  (for SLAM and navigation). Launch it, otherwise `odom` will be missing from the TF tree.
- All nodes should run with `use_sim_time:=true`; the simulation clock is bridged on `/clock`.

## Dynamic obstacles
`classroom.sdf` contains two cylinders (`dynamic_obstacle` at start pose (-2, 1.5) and `dynamic_obstacle_2`),
each driven by a `VelocityControl` plugin. Command them with the bridged topics, or run the patrol script:

```bash
# from the package source directory
./scripts/patrol_obstacle.sh [speed m/s] [seconds per leg]   # defaults: 0.5 m/s, 8 s
```
`dynamic_obstacle` patrols along x and `dynamic_obstacle_2` along y, reversing every leg.
Ctrl+C stops both. Manual command:
```bash
ros2 topic pub --once /dynamic_obstacle/cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.3}}"
```

## Driving the robot
```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard        # needs ros-jazzy-teleop-twist-keyboard
ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.2}, angular: {z: 0.0}}"
```
The DiffDrive plugin limits speeds to ±1.0 m/s and ±2.0 rad/s.

Check the sensors:
```bash
ros2 topic hz /scan
ros2 topic echo /odom --once
ros2 run rviz2 rviz2 --ros-args -p use_sim_time:=true
```

## Troubleshooting
- **No `/scan`, `/imu` or camera data** – the world must load the Sensors and Imu systems (the provided worlds
  do), and `ogre2` rendering must work on your machine.
- **`odom` frame missing in TF** – expected without the EKF, see [TF and odometry](#tf-and-odometry).
- **Robot not visible in the GUI** – use the default `gui_after_spawn:=true`, or increase `gui_delay`.
- **Robot turns by the wrong angle in odometry** – tune `skid_steer_factor` in `simple_diffbot_description`.
- **Nodes show stale time** – set `use_sim_time:=true`.

## Dependencies
`simple_diffbot_description`, `ros_gz_sim`, `ros_gz_bridge`, `robot_state_publisher`, `xacro`,
`launch`, `launch_ros`, `ament_index_python`

## License
Apache-2.0
