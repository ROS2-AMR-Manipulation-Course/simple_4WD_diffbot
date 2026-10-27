#!/usr/bin/env python3
"""PS4 teleop: joystick -> trailobot/cmd_vel with deadzone, smoothing and safe stop."""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist


def clamp(value, low, high):
    return max(low, min(high, value))


def ramp(current, target, max_step):
    """Move current toward target by at most max_step."""
    if abs(target - current) <= max_step:
        return target
    return current + clamp(target - current, -max_step, max_step)


class PS4ControlNode(Node):
    def __init__(self):
        super().__init__('ps4_control_node')

        # Stick / button mapping (defaults match the previous behaviour)
        self.declare_parameter('axis_linear', 1)             # left stick vertical
        self.declare_parameter('axis_angular', 3)            # right stick horizontal
        self.declare_parameter('button_linear_up', 4)        # L1
        self.declare_parameter('button_linear_down', 7)      # L2
        self.declare_parameter('button_angular_up', 5)       # R1
        self.declare_parameter('button_angular_down', 6)     # R2
        self.declare_parameter('button_stop', -1)            # -1 = disabled
        self.declare_parameter('button_deadman', -1)         # -1 = not required
        self.declare_parameter('invert_angular', False)

        # Speed scaling: max speed at full stick, adjusted with the buttons
        self.declare_parameter('linear_speed', 0.5)
        self.declare_parameter('angular_speed', 0.5)
        self.declare_parameter('linear_speed_min', 0.1)
        self.declare_parameter('linear_speed_max', 1.0)
        self.declare_parameter('angular_speed_min', 0.1)
        self.declare_parameter('angular_speed_max', 0.8)
        self.declare_parameter('speed_step', 0.1)

        # Feel
        self.declare_parameter('deadzone', 0.1)
        self.declare_parameter('linear_accel', 1.0)          # m/s^2
        self.declare_parameter('angular_accel', 2.0)         # rad/s^2
        self.declare_parameter('joy_timeout', 0.5)           # s without joy -> stop
        self.declare_parameter('rate', 20.0)                 # Hz

        p = self.get_parameter
        self.axis_linear = p('axis_linear').value
        self.axis_angular = p('axis_angular').value
        self.btn_lin_up = p('button_linear_up').value
        self.btn_lin_down = p('button_linear_down').value
        self.btn_ang_up = p('button_angular_up').value
        self.btn_ang_down = p('button_angular_down').value
        self.btn_stop = p('button_stop').value
        self.btn_deadman = p('button_deadman').value
        self.angular_sign = -1.0 if p('invert_angular').value else 1.0

        self.lin_min = p('linear_speed_min').value
        self.lin_max = p('linear_speed_max').value
        self.ang_min = p('angular_speed_min').value
        self.ang_max = p('angular_speed_max').value
        self.speed_step = p('speed_step').value
        self.speed_linear = clamp(p('linear_speed').value, self.lin_min, self.lin_max)
        self.speed_angular = clamp(p('angular_speed').value, self.ang_min, self.ang_max)

        self.deadzone = p('deadzone').value
        self.lin_accel = p('linear_accel').value
        self.ang_accel = p('angular_accel').value
        self.joy_timeout = p('joy_timeout').value
        self.dt = 1.0 / p('rate').value

        # State
        self.stick_linear = 0.0
        self.stick_angular = 0.0
        self.deadman_ok = self.btn_deadman < 0
        self.cmd_linear = 0.0
        self.cmd_angular = 0.0
        self.prev_buttons = []
        self.last_joy = None
        self.was_stopped = True

        self.create_subscription(Joy, 'joy', self.joy_callback, 10)
        self.cmd_publisher = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_timer(self.dt, self.publish_cmd)
        self.log_speeds()

    def log_speeds(self):
        self.get_logger().info(
            f'Max speed: linear {self.speed_linear:.1f} m/s, angular {self.speed_angular:.1f} rad/s')

    def apply_deadzone(self, value):
        """Zero inside the deadzone, rescaled so the output still reaches +-1."""
        if abs(value) < self.deadzone:
            return 0.0
        sign = 1.0 if value > 0 else -1.0
        return sign * (abs(value) - self.deadzone) / (1.0 - self.deadzone)

    def pressed(self, buttons, index):
        """True only on the press edge, so holding a button changes speed once."""
        if index < 0 or index >= len(buttons):
            return False
        was = self.prev_buttons[index] if index < len(self.prev_buttons) else 0
        return bool(buttons[index]) and not was

    def joy_callback(self, msg):
        self.last_joy = self.get_clock().now()
        buttons = list(msg.buttons)

        changed = False
        if self.pressed(buttons, self.btn_lin_up):
            self.speed_linear = clamp(self.speed_linear + self.speed_step, self.lin_min, self.lin_max)
            changed = True
        if self.pressed(buttons, self.btn_lin_down):
            self.speed_linear = clamp(self.speed_linear - self.speed_step, self.lin_min, self.lin_max)
            changed = True
        if self.pressed(buttons, self.btn_ang_up):
            self.speed_angular = clamp(self.speed_angular + self.speed_step, self.ang_min, self.ang_max)
            changed = True
        if self.pressed(buttons, self.btn_ang_down):
            self.speed_angular = clamp(self.speed_angular - self.speed_step, self.ang_min, self.ang_max)
            changed = True
        if changed:
            self.log_speeds()

        if self.btn_deadman >= 0:
            self.deadman_ok = self.btn_deadman < len(buttons) and bool(buttons[self.btn_deadman])
        if self.btn_stop >= 0 and self.btn_stop < len(buttons) and buttons[self.btn_stop]:
            # Emergency stop: no ramp
            self.cmd_linear = 0.0
            self.cmd_angular = 0.0
            self.stick_linear = 0.0
            self.stick_angular = 0.0
        else:
            axes = msg.axes
            if self.axis_linear < len(axes):
                self.stick_linear = self.apply_deadzone(axes[self.axis_linear])
            if self.axis_angular < len(axes):
                self.stick_angular = self.apply_deadzone(axes[self.axis_angular])
        self.prev_buttons = buttons

    def publish_cmd(self):
        timed_out = (self.last_joy is None or
                     (self.get_clock().now() - self.last_joy).nanoseconds * 1e-9 > self.joy_timeout)

        if timed_out or not self.deadman_ok:
            target_linear = 0.0
            target_angular = 0.0
        else:
            target_linear = self.stick_linear * self.speed_linear
            target_angular = self.stick_angular * self.speed_angular * self.angular_sign

        # Smooth acceleration; stopping uses the same ramp unless e-stop zeroed the command
        self.cmd_linear = ramp(self.cmd_linear, target_linear, self.lin_accel * self.dt)
        self.cmd_angular = ramp(self.cmd_angular, target_angular, self.ang_accel * self.dt)

        stopped = self.cmd_linear == 0.0 and self.cmd_angular == 0.0
        if stopped and self.was_stopped:
            return                      # already sent a zero command; stay quiet
        self.was_stopped = stopped

        cmd = Twist()
        cmd.linear.x = self.cmd_linear
        cmd.angular.z = self.cmd_angular
        self.cmd_publisher.publish(cmd)

    def stop(self):
        self.cmd_publisher.publish(Twist())


def main(args=None):
    rclpy.init(args=args)
    node = PS4ControlNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.stop()
        except Exception:
            pass
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
