# TRIDENT PRO - Robot Mission Control

TRIDENT PRO is a high-performance, single-file web interface designed for the TITAN robot. It provides a minimalist, safety-first mission control experience with high-precision directional and lifting mechanism controls.

## 🚀 Key Features

- **Dedicated DPAD Control**: A high-reliability 4-way DPAD for precise robot maneuvering.
- **Lifting Mechanism Controls**: Dedicated **UP**, **DOWN**, and **EMERGENCY STOP** buttons for auxiliary motor systems.
- **Safety Orientation Lock**: Optimized exclusively for **Landscape Mode** to ensure ergonomic operation.
- **Dynamic Speed Tuning**: Real-time linear velocity scaling (0.1m/s - 0.5m/s) with optimized angular defaults (0.50).
- **Glassmorphism UI**: A premium, dark-mode "cockpit" aesthetic with real-time connection status monitoring.

## 🛠 Tech Stack

- **Frontend**: Vanilla HTML5, CSS3 (Glassmorphism), and JavaScript.
- **Communication**: [roslib.js](https://github.com/RobotWebTools/roslibjs) for WebSocket communication with ROS2.
- **Fonts**: Google Fonts (`Inter`, `JetBrains Mono`).

## 🤖 ROS2 Integration

The TRIDENT PRO GUI communicates with the robot via the `rosbridge_suite` on port `9090`.

### Published Topics

| Topic | Type | Description |
| :--- | :--- | :--- |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | Differential drive commands (Linear X, Angular Z). |
| `/aux_motor/cmd` | `std_msgs/msg/Int16` | Lifting mechanism control signals (255=Up, -255=Down, 0=Stop). |

## 📦 Getting Started

1. Ensure `rosbridge_server` is running on your robot:
   ```bash
   ros2 launch rosbridge_server rosbridge_websocket_launch.xml
   ```
2. Open `index.html` in any modern mobile or desktop browser.
3. Rotate your device to **Landscape** to activate the control panel.
4. Use the **Retry (↻)** button if the connection is not established automatically.

---
*Developed for the TITAN Robot Platform.*
