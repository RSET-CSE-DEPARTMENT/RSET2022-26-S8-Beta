import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import subprocess
import os
import signal

class SystemManager(Node):
    def __init__(self):
        super().__init__('system_manager')
        self.subscription = self.create_subscription(
            String,
            '/titan/system_command',
            self.listener_callback,
            10)
        self.get_logger().info('System Manager Node started. Ready for commands.')
        self.processes = {}

    def listener_callback(self, msg):
        command = msg.data
        self.get_logger().info(f'Received command: {command}')

        if command == 'start_mapping':
            self.start_process('mapping', 'ros2 launch titan_bringup mapping.launch.py')
        elif command.startswith('save_map:'):
            map_name = command.split(':')[1]
            self.run_oneshot(f'ros2 run nav2_map_server map_saver_cli -f ~/titan_ws/src/titan_bringup/maps/{map_name}')
        elif command == 'kill_all':
            self.kill_all()
        elif command.startswith('start_navigation:'):
            map_name = command.split(':')[1]
            map_path = f'~/titan_ws/src/titan_bringup/maps/{map_name}.yaml'
            self.start_process('navigation', f'ros2 launch titan_bringup navigation.launch.py map:={map_path}')

    def start_process(self, name, cmd):
        if name in self.processes and self.processes[name].poll() is None:
            self.get_logger().warn(f'Process {name} is already running. Killing old one first.')
            self.stop_process(name)
        
        self.get_logger().info(f'Starting {name}: {cmd}')
        # Use shell=True for convenience with ROS2 launch strings
        self.processes[name] = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)

    def stop_process(self, name):
        if name in self.processes:
            p = self.processes[name]
            if p.poll() is None:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            del self.processes[name]

    def run_oneshot(self, cmd):
        self.get_logger().info(f'Running one-shot: {cmd}')
        subprocess.Popen(cmd, shell=True)

    def kill_all(self):
        self.get_logger().info('Killing all managed processes and global ROS nodes...')
        for name in list(self.processes.keys()):
            self.stop_process(name)
        # Global pkill for safety as per TUI logic
        subprocess.run('pkill -9 -f slam_toolbox; pkill -9 -f nav2; pkill -9 -f map_server', shell=True)

def main(args=None):
    rclpy.init(args=args)
    node = SystemManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.kill_all()
        node.destroy_node()
        rclpy.shutdown()
