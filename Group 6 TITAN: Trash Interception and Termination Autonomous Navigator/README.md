# Project-TITAN: Trash Interception and Termination Autonomous Navigator

Project-TITAN is a comprehensive robotics platform that integrates a high-performance ROS2 workspace with custom web and terminal interfaces for seamless mission control.

## System Architecture

The project is organized as a **Monorepo** to ensure synchronized development between hardware logic and user interfaces:

```text
Project_TITAN/
├── titan_ws/           # ROS2 Workspace (C++/Python)
│   └── Core hardware drivers, odometry, and motor bridges.
├── titan_gui/          # TRIDENT Web Interface (HTML/JS)
│   └── High-precision Pilot controller (Landscape-optimized).
└── titan_tui/          # TRIDENT Terminal Interface (Python/TUI)
    └── Low-latency system monitoring and WiFi configuration.
```

## Quick Start

### 1. Hardware Initialization (Workspace)
Ensure your ROS2 environment is sourced and build the workspace:
```bash
cd titan_ws
colcon build
source install/setup.bash
ros2 launch titan_bringup robot.launch.py
```

### 2. Pilot Interface (GUI)
Start the web controller:
```bash
cd titan_gui
npm run dev -- --host
```
Open the provided URL in your browser and rotate your device to **Landscape**.

### 3. System Monitor (TUI)
Launch the terminal interface for real-time telemetry:
```bash
cd titan_tui
python3 main.py
```

## Features

- **TRIDENT PRO Console**: Robust button-based DPAD for piloting and lifting mechanism control.
- **Safety Lock**: Integrated landscape orientation requirement and high-precision speed scaling.
- **Unified Versioning**: Single repository management for all TITAN sub-systems.

---
*Developed for the TITAN Robot Platform.*
