from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os
import xacro

def generate_launch_description():

    # 1. Setup Paths
    desc_pkg = get_package_share_directory('titan_description')
    xacro_file = os.path.join(desc_pkg, 'urdf', 'robot.urdf.xacro')

    lidar_pkg = get_package_share_directory('ydlidar_ros2_driver')
    x2_params = os.path.join(lidar_pkg, 'params', 'X2.yaml')

    # 2. Process Xacro
    robot_description_config = xacro.process_file(xacro_file)
    robot_desc = robot_description_config.toxml()

    return LaunchDescription([

        # 3. Robot State Publisher
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'robot_description': robot_desc}]
        ),

        # 4. Joint State Publisher
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            parameters=[{'use_sim_time': False}]
        ),

        # 5. YDLidar Driver
        Node(
            package='ydlidar_ros2_driver',
            executable='ydlidar_ros2_driver_node',
            name='ydlidar_ros2_driver_node',
            output='screen',
            parameters=[x2_params, {
                'port': '/dev/lidar',
                'ignore_array': '150, 210' # Ignore -150 to -210 (rear sector)
            }]
        ),

        # 6. Arduino Bridge
        Node(
            package='titan_bringup',
            executable='arduino_bridge',
            name='arduino_bridge',
            output='screen',
            parameters=[{
                'port': '/dev/arduino',
                'baudrate': 115200,
                'ticks_per_meter': 3186.0,
                'wheel_base': 0.45,
                'publish_tf': True
            }]
        ),

        # 7. ROS Web Bridge (For Consumer GUI)
        Node(
            package='rosbridge_server',
            executable='rosbridge_websocket',
            name='rosbridge_websocket',
            output='screen'
        ),

        # 8. System Manager (For GUI Control)
        Node(
            package='titan_bringup',
            executable='system_manager',
            name='system_manager',
            output='screen'
        )
    ])