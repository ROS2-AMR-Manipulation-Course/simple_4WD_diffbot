# simple_diffbot_navigation

Nav2 bringup for simple_diffbot with a selectable local controller (MPPI, DWB or Regulated Pure Pursuit).

## Build and launch
```bash
cd ~/work_ros2/simple_diffbot_ws
colcon build --symlink-install --packages-select simple_diffbot_navigation
source install/setup.bash
# terminal 1
ros2 launch simple_diffbot_gazebo gazebo.launch.py
# terminal 2: localization (EKF + AMCL + map) + Nav2 + RViz
ros2 launch simple_diffbot_navigation bringup.launch.py controller_type:=mppi
```
Arguments:
| Argument | Default | |
|---|---|---|
| `controller_type` | `mppi` | `mppi`, `dwb` or `pure_pursuit` |
| `map` | `simple_diffbot_slam/maps/class_room.yaml` | map to navigate in |
| `localization` | `true` | set `false` if you launch localization yourself |
| `rviz` | `true` | open RViz with `rviz/nav2.rviz` |
| `params_file` | `config/nav2_params.yaml` | common Nav2 parameters |
| `use_sim_time`, `autostart`, `use_composition`, `use_respawn`, `log_level`, `namespace`, `use_namespace` | | standard Nav2 options |

In RViz, set the initial pose (2D Pose Estimate), then send a goal (Nav2 Goal).
`navigation.launch.py` starts only the Nav2 servers (no localization, no RViz).

## Data flow
```
controller_server -> cmd_vel_nav -> velocity_smoother -> cmd_vel_smoothed
                  -> collision_monitor -> /cmd_vel
```
| | |
|---|---|
| Subscribes | `/scan`, `/odometry/filtered`, `/map`, TF |
| Publishes | `/cmd_vel`, costmaps, plans |
| Frames | global `map`, local `odom`, base `base_footprint` |

## Config
- `config/nav2_params.yaml` – costmaps, planner (Smac 2D), smoother, behaviors, waypoint follower, velocity smoother, collision monitor.
  - Footprint 0.34 x 0.30 m, laser obstacle layer on `/scan`, depth-camera voxel layer on `/camera/points`.
  - Velocity limits: 0.4 m/s linear, 1.5 rad/s angular.
- `config/controller_mppi.yaml`, `controller_dwb.yaml`, `controller_pure_pursuit.yaml` – loaded after the common file, so they override `controller_server`.

The controller values are first-pass numbers adapted from a larger robot; tune them in simulation.

## Choosing a controller
Select with `controller_type:=mppi|dwb|pure_pursuit`. All three follow the global plan; they differ in how they avoid obstacles.

| Controller | Use when | Avoids obstacles by | Weak point |
|---|---|---|---|
| **MPPI** (default) | Dynamic obstacles, cluttered rooms, smooth motion wanted | Sampling 2000 noisy trajectories each cycle and scoring them against the costmap | Highest CPU. Output is random, so slightly jittery. |
| **DWB** | Simple, predictable behaviour; easy to debug (critic scores are logged) | Scoring a fixed grid of velocity arcs | Fails with "No valid trajectories" when every arc hits something. Many critic weights to balance. |
| **Regulated Pure Pursuit** | Open spaces, following a clean path, lowest CPU | Slowing near obstacles and stopping on predicted collision. It does **not** steer around them | Cannot dodge. Relies on the planner to replan. |

Rule of thumb: start with Pure Pursuit to check that the plan, TF and localization are good; use MPPI or DWB once moving obstacles are in the scene.

## Planner server
`planner_server` computes the global path on the global costmap. It is configured as `SmacPlanner2D` (`GridBased` in `nav2_params.yaml`). The plan is only recomputed when the behavior tree asks for it, not continuously.

Why Smac 2D rather than NavFn: it is A*-based, uses the costmap gradient to stay away from walls, and has a built-in smoother. NavFn (Dijkstra) picks between equal-cost routes arbitrarily, so the plan can jump between replans.

| Parameter | Value | Effect and how to tune |
|---|---|---|
| `tolerance` | 0.125 | How far from an unreachable goal the planner accepts. Raise it if goals near walls fail; keep it small so the robot does not stop short. |
| `allow_unknown` | true | Lets plans cross unknown cells. Set `false` once the map is complete so plans never cut through unexplored space. |
| `cost_travel_multiplier` | 2.0 | Pushes the path away from high-cost cells. Higher gives a centred path in corridors but is slower to compute. 1.0 is faster; 0.0 ignores costs. |
| `max_planning_time` | 2.0 | Budget in seconds. Raise it for large maps; lower it if replanning stalls the robot. |
| `use_final_approach_orientation` | false | `true` ends the path along the approach direction, so the robot does not spin at the goal. |
| `smoother.w_smooth` / `w_data` | 0.3 / 0.2 | Higher `w_smooth` gives rounder paths but cuts corners; higher `w_data` stays closer to the raw path. |

Costmap settings that shape the plan (global costmap):
- `inflation_radius` 0.4 and `cost_scaling_factor` 3.2. The robot's circumscribed radius is about 0.23 m. A larger radius or a smaller scaling factor gives a wider, gentler gradient, so paths stay further from walls but narrow doorways may become impassable.
- `update_frequency` 5 Hz. Moving obstacles only appear in the plan if they are in the global costmap.
- If the plan changes every replan with no obstacles in the scene, the usual causes are sensor noise marking cells in the voxel layer (raise `mark_threshold`) or localization jitter in `map -> odom`. Replanning more slowly in the behavior tree also steadies the line.

## Tuning for dynamic obstacles
None of the controllers predict where an obstacle will be; they treat the current costmap as frozen over their horizon. So tuning is about seeing obstacles quickly and having room to react.

Costmaps (`nav2_params.yaml`):
| Parameter | Effect and why |
|---|---|
| local costmap `update_frequency` (5 Hz now) | Raise to 10 Hz or more. At 0.5 m/s an obstacle moves 10 cm between updates at 5 Hz. |
| `voxel_layer.mark_threshold` | Lower marks faster; higher rejects noise. 1 to 2 is a good range. |
| `inflation_radius`, `cost_scaling_factor` | Controllers (especially MPPI `CostCritic`) need a smooth gradient. A very steep scaling factor (above about 5) gives them no warning. |
| `raytrace_max_range` | Clears the trail an obstacle leaves behind. Keep it at or above the marking range. |

MPPI (`controller_mppi.yaml`):
| Parameter | Effect and why |
|---|---|
| `CostCritic.cost_weight` (3.81) | The main obstacle-avoidance weight. Raise to 5 to 8 to swerve earlier. |
| `PathAlignCritic.cost_weight` (14), `PathFollowCritic.cost_weight` (5) | Pull back to the path. Lower them if the robot refuses to leave the path to dodge. |
| `CostCritic.near_goal_distance` (1.0) | The cost critic is ignored this close to the goal. Lower it to about 0.5 if obstacles near the goal are a problem. |
| `vx_min` | Negative lets the robot back away from an approaching obstacle. |
| `ax_max`, `ax_min` | Keep them within what the motors can do; otherwise MPPI plans stops it cannot execute. |
| `temperature`, `vx_std`, `wz_std` | Lower is more decisive and less random; higher gives smoother but less reactive motion. |
| `batch_size`, `controller_frequency` | Raise for better coverage; lower them if the controller cannot hold its rate. |

DWB (`controller_dwb.yaml`):
| Parameter | Effect and why |
|---|---|
| `BaseObstacle.scale` (0.2) | Weight of obstacle cost when ranking arcs. Very low and the robot ignores obstacles until it is about to hit them. Consider `ObstacleFootprint`, which checks the whole body. |
| `PathAlign.scale`, `PathDist.scale` (16) | Weight of staying on the path. Lower than the obstacle weight lets the robot leave it to dodge. |
| `sim_time` (2.5 s) | Prediction horizon. Too long and a walking obstacle's current position blocks every arc; too short and it reacts late. 1.5 to 2.5 s works. |
| `min_vel_x` | Must be negative to allow reversing. With 0.0 the robot can only rotate when blocked. |
| `max_vel_x`, `acc_lim_x`, `decel_lim_x` | Lower speed and stronger braking give more stopping margin. |

Regulated Pure Pursuit (`controller_pure_pursuit.yaml`):
| Parameter | Effect and why |
|---|---|
| `desired_linear_vel` (0.3) | Cruise speed. |
| `lookahead_dist` (0.45) | Short is accurate but wobbly; long is smooth but cuts corners. |
| `max_allowed_time_to_collision_up_to_carrot` (1.0) | How far ahead the collision check looks. Raise it to stop earlier. |
| `use_cost_regulated_linear_velocity_scaling` (false) | Set `true` to slow down near obstacles and walls. |

Safety net: `collision_monitor` stops or slows the robot independently of the controller (`FootprintApproach` with `time_before_collision` 1.5 s, and `SlowdownZone`). Tune the controller first; use the monitor only as a backstop.

## Files
```
config/nav2_params.yaml, controller_{mppi,dwb,pure_pursuit}.yaml
launch/bringup.launch.py, navigation.launch.py
rviz/nav2.rviz
```

## Dependencies
`nav2_bringup`, `nav2_smoother`, `nav2_velocity_smoother`, `nav2_collision_monitor`, `nav2_mppi_controller`,
`nav2_dwb_controller`, `nav2_regulated_pure_pursuit_controller`, `nav2_smac_planner`,
`simple_diffbot_localization`, `simple_diffbot_slam`

## References
Official Nav2 documentation (Jazzy):

| Topic | Link |
|---|---|
| Tuning Guide (general advice on inflation, controllers, costmaps) | https://docs.nav2.org/jazzy/configuration_and_development/tuning_guide/ |
| Configuration Guide index | https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/ |
| Navigation Plugins (which planner, controller and smoother to choose) | https://docs.nav2.org/jazzy/configuration_and_development/navigation_plugins/ |
| Controller Server | https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/controller_server/ |
| Planner Server | https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/configuring_planner_server/ |
| Smac Planner (2D, Hybrid, Lattice) | https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/planners_plugins/smac/ |
| NavFn Planner | https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/planners_plugins/configuring_navfn/ |
| MPPI Controller | https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/controller_plugins/mppi_controller/configuring_mppic/ |
| DWB Controller | https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/controller_plugins/dwb_controller/ |
| Regulated Pure Pursuit | https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/controller_plugins/configuring_regulated_pp/ |
| Costmap 2D (static, obstacle, voxel and inflation layers) | https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/costmap_2d/ |
| Collision Monitor | https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/collision_monitor/ |
| Smoother Server | https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/configuring_smoother_server/ |
| Velocity Smoother | https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/configuring_velocity_smoother/ |
| Behavior Server | https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/configuring_behavior_server/ |
| Behavior-Tree Navigator | https://docs.nav2.org/jazzy/configuration_and_development/configuration_guide/core_servers/configuring_bt_navigator/ |
| Navigation Concepts | https://docs.nav2.org/jazzy/getting_started/navigation_concepts/ |
