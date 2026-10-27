# simple_diffbot_localization

Wheel-odometry + IMU fusion (`robot_localization` EKF) and map-based localization (Nav2 `map_server` + `amcl`).

## Build and launch
```bash
cd ~/work_ros2/simple_diffbot_ws
colcon build --symlink-install --packages-select simple_diffbot_localization
source install/setup.bash
ros2 launch simple_diffbot_localization ekf.launch.py            # EKF only (use for SLAM)
ros2 launch simple_diffbot_localization localization.launch.py   # EKF + map_server + AMCL
```
`localization.launch.py` arguments: `map` (default `simple_diffbot_slam/maps/class_room.yaml`),
`use_ekf:=true`, `use_sim_time:=true`, `autostart:=true`, `use_composition:=False`,
`localization_params_file`, `ekf_params_file`, `namespace`, `use_respawn`, `log_level`.

Set the initial pose with RViz "2D Pose Estimate", or in `config/amcl.yaml` (`initial_pose`, default 0, 0, 0).

## Topics and frames
| | |
|---|---|
| EKF subscribes | `/odom`, `/imu` |
| EKF publishes | `/odometry/filtered`, TF `odom -> base_footprint` |
| AMCL subscribes | `/scan`, `/map`, `/initialpose` |
| AMCL publishes | `/amcl_pose`, TF `map -> odom` |
| `map_server` publishes | `/map` |

## Config
- `config/ekf.yaml` – 2D mode, 30 Hz, world frame `odom`. Fuses vx, vy and yaw rate from `/odom`, and yaw rate from `/imu`.
- `config/amcl.yaml` – differential motion model, likelihood-field laser model, 500–2000 particles, `scan_topic: scan`, plus `map_server` settings.

## EKF configuration (`config/ekf.yaml`)
`robot_localization` `ekf_node` fuses wheel odometry and the IMU into `/odometry/filtered` and publishes `odom -> base_footprint`.

| Parameter | Value | Meaning |
|---|---|---|
| `frequency` | 30.0 | Filter and output rate in Hz. Match or stay below the fastest sensor. |
| `two_d_mode` | true | Planar robot: forces z, roll, pitch and their velocities to zero. Keep `true` for a ground robot. |
| `publish_tf` | true | EKF publishes the `odom -> base_footprint` transform. Make sure nothing else (such as the DiffDrive plugin) publishes the same one. |
| `world_frame` | `odom` | Frame the state is estimated in. `odom` gives smooth, continuous pose; AMCL supplies `map -> odom`. |
| `odom_frame`, `base_link_frame`, `map_frame` | `odom`, `base_footprint`, `map` | Must match the frames in the URDF and Nav2. |

### What is fused
Each `*_config` list has 15 booleans in this order:
```
[ x,  y,  z,   roll,  pitch,  yaw,   vx,  vy,  vz,   vroll,  vpitch,  vyaw,   ax,  ay,  az ]
```
| Source | Fused | Why |
|---|---|---|
| `odom0` (`/odom`) | `vx`, `vy`, `vyaw` | Body-frame velocities only. The differential drive cannot move sideways, so `vy` is always about 0 and acts as a no-slip constraint. Pose is not fused, so odometry drift is not double counted. |
| `imu0` (`/imu`) | `vyaw` | The gyro yaw rate is accurate over short periods. Absolute yaw is left out to avoid heading jumps from a poorly calibrated magnetometer or orientation estimate. |

### Parameters to tune
| Parameter | Default | When and how to tune |
|---|---|---|
| `process_noise_covariance` | library default | Not set in this file. **Raise** values (for example yaw and `vx`) if the filter is slow to follow real motion; **lower** them if the output is noisy. Tune the diagonal only. |
| `initial_estimate_covariance` | library default | Only matters at startup. Rarely needs changing. |
| `odom0_config` / `imu0_config` | see above | Fuse only what the sensor measures well. Turning on more states than needed makes the filter trust noisy ones. |
| `odom0_differential`, `imu0_differential` | false | `true` fuses changes between messages. Use it for sensors that drift in absolute value. |
| `odom0_queue_size`, `imu0_queue_size` | 1 | Raise to 10 or more if messages are dropped at the sensor's rate. |
| `odom0_nodelay`, `imu0_nodelay` | false | Set `true` only if `use_sim_time` and message stamps cause late-message drops. |
| `imu0_remove_gravitational_acceleration` | false | Needed only if linear acceleration is fused. |
| `sensor_timeout` | 1/frequency | Raise if a sensor publishes slower than the filter rate. |

The measurement covariance comes from each message. If `/odom` publishes zero covariance, the EKF trusts it completely. Check with:
```bash
ros2 topic echo /odom --field twist.covariance --once
```
and set non-zero values in the Gazebo DiffDrive/odometry source (or per-sensor overrides) if they are all zeros.

### Checking the filter
```bash
ros2 topic hz /odometry/filtered
ros2 run tf2_ros tf2_echo odom base_footprint
ros2 topic echo /odometry/filtered --field twist.twist
```
Drive the robot in a straight line and a full circle; the filtered yaw should return to its start value within a few degrees and the output should not oscillate.

## AMCL configuration (`config/amcl.yaml`)
AMCL matches the laser scan against the map with a particle filter and publishes `map -> odom`.

| Parameter | Value | Effect and how to tune |
|---|---|---|
| `alpha1`–`alpha4` | 0.2 | Motion-model noise (rotation from rotation, rotation from translation, translation from translation, translation from rotation). Raise if the particle cloud is too tight and loses the robot after slips; lower for good odometry. `alpha5` is unused by the differential model. |
| `min_particles`, `max_particles` | 500, 2000 | More particles are more robust but cost CPU. Lower both for small maps. |
| `max_beams` | 60 | Beams used per scan. More beams are more accurate but slower; 30 to 100 is typical. |
| `laser_model_type` | `likelihood_field` | Fast and robust. `beam` is slower and rarely needed. |
| `laser_likelihood_max_dist` | 2.0 | Obstacle inflation distance in the likelihood field. Smaller trusts only close matches. |
| `sigma_hit` | 0.2 | Standard deviation of laser noise. Lower (about 0.05 to 0.1) if the lidar is accurate, as in the simulator. |
| `z_hit`, `z_rand`, `z_short`, `z_max` | 0.5, 0.5, 0.05, 0.05 | Weights of the sensor model. They should sum to 1, and they currently sum to 1.1. For `likelihood_field`, only `z_hit` and `z_rand` are used, so something like 0.95 and 0.05 is more usual. |
| `update_min_d`, `update_min_a` | 0.25, 0.2 | Motion needed before a filter update. Lower for faster correction at the cost of CPU. |
| `resample_interval` | 1 | Resample after every update. Raise to reduce particle depletion. |
| `recovery_alpha_fast`, `recovery_alpha_slow` | 0.0 | Zero disables random-particle recovery. Set to about 0.1 and 0.001 to recover from a kidnapped robot. |
| `transform_tolerance` | 1.0 | Time (s) the published TF is forward-dated. Too low gives "extrapolation" errors; too high hides delays. |
| `set_initial_pose`, `initial_pose` | true, (0, 0, 0) | Where AMCL starts. Use RViz "2D Pose Estimate" for any other start. |
| `tf_broadcast` | true | Publish `map -> odom`. Disable only if another node does it. |

Symptoms and fixes:
- **Cloud spreads and pose jumps:** odometry is poor. Check the EKF output first, then raise `alpha1`–`alpha4`.
- **Pose drifts in a long featureless corridor:** the scan has no features. Nothing in AMCL tuning fixes this.
- **"Message Filter dropping message" or extrapolation errors:** a clock mismatch. Make sure every node uses `use_sim_time:=true`.

## References
- robot_localization (EKF) state estimation nodes and parameters: https://docs.ros.org/en/noetic/api/robot_localization/html/state_estimation_nodes.html
- robot_localization configuration: https://docs.ros.org/en/noetic/api/robot_localization/html/configuring_robot_localization.html
- Nav2 AMCL (Jazzy): https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/others/configuring_amcl/
- Nav2 Map Server (Jazzy): https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/map_server/
- Nav2 First-Time Robot Setup Guide (Jazzy): https://docs.nav2.org/jazzy/configuration_and_development/first_time_robot_setup_guide/

## Files
```
config/ekf.yaml, amcl.yaml
launch/ekf.launch.py, localization.launch.py
```

## Dependencies
`robot_localization`, `nav2_amcl`, `nav2_map_server`, `nav2_lifecycle_manager`, `nav2_common`, `simple_diffbot_slam` (default map)
