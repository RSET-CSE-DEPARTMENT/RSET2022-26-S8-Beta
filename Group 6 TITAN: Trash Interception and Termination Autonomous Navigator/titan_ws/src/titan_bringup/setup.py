from setuptools import find_packages, setup
import os               
from glob import glob   

package_name = 'titan_bringup'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'maps'), [f for f in glob('maps/*', recursive=True) if os.path.isfile(f)]),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'rviz'), glob('rviz/*.rviz')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='pidev',
    maintainer_email='pidev@todo.todo',
    description='Bringup package for the IEEE MAGIC garbage bot',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'arduino_bridge = titan_bringup.arduino_bridge_node:main',
            'system_manager = titan_bringup.system_manager:main',
            'titan_teleop = titan_bringup.titan_teleop:main',
        ],
    },
)