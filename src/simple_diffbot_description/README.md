# simple_diffbot_description

URDF/Xacro model of a 4-wheel differential-drive (skid-steer) educational robot for ROS 2 Jazzy.
All four wheels are conventional and driven (left pair / right pair); there are no mecanum or caster wheels.
The package also holds the Gazebo Harmonic plugin and sensor definitions (`gazebo.xacro`), so the
same description is used for RViz visualisation and for simulation in `simple_diffbot_gazebo`.

## Contents
- [Package layout](#package-layout)
- [Build and view](#build-and-view)
- [Launch arguments](#launch-arguments)
- [Robot parameters](#robot-parameters)
- [Frames and TF tree](#frames-and-tf-tree)
- [Sensors](#sensors)
- [Gazebo plugins](#gazebo-plugins)
- [Xacro arguments](#xacro-arguments)
- [Validating the model](#validating-the-model)
- [Dependencies](#dependencies)
- [Not included yet](#not-included-yet)

## Package layout
```
simple_diffbot_description/
├── urdf/
│   ├── simple_diffbot.urdf.xacro   # entry point: parameters, chassis, logo decals, includes
│   ├── wheel.xacro                 # `wheel` macro (link + continuous joint)
│   ├── sensors.xacro               # LiDAR, IMU, camera links and joints
│   ├── gazebo.xacro                # `gz_plugins` macro: DiffDrive, JointStatePublisher, sensors, friction
│   └── inertial_macros.xacro       # box / cylinder inertia helpers
├── launch/display.launch.py        # robot_state_publisher + joint_state_publisher_gui + RViz
├── rviz/display.rviz               # RViz configuration
└── meshes/                         # logo_plane.dae and textures/ai_farm_logo.png (side decals)
```
`urdf`, `launch`, `rviz` and `meshes` are installed to `share/simple_diffbot_description`.

## Build and view
```bash
cd ~/work_ros2/simple_diffbot_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install --packages-select simple_diffbot_description
source install/setup.bash
ros2 launch simple_diffbot_description display.launch.py
```
This starts `robot_state_publisher`, the `joint_state_publisher_gui` sliders (to turn the wheels by hand)
and RViz with the saved configuration.

## Launch arguments
`display.launch.py`:

| Argument | Default | Description |
|---|---|---|
| `use_gui` | `true` | Open `joint_state_publisher_gui` sliders |
| `rviz` | `true` | Start RViz |
| `wheel_track` | `0.255` | Centre-to-centre wheel track (m), forwarded to xacro |

Example: `ros2 launch simple_diffbot_description display.launch.py use_gui:=false rviz:=false`

## Robot parameters
Defined in `urdf/simple_diffbot.urdf.xacro`.

| Parameter | Value |
|---|---|
| Chassis (L x W x H) | 0.30 x 0.22 x 0.12 m, 3.0 kg |
| Ground clearance | 0.02 m |
| Wheel radius / width / mass | 0.05 m / 0.025 m / 0.2 kg |
| Wheel x offset from `base_link` | ±0.10 m (front / rear axles) |
| Wheel track | 0.255 m |
| Wheel side gap | 0.005 m |
| LiDAR x offset | +0.05 m |
| Skid-steer factor | 1.4 |

**Wheel track.** A 0.18 m track would put the wheels (y = ±0.09 m, occupying 0.0775–0.1025 m) inside the
0.22 m wide chassis (half-width 0.11 m). The default is therefore derived as
`chassis_width + wheel_width + 2 * wheel_side_gap = 0.22 + 0.025 + 0.01 = 0.255 m`.
Xacro raises an error if `wheel_track < chassis_width + wheel_width`.

**Skid-steer factor.** A 4-wheel skid-steer robot slips when turning, so the geometric track
under-estimates the effective separation. Gazebo's DiffDrive uses
`wheel_separation = wheel_track * skid_steer_factor` (0.255 * 1.4 = 0.357 m). To calibrate, command a
known `angular.z` and compare the `/odom` yaw with the true yaw; `1.0` is the ideal (no-slip) case.

## Frames and TF tree
Conventions follow REP-103: X forward, Y left, Z up.

```
base_footprint              (on the ground, wheel_radius below base_link)
└── base_link               (at axle height, centre of the wheel rectangle)
    ├── front_left_wheel_link    (continuous)
    ├── rear_left_wheel_link     (continuous)
    ├── front_right_wheel_link   (continuous)
    ├── rear_right_wheel_link    (continuous)
    ├── logo_left_link / logo_right_link   (fixed, visual-only decals on the chassis sides)
    ├── laser_link               (fixed, top of chassis, x = +0.05)
    ├── imu_link                 (fixed, chassis centre)
    └── camera_link              (fixed, front face)
        └── camera_optical_frame (fixed; Z forward, X right, Y down)
```
Wheel joints: `front_left_wheel_joint`, `rear_left_wheel_joint`, `front_right_wheel_joint`,
`rear_right_wheel_joint`. The wheel joint axis is `base_link` +Y, so a positive rotation drives the robot
forward on every wheel. Wheel joints have damping and friction of 0.01.

## Sensors
Links are defined in `sensors.xacro`; the Gazebo sensor definitions are in `gazebo.xacro`.

| Sensor | Frame | Rate | Details | Gazebo topic |
|---|---|---|---|---|
| 2D LiDAR (`gpu_lidar`) | `laser_link` | 30 Hz | 640 samples over ±π (360°), range 0.12–8.0 m, Gaussian noise σ = 0.01 | `/scan` |
| IMU | `imu_link` | 50 Hz | Gaussian noise and bias on angular velocity and linear acceleration | `/imu` |
| RGB-D camera | `camera_optical_frame` | 15 Hz | 320 x 240 `R8G8B8`, horizontal FOV 1.396 rad (80°), clip 0.1–8 m | `/camera/image`, `/camera/depth_image`, `/camera/points`, `/camera/camera_info` |

Gazebo cameras look along +X of the link, which matches `camera_link`. The sensor data is published with
`camera_optical_frame` as its frame id.

## Gazebo plugins
`urdf/gazebo.xacro` provides the `gz_plugins` macro, which `simple_diffbot.urdf.xacro` instantiates.

- **JointStatePublisher** – publishes the four wheel joints on `/joint_states` at 50 Hz.
- **DiffDrive** – left joints `front_left`/`rear_left`, right joints `front_right`/`rear_right`.
  Listens on `/cmd_vel` and publishes `/odom` (frame `odom`, child `base_footprint`) at 50 Hz.
  `publish_odom_tf` is `false`: the `odom -> base_footprint` TF must come from an EKF
  (`simple_diffbot_localization`). `publish_wheel_tf` is `true`.
  Limits: ±1.0 m/s and ±2.0 rad/s, with acceleration limits ±1.0 m/s² and ±2.0 rad/s².
- **Wheel friction** – `mu = mu2 = 0.4` on each wheel, low enough for the wheels to scrub sideways while turning.
- **Sensors** – IMU, LiDAR and RGB-D camera, as listed above. The world must load the `Sensors` system
  (with a render engine) and the `Imu` system for these to publish; the worlds in `simple_diffbot_gazebo` do.

## Xacro arguments
| Argument | Default | Description |
|---|---|---|
| `wheel_track` | `0.255` | Wheel centre-to-centre track (m) |
| `skid_steer_factor` | `1.4` | Multiplier applied to `wheel_track` for DiffDrive's `wheel_separation` |

Example: `xacro urdf/simple_diffbot.urdf.xacro wheel_track:=0.28 skid_steer_factor:=1.2`

## Validating the model
```bash
xacro $(ros2 pkg prefix simple_diffbot_description)/share/simple_diffbot_description/urdf/simple_diffbot.urdf.xacro > /tmp/diffbot.urdf
check_urdf /tmp/diffbot.urdf
```

## Dependencies
- Build: `ament_cmake`, `xacro`, `robot_state_publisher`, `rviz2`, `urdf`
- Run: `joint_state_publisher_gui`, `launch`, `launch_ros`, `ament_index_python`
- Simulation (separate package): `simple_diffbot_gazebo`

## Not included yet
No `ros2_control` tags. When added, the controlled joints will be `front_left_wheel_joint`,
`rear_left_wheel_joint`, `front_right_wheel_joint` and `rear_right_wheel_joint`
(wheel radius 0.05 m, wheel separation 0.255 m, or the skid-steer adjusted value).

## License
Apache-2.0
