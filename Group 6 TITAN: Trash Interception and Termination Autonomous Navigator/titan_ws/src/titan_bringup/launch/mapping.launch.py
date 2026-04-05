import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource

def generate_launch_description():
   
    bringup_pkg = get_package_share_directory('titan_bringup')
    slam_toolbox_pkg = get_package_share_directory('slam_toolbox')
    

    slam_params = os.path.join(bringup_pkg, 'config', 'mapper_params_online_async.yaml')

 
    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(slam_toolbox_pkg, 'launch', 'online_async_launch.py')
        ),
        launch_arguments={
            'use_sim_time': 'false',
            'slam_params_file': slam_params
        }.items()
    )

    return LaunchDescription([
        slam_launch
    ])