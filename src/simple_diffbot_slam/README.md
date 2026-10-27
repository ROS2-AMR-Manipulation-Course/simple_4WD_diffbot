# simple_diffbot_slam

Mapping with `slam_toolbox` (online async). Also stores the saved maps used by localization and navigation.

## Build and launch
```bash
cd ~/work_ros2/simple_diffbot_ws
colcon build --symlink-install --packages-select simple_diffbot_slam
source install/setup.bash
# terminal 1
ros2 launch simple_diffbot_gazebo gazebo.launch.py
# terminal 2: EKF (publishes odom -> base_footprint)
ros2 launch simple_diffbot_localization ekf.launch.py
# terminal 3: slam_toolbox + RViz + PS4 teleop
ros2 launch simple_diffbot_slam slam.launch.py
```
Arguments: `use_sim_time:=true`, `slam_params_file:=...`, `rviz:=true`.

Drive around with the PS4 controller, then save the map:
```bash
ros2 run nav2_map_server map_saver_cli -f ~/work_ros2/simple_diffbot_ws/src/simple_diffbot_slam/maps/my_map
```
Rebuild afterwards so the map is installed.

## Topics and frames
| | |
|---|---|
| Subscribes | `/scan`, TF (`odom -> base_footprint`) |
| Publishes | `/map`, TF `map -> odom` |

## Config (`config/slam_toolbox_online_async.yaml`)
| Parameter | Value |
|---|---|
| `mode` | `mapping` |
| `odom_frame` / `map_frame` / `base_frame` | `odom` / `map` / `base_footprint` |
| `scan_topic` | `/scan` |
| `resolution` | 0.05 |
| `max_laser_range` | 8.0 (matches the simulated lidar) |
| `minimum_travel_distance` / `_heading` | 0.2 / 0.2 |
| `do_loop_closing` | true |

## Files
```
config/slam_toolbox_online_async.yaml
launch/slam.launch.py
maps/class_room.yaml, class_room.pgm, class_room_edit.pgm
rviz/slam.rviz
```

## Dependencies
`slam_toolbox`, `nav2_map_server`, `rviz2`, `simple_diffbot_teleop`
