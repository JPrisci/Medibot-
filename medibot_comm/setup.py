from glob import glob

from setuptools import find_packages, setup


package_name = 'medibot_comm'


setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        (
            'share/ament_index/resource_index/packages',
            ['resource/' + package_name],
        ),
        (
            'share/' + package_name,
            ['package.xml'],
        ),
        (
            'share/' + package_name + '/launch',
            glob('launch/*.launch.py'),
        ),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='jarvis',
    maintainer_email='jarvis@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'status_monitor = medibot_comm.status_monitor:main',
            'handover_decision_subscriber = medibot_comm.handover_decision_subscriber:main',
            'navigation_status_adapter = medibot_comm.navigation_status_adapter:main',
            'local_action_subscriber = medibot_comm.local_action_subscriber:main',
            'task_coordinator = medibot_comm.task_coordinator:main',
            'ux_api_adapter = medibot_comm.ux_api_adapter:main',
        ],
    },
)