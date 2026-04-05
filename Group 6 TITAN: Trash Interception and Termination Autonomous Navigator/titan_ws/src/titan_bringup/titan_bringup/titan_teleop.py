#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from std_msgs.msg import Int16
import sys
import select
import time
import termios
import tty

settings = termios.tcgetattr(sys.stdin)

msg = """
TRIDENT PRO Custom Teleop
---------------------------
Drive Control (Press & Hold):
        W
   A    S    D

Lifting Motor (Aux):
   E : Lift UP (+255)
   C : Lift DOWN (-255)

Space: Force Stop

CTRL-C to quit
"""

moveBindings = {
    'w': (1, 0),
    's': (-1, 0),
    'a': (0, 1),
    'd': (0, -1),
}

def getKey(settings):
    tty.setraw(sys.stdin.fileno())
    # Timeout 0.1s ensures we detect when keys are released
    rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
    if rlist:
        key = sys.stdin.read(1)
    else:
        key = ''
    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
    return key

def main(args=None):
    rclpy.init(args=args)
    node = rclpy.create_node('titan_teleop')
    
    # Declare dynamic speed parameters
    node.declare_parameter('speed', 0.15)
    node.declare_parameter('turn', 0.5)
    speed_param = node.get_parameter('speed').value
    turn_param = node.get_parameter('turn').value

    pub_cmd = node.create_publisher(Twist, '/cmd_vel', 10)
    pub_aux = node.create_publisher(Int16, '/aux_motor/cmd', 10)

    target_x = 0.0
    target_th = 0.0
    current_x = 0.0
    current_th = 0.0
    target_aux = 0

    # Deceleration limits (time in seconds to stop)
    ramp_time = 0.2
    decel_linear = speed_param / ramp_time
    decel_angular = turn_param / ramp_time

    last_time = time.time()
    
    # State tracking for OS keyboard repeat delay
    last_key_time = time.time()
    auto_repeat_active = False

    try:
        print(msg)
        while rclpy.ok():
            key = getKey(settings)
            now = time.time()
            dt = now - last_time
            last_time = now
            
            if key in moveBindings.keys():
                target_x = float(moveBindings[key][0]) * speed_param
                target_th = float(moveBindings[key][1]) * turn_param
                target_aux = 0
                
                if now - last_key_time < 0.15:
                    auto_repeat_active = True
                last_key_time = now
                
            elif key == 'e' or key == 'E':
                target_x = 0.0
                target_th = 0.0
                target_aux = 255
                
                if now - last_key_time < 0.15: auto_repeat_active = True
                last_key_time = now
                
            elif key == 'c' or key == 'C':
                target_x = 0.0
                target_th = 0.0
                target_aux = -255
                
                if now - last_key_time < 0.15: auto_repeat_active = True
                last_key_time = now
                
            elif key == ' ' or key == 'k':
                target_x = 0.0
                target_th = 0.0
                target_aux = 0
                auto_repeat_active = False
            elif key == '\x03': # CTRL-C
                break
            elif key == '':
                time_since_last = now - last_key_time
                if auto_repeat_active:
                    # Key was repeating, but we missed a beat -> released
                    if time_since_last > 0.15:
                        target_x = 0.0
                        target_th = 0.0
                        target_aux = 0
                        auto_repeat_active = False
                else:
                    # Waiting for first repeat, give it 0.6s max
                    if time_since_last > 0.6:
                        target_x = 0.0
                        target_th = 0.0
                        target_aux = 0
            
            # Apply Smoothing: Instant start, smooth stop
            if target_x != 0.0:
                current_x = target_x
            else:
                if current_x < 0.0:
                    current_x = min(0.0, current_x + decel_linear * dt)
                elif current_x > 0.0:
                    current_x = max(0.0, current_x - decel_linear * dt)
                    
            if target_th != 0.0:
                current_th = target_th
            else:
                if current_th < 0.0:
                    current_th = min(0.0, current_th + decel_angular * dt)
                elif current_th > 0.0:
                    current_th = max(0.0, current_th - decel_angular * dt)

            if abs(current_x) < 0.001: current_x = 0.0
            if abs(current_th) < 0.001: current_th = 0.0
            
            twist = Twist()
            twist.linear.x = current_x
            twist.angular.z = current_th
            pub_cmd.publish(twist)
            
            aux_msg = Int16()
            aux_msg.data = target_aux
            pub_aux.publish(aux_msg)

    except Exception as e:
        print(f"Teleop Error: {e}")
    finally:
        twist = Twist()
        pub_cmd.publish(twist)
        aux_msg = Int16()
        aux_msg.data = 0
        pub_aux.publish(aux_msg)

        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, settings)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
