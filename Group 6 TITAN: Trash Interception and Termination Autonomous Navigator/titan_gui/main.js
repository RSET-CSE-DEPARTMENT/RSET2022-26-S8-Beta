import ROSLIB from 'roslib';

// --- ROS2 CONFIGURATION ---
const ros = new ROSLIB.Ros({
    url: 'ws://' + window.location.hostname + ':9090'
});

const statusIndicator = document.getElementById('ros-status');
const logContainer = document.getElementById('system-logs');

ros.on('connection', () => {
    addLog('System online. ROS Bridge connected.', 'system');
    statusIndicator.className = 'indicator connected';
    document.getElementById('mobile-ros-status').className = 'indicator connected';
});

ros.on('error', (error) => {
    addLog(`Connection error: ${error}`, 'error');
    statusIndicator.className = 'indicator disconnected';
    document.getElementById('mobile-ros-status').className = 'indicator disconnected';
});

ros.on('close', () => {
    addLog('Connection closed.', 'warn');
    statusIndicator.className = 'indicator disconnected';
    document.getElementById('mobile-ros-status').className = 'indicator disconnected';
});

// Mobile Sidebar Toggle
const menuToggle = document.getElementById('menu-toggle');
const sidebar = document.getElementById('sidebar');

menuToggle.addEventListener('click', () => {
    sidebar.classList.toggle('open');
});

function addLog(msg, type = '') {
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const now = new Date();
    const timeStr = `[${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}] `;
    entry.innerText = timeStr + msg;
    logContainer.prepend(entry);
}

// --- SYSTEM COMMANDS ---
const systemCmdPub = new ROSLIB.Topic({
    ros: ros,
    name: '/titan/system_command',
    messageType: 'std_msgs/msg/String'
});

function sendSystemCmd(cmd) {
    const msg = new ROSLIB.Message({ data: cmd });
    systemCmdPub.publish(msg);
    addLog(`Sent System Command: ${cmd}`, 'system');
}

document.getElementById('start-slam-btn')?.addEventListener('click', () => sendSystemCmd('start_mapping'));
document.getElementById('kill-slam-btn')?.addEventListener('click', () => sendSystemCmd('kill_all'));
document.getElementById('save-map-btn')?.addEventListener('click', () => {
    const name = document.getElementById('map-name-input').value || 'new_map';
    sendSystemCmd(`save_map:${name}`);
});

// --- WAYPOINTS ---
let waypoints = [];
const goalPub = new ROSLIB.Topic({
    ros: ros,
    name: '/goal_pose',
    messageType: 'geometry_msgs/msg/PoseStamped'
});

let currentPos = { x: 0, y: 0, yaw: 0 };

document.getElementById('add-waypoint-btn')?.addEventListener('click', () => {
    const name = prompt("Enter checkpoint name:") || `WP_${waypoints.length + 1}`;
    const wp = { name, ...currentPos };
    waypoints.push(wp);
    renderWaypoints();
    addLog(`Checkpoint saved: ${name}`, 'system');
});

function renderWaypoints() {
    const list = document.getElementById('waypoint-list');
    list.innerHTML = '';
    waypoints.forEach((wp, index) => {
        const div = document.createElement('div');
        div.className = 'wp-item';
        div.innerHTML = `
            <span>${wp.name}</span>
            <button onclick="window.navToWaypoint(${index})">Navigate</button>
        `;
        list.appendChild(div);
    });
}

window.navToWaypoint = (index) => {
    const wp = waypoints[index];
    const goal = new ROSLIB.Message({
        header: { frame_id: 'map', stamp: { secs: 0, nsecs: 0 } },
        pose: {
            position: { x: wp.x, y: wp.y, z: 0 },
            orientation: eulerToQuaternion(wp.yaw)
        }
    });
    goalPub.publish(goal);
    addLog(`Navigating to ${wp.name}...`, 'system');
};

function eulerToQuaternion(yaw) {
    const qz = Math.sin(yaw / 2);
    const qw = Math.cos(yaw / 2);
    return { x: 0, y: 0, z: qz, w: qw };
}

const odomSub = new ROSLIB.Topic({
    ros: ros,
    name: '/odom',
    messageType: 'nav_msgs/msg/Odometry'
});

// Update local currentPos from Odom
odomSub.subscribe((message) => {
    const pos = message.pose.pose.position;
    const q = message.pose.pose.orientation;
    const yaw = Math.atan2(2.0 * (q.w * q.z + q.x * q.y), 1.0 - 2.0 * (q.y * q.y + q.z * q.z));
    
    currentPos = { x: pos.x, y: pos.y, yaw: yaw };
    
    document.getElementById('tel-x').innerText = pos.x.toFixed(2);
    document.getElementById('tel-y').innerText = pos.y.toFixed(2);
    document.getElementById('tel-yaw').innerText = (yaw * 180 / Math.PI).toFixed(1) + '°';
    
    updateRobotMarker(pos.x, pos.y, yaw);
});

// --- TELEOP / JOYSTICK ---
const cmdVelPub = new ROSLIB.Topic({
    ros: ros,
    name: '/cmd_vel',
    messageType: 'geometry_msgs/msg/Twist'
});

const auxMotorPub = new ROSLIB.Topic({
    ros: ros,
    name: '/aux_motor/cmd',
    messageType: 'std_msgs/msg/Int16'
});

const joystickBase = document.getElementById('joystick-base');
const joystickHandle = document.getElementById('joystick-handle');
const driveSpeedSlider = document.getElementById('drive-speed-slider');
const speedDisplayVal = document.getElementById('speed-display-val');

let isDragging = false;
let maxLin = 0.2;
let maxAng = 0.8;

driveSpeedSlider?.addEventListener('input', (e) => {
    maxLin = parseFloat(e.target.value);
    maxAng = maxLin * 4; // Scale angular with linear
    speedDisplayVal.innerText = maxLin.toFixed(2) + 'm/s';
});

function handleMove(e) {
    if (!isDragging) return;
    
    const rect = joystickBase.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    
    let x, y;
    if (e.type === 'touchmove') {
        x = e.touches[0].clientX - centerX;
        y = e.touches[0].clientY - centerY;
    } else {
        x = e.clientX - centerX;
        y = e.clientY - centerY;
    }
    
    const dist = Math.sqrt(x*x + y*y);
    const maxDist = rect.width / 2;
    
    if (dist > maxDist) {
        x = x * maxDist / dist;
        y = y * maxDist / dist;
    }
    
    joystickHandle.style.transform = `translate(calc(-50% + ${x}px), calc(-50% + ${y}px))`;
    
    // Map to Twist
    // Y is forward (negative in screen coords), X is turn
    const lin = (-y / maxDist) * maxLin;
    const ang = (-x / maxDist) * maxAng;
    
    sendTwist(lin, ang);
}

function sendTwist(lin, ang) {
    const twist = new ROSLIB.Message({
        linear: { x: lin, y: 0, z: 0 },
        angular: { x: 0, y: 0, z: ang }
    });
    cmdVelPub.publish(twist);
}

function resetJoystick() {
    if (!isDragging) return;
    isDragging = false;
    joystickHandle.style.transition = 'all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
    joystickHandle.style.transform = 'translate(-50%, -50%)';
    setTimeout(() => joystickHandle.style.transition = '', 200);
    sendTwist(0, 0);
}

joystickHandle?.addEventListener('mousedown', () => isDragging = true);
window.addEventListener('mousemove', handleMove);
window.addEventListener('mouseup', resetJoystick);

joystickHandle?.addEventListener('touchstart', (e) => {
    e.preventDefault();
    isDragging = true;
}, { passive: false });
window.addEventListener('touchmove', handleMove, { passive: false });
window.addEventListener('touchend', resetJoystick);

// --- LIFTING MECHANISM CONTROL ---
const liftUpBtn = document.getElementById('lift-up-btn');
const liftDownBtn = document.getElementById('lift-down-btn');
const liftStatusText = document.getElementById('lift-status-text');
const liftStopBtn = document.getElementById('lift-stop-btn');

let liftInterval = null;

function sendLiftCmd(val) {
    const msg = new ROSLIB.Message({ data: parseInt(val) });
    auxMotorPub.publish(msg);
    if (liftStatusText) {
        if (val > 0) liftStatusText.innerText = 'LIFTING ↑';
        else if (val < 0) liftStatusText.innerText = 'LOWERING ↓';
        else liftStatusText.innerText = 'STATIONARY';
    }
}

const startLift = (dir) => {
    if (liftInterval) clearInterval(liftInterval);
    const speed = dir === 'up' ? 255 : -255;
    sendLiftCmd(speed);
    
    if (window.navigator.vibrate) window.navigator.vibrate(30);

    liftInterval = setInterval(() => {
        sendLiftCmd(speed);
    }, 100);
};

const stopLift = () => {
    if (liftInterval) {
        clearInterval(liftInterval);
        liftInterval = null;
    }
    sendLiftCmd(0);
};

liftUpBtn?.addEventListener('mousedown', () => startLift('up'));
liftDownBtn?.addEventListener('mousedown', () => startLift('down'));
window.addEventListener('mouseup', stopLift);
liftStopBtn?.addEventListener('click', stopLift);

liftUpBtn?.addEventListener('touchstart', (e) => { e.preventDefault(); startLift('up'); }, { passive: false });
liftDownBtn?.addEventListener('touchstart', (e) => { e.preventDefault(); startLift('down'); }, { passive: false });
window.addEventListener('touchend', stopLift);

// --- MAP VISUALIZATION ---
const canvas = document.getElementById('map-canvas');
const ctx = canvas?.getContext('2d');
const marker = document.getElementById('robot-marker');

const mapSub = new ROSLIB.Topic({
    ros: ros,
    name: '/map',
    messageType: 'nav_msgs/msg/OccupancyGrid'
});

let mapMetadata = null;

mapSub.subscribe((message) => {
    if (!ctx) return;
    mapMetadata = message.info;
    const { width, height, resolution } = mapMetadata;
    
    if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
    }
    
    const imageData = ctx.createImageData(width, height);
    for (let i = 0; i < message.data.length; i++) {
        const val = message.data[i];
        let r, g, b, a;
        
        if (val === -1) { // Unknown
            r = 30; g = 32; b = 40; a = 180;
        } else if (val === 100) { // Occupied
            r = 59; g = 130; b = 246; a = 255;
        } else { // Free
            r = 10; g = 11; b = 15; a = 255;
        }
        
        const idx = (height - 1 - Math.floor(i / width)) * width + (i % width);
        imageData.data[idx * 4] = r;
        imageData.data[idx * 4 + 1] = g;
        imageData.data[idx * 4 + 2] = b;
        imageData.data[idx * 4 + 3] = a;
    }
    ctx.putImageData(imageData, 0, 0);
});

function updateRobotMarker(x, y, yaw) {
    if (!mapMetadata || !marker) return;
    
    const { origin, resolution, height, width } = mapMetadata;
    const px = (x - origin.position.x) / resolution;
    const py = height - (y - origin.position.y) / resolution;
    
    marker.style.left = `${(px / width) * 100}%`;
    marker.style.top = `${(py / height) * 100}%`;
    marker.style.transform = `translate(-50%, -50%) rotate(${-yaw}rad)`;
}

// Side-bar View Switching
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const view = btn.getAttribute('data-view');
        
        document.querySelector('.nav-btn.active')?.classList.remove('active');
        btn.classList.add('active');
        document.getElementById('view-title').innerText = btn.innerText;
        
        // Hide all overlays and control layers
        document.getElementById('mapping-overlay')?.classList.add('hidden');
        document.getElementById('waypoints-overlay')?.classList.add('hidden');
        document.getElementById('control-layer')?.classList.add('hidden');
        
        // Navigation logic
        const viewport = document.getElementById('viewport');
        if (viewport) viewport.style.display = 'flex';

        if (view === 'pilot') {
            document.getElementById('control-layer')?.classList.remove('hidden');
        } else if (view === 'mapping') {
            document.getElementById('mapping-overlay')?.classList.remove('hidden');
        } else if (view === 'navigation') {
            document.getElementById('waypoints-overlay')?.classList.remove('hidden');
            renderWaypoints();
        } else if (view === 'settings') {
            if (viewport) viewport.style.display = 'none';
        }
        
        // Auto-close sidebar on mobile
        if (window.innerWidth <= 1024) {
            sidebar.classList.remove('open');
        }
    });
});
