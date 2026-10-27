#!/usr/bin/env bash
# Patrol both dynamic obstacles: dynamic_obstacle along x, dynamic_obstacle_2 along y.
# Usage: patrol_obstacle.sh [speed m/s] [seconds per leg]
SPEED=${1:-0.5}
LEG=${2:-8}
send() { gz topic -t "/model/$1/cmd_vel" -m gz.msgs.Twist -p "linear: {$2: $3}"; }
trap 'send dynamic_obstacle x 0; send dynamic_obstacle_2 y 0; exit' INT TERM
while true; do
  send dynamic_obstacle   x  "$SPEED"; send dynamic_obstacle_2 y  "$SPEED"; sleep "$LEG"
  send dynamic_obstacle   x "-$SPEED"; send dynamic_obstacle_2 y "-$SPEED"; sleep "$LEG"
done
