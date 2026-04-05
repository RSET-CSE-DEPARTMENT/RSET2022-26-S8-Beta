import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TransformStamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu
from std_msgs.msg import Empty, Int16
import tf2_ros
from tf_transformations import quaternion_from_euler
import serial
import struct
import math

class ArduinoBridge(Node):
    def __init__(self):
        super().__init__('arduino_bridge')
        
        self.declare_parameter('port', '/dev/arduino')
        self.declare_parameter('baudrate', 115200)
        self.declare_parameter('ticks_per_meter', 3186.0) # Adjusted for 10cm wheels
        self.declare_parameter('wheel_base', 0.45)      # Measured 45cm width
        self.declare_parameter('publish_tf', True)
        self.declare_parameter('use_gyro', True)
        self.declare_parameter('publish_imu', True)
        
        self.port = self.get_parameter('port').value
        self.baudrate = self.get_parameter('baudrate').value
        self.TICKS_PER_METER = self.get_parameter('ticks_per_meter').value
        self.WHEEL_BASE = self.get_parameter('wheel_base').value
        self.publish_tf = self.get_parameter('publish_tf').value
        self.use_gyro = self.get_parameter('use_gyro').value
        
        self.ser = None
        self.connect_serial()

        self.x = 0.0
        self.y = 0.0
        self.th = 0.0
        self.last_l_ticks = None
        self.last_r_ticks = None
        self.last_time = self.get_clock().now()

        # Motor State
        self.target_l = 0
        self.target_r = 0
        self.target_aux = 0
        self.consecutive_crc_failures = 0

        self.odom_pub = self.create_publisher(Odometry, 'odom', 10)
        self.imu_pub = self.create_publisher(Imu, 'imu/data_raw', 10)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)
        self.sub = self.create_subscription(Twist, 'cmd_vel', self.cmd_callback, 10)
        self.aux_sub = self.create_subscription(Int16, 'aux_motor/cmd', self.aux_callback, 10)
        self.reset_sub = self.create_subscription(Empty, 'reset_odom', self.reset_callback, 10)
        
        self.create_timer(0.01, self.update_odom) # 100Hz

    def reset_callback(self, msg):
        self.x = 0.0
        self.y = 0.0
        self.th = 0.0
        self.get_logger().info("Odometry reset to zero.")

    def connect_serial(self):
        try:
            if self.ser: self.ser.close()
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.01)
            self.ser.reset_input_buffer()
            self.get_logger().info(f"Connected to Arduino (Binary Mode) on {self.port}")
        except Exception as e:
            self.get_logger().error(f"Serial error: {e}")
            self.ser = None
            self.last_l_ticks = None
            self.last_r_ticks = None

    def cmd_callback(self, msg):
        v, w = msg.linear.x, msg.angular.z
        v_l = v - (w * self.WHEEL_BASE / 2.0)
        v_r = v + (w * self.WHEEL_BASE / 2.0)
        
        # Asymmetric Drift Compensation:
        # The front-right quadrant is physically heavier. Boost the right motor 
        # algorithmically by 25% so it has the explicit torque to over-match the friction
        v_r = v_r * 1.25 
        
        self.target_l = max(-255, min(255, int(v_l * 400))) 
        self.target_r = max(-255, min(255, int(v_r * 400)))
        self.send_robot_cmd()

    def aux_callback(self, msg):
        self.target_aux = msg.data
        self.send_robot_cmd()

    def send_robot_cmd(self):
        if not self.ser or not self.ser.is_open: return
        
        # Packet: [0xAA, 0x55, pwm_l(2), pwm_r(2), pwm_aux(2), crc(1)]
        crc = (self.target_l ^ self.target_r ^ self.target_aux) & 0xFF
        packet = struct.pack('>BBhhhB', 0xAA, 0x55, self.target_l, self.target_r, self.target_aux, crc)
        
        try:
            self.ser.write(packet)
        except Exception as e:
            self.get_logger().error(f"Write error: {e}")
            self.ser = None

    def update_odom(self):
        if not self.ser or not self.ser.is_open:
            self.connect_serial()
            return

        try:
            # Backlog Protection: Flush buffer if it's falling behind ( > 500 bytes)
            if self.ser.in_waiting > 500:
                self.get_logger().warn(f"Serial backlog detected ({self.ser.in_waiting} bytes). Flushing buffer to restore real-time sync.")
                self.ser.reset_input_buffer()
                return

            has_new_data = False
            while self.ser.in_waiting >= 23:
                # Find header [0xAA, 0x55] by sliding one byte at a time
                header_check = self.ser.read(1)
                if header_check != b'\xAA':
                    continue
                
                next_byte = self.ser.read(1)
                if next_byte != b'\x55':
                    # If it wasn't 55, we effectively "consumed" the AA and will try again
                    continue
                
                # We found [AA, 55], read the 21-byte payload
                payload = self.ser.read(21)
                if len(payload) < 21:
                    break
                
                # Unpack: ticks (2x i=4), IMU (6x h=2), CRC (1x B=1)
                try:
                    l_ticks, r_ticks, ax, ay, az, gx, gy, gz, crc = struct.unpack('>iihhhhhhB', payload)
                except struct.error as e:
                    self.get_logger().warn(f"Unpack error: {e}")
                    continue
                
                # Check CRC (XOR of all bytes in payload except the last one)
                calc_crc = 0
                for b in payload[:-1]:
                    calc_crc ^= b
                
                if calc_crc != crc:
                    self.consecutive_crc_failures += 1
                    self.get_logger().warn(f"CRC Mismatch ({self.consecutive_crc_failures}/5). Calc: {calc_crc:02X}, Recv: {crc:02X}")
                    
                    if self.consecutive_crc_failures >= 5:
                        self.get_logger().error("Sync lost! Flushing serial buffer for re-alignment.")
                        self.ser.reset_input_buffer()
                        self.consecutive_crc_failures = 0
                    continue
                
                # Success! Reset failure counter
                self.consecutive_crc_failures = 0
                
                l_ticks = -l_ticks # Restore left-side motor inversion
                
                if self.last_l_ticks is None:
                    self.last_l_ticks, self.last_r_ticks = l_ticks, r_ticks
                    continue

                dl = (l_ticks - self.last_l_ticks) / self.TICKS_PER_METER
                dr = (r_ticks - self.last_r_ticks) / self.TICKS_PER_METER
                self.last_l_ticks, self.last_r_ticks = l_ticks, r_ticks
                
                # Displacement and Heading Update
                d_center = (dl + dr) / 2.0
                
                now_abs = self.get_clock().now()
                dt = (now_abs - self.last_time).nanoseconds / 1e9
                self.last_time = now_abs

                if self.use_gyro:
                    # IMU is mounted upright (VCC forward). Vertical axis is X.
                    # Convert deg/s to rad/s.
                    d_theta = (gx / 1000.0) * (math.pi / 180.0) * dt
                else:
                    d_theta = (dr - dl) / self.WHEEL_BASE
                
                self.x += d_center * math.cos(self.th)
                self.y += d_center * math.sin(self.th)
                self.th += d_theta
                has_new_data = True

            if has_new_data:
                now = self.get_clock().now().to_msg()
                q = quaternion_from_euler(0, 0, self.th)
                
                # BroadTF
                t = TransformStamped()
                t.header.stamp = now
                t.header.frame_id, t.child_frame_id = 'odom', 'base_link'
                t.transform.translation.x, t.transform.translation.y = self.x, self.y
                t.transform.rotation.x, t.transform.rotation.y = q[0], q[1]
                t.transform.rotation.z, t.transform.rotation.w = q[2], q[3]
                if self.publish_tf:
                    self.tf_broadcaster.sendTransform(t)

                # IMU Data (Convert g's to m/s^2, degrees/sec to rad/s)
                G_TO_MS2 = 9.80665
                imu = Imu()
                imu.header.stamp = now
                imu.header.frame_id = 'imu_link'
                imu.linear_acceleration.x = (ax / 100.0) * G_TO_MS2
                imu.linear_acceleration.y = (ay / 100.0) * G_TO_MS2
                imu.linear_acceleration.z = (az / 100.0) * G_TO_MS2
                imu.angular_velocity.x = (gx / 1000.0) * (math.pi / 180.0)
                imu.angular_velocity.y = (gy / 1000.0) * (math.pi / 180.0)
                imu.angular_velocity.z = (gz / 1000.0) * (math.pi / 180.0)
                if self.get_parameter('publish_imu').value:
                    self.imu_pub.publish(imu)

                # Odom
                odom = Odometry()
                odom.header.stamp = now
                odom.header.frame_id, odom.child_frame_id = 'odom', 'base_link'
                odom.pose.pose.position.x, odom.pose.pose.position.y = self.x, self.y
                odom.pose.pose.orientation.x, odom.pose.pose.orientation.y = q[0], q[1]
                odom.pose.pose.orientation.z, odom.pose.pose.orientation.w = q[2], q[3]
                self.odom_pub.publish(odom)

        except Exception as e:
            self.get_logger().error(f"Bridge error: {e}")
            self.ser = None
            self.last_l_ticks = None
            self.last_r_ticks = None

def main(args=None):
    rclpy.init(args=args)
    node = ArduinoBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()