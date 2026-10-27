# simple_diffbot_teleop

PS4 controller teleoperation. `ps4_node` turns `/joy` into `/cmd_vel` with acceleration
limiting, a deadzone and a joy timeout (stops if no joy message for 0.5 s).

## Build and launch
```bash
cd ~/work_ros2/simple_diffbot_ws
colcon build --symlink-install --packages-select simple_diffbot_teleop
source install/setup.bash
ros2 launch simple_diffbot_teleop ps4.launch.py
```
Starts `joy_node` and `ps4_node`.

## Topics
| Topic | Type | Direction |
|---|---|---|
| `/joy` | `sensor_msgs/Joy` | subscribed |
| `/cmd_vel` | `geometry_msgs/Twist` | published |

## Default controls
| Input | Action |
|---|---|
| Left stick vertical (axis 1) | forward / backward |
| Right stick horizontal (axis 3) | turn |
| L1 / L2 (buttons 4 / 7) | max linear speed + / - |
| R1 / R2 (buttons 5 / 6) | max angular speed + / - |

## Parameters (`ps4_node`)
| Parameter | Default | Meaning |
|---|---|---|
| `linear_speed`, `angular_speed` | 0.5, 0.5 | starting max speeds |
| `linear_speed_min` / `_max` | 0.1 / 1.0 | linear speed limits (m/s) |
| `angular_speed_min` / `_max` | 0.1 / 0.8 | angular speed limits (rad/s) |
| `speed_step` | 0.1 | change per button press |
| `deadzone` | 0.1 | stick deadzone |
| `linear_accel`, `angular_accel` | 1.0, 2.0 | acceleration limits |
| `joy_timeout` | 0.5 | seconds without joy before stopping |
| `rate` | 20.0 | publish rate (Hz) |
| `axis_*`, `button_*` | see above | mapping; `button_stop` / `button_deadman` = -1 disables them |
| `invert_angular` | false | flip turn direction |

Override with e.g. `ros2 run simple_diffbot_teleop ps4_node --ros-args -p linear_speed:=0.3`.

## Files
```
launch/ps4.launch.py
simple_diffbot_teleop/ps4_node.py
```

## Dependencies
`rclpy`, `geometry_msgs`, `sensor_msgs`, and the `joy` package at runtime.
