#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

/*
 * TITAN-Core Firmware v1.5
 * Includes IMU telemetry (23-byte packet)
 */

// --- HARDWARE PINOUT ---
#define PIN_R_PWM_F 6
#define PIN_R_PWM_B 11
#define PIN_L_PWM_F 9
#define PIN_L_PWM_B 10

#define PIN_ENC_R_A 2 
#define PIN_ENC_R_B 4
#define PIN_ENC_L_A 3
#define PIN_ENC_L_B 5

#define PIN_AUX_ENA 12
#define PIN_AUX_IN1 7
#define PIN_AUX_IN2 8
// -----------------------

Adafruit_MPU6050 mpu;

volatile long left_ticks = 0;
volatile long right_ticks = 0;

// IMU Offsets
float gx_off = 0, gy_off = 0, gz_off = 0;
float ax_off = 0, ay_off = 0, az_off = 0;

unsigned long last_cmd_time = 0;
const unsigned long WATCHDOG_TIMEOUT = 500; // ms

void setup() {
  Serial.begin(115200);
  
  pinMode(PIN_L_PWM_F, OUTPUT); pinMode(PIN_L_PWM_B, OUTPUT);
  pinMode(PIN_R_PWM_F, OUTPUT); pinMode(PIN_R_PWM_B, OUTPUT);
  
  pinMode(PIN_ENC_L_A, INPUT_PULLUP); pinMode(PIN_ENC_L_B, INPUT_PULLUP);
  pinMode(PIN_ENC_R_A, INPUT_PULLUP); pinMode(PIN_ENC_R_B, INPUT_PULLUP);
  
  pinMode(PIN_AUX_ENA, OUTPUT);
  pinMode(PIN_AUX_IN1, OUTPUT);
  pinMode(PIN_AUX_IN2, OUTPUT);

  attachInterrupt(digitalPinToInterrupt(PIN_ENC_L_A), handleL, RISING);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_R_A), handleR, RISING);

  if (!mpu.begin()) {
    // If IMU fails, we still want the robot to work
    // Serial.println("Failed to find MPU6050 chip");
  } else {
    mpu.setAccelerometerRange(MPU6050_RANGE_8_G);
    mpu.setGyroRange(MPU6050_RANGE_500_DEG);
    mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);

    // Startup Calibration (Robot must be still and flat)
    const int num_samples = 100;
    for (int i = 0; i < num_samples; i++) {
      sensors_event_t a, g, temp;
      mpu.getEvent(&a, &g, &temp);
      gx_off += g.gyro.x; gy_off += g.gyro.y; gz_off += g.gyro.z;
      ax_off += a.acceleration.x; ay_off += a.acceleration.y;
      // We don't tare Z acceleration as it accounts for gravity (~9.8)
      delay(5);
    }
    gx_off /= num_samples; gy_off /= num_samples; gz_off /= num_samples;
    ax_off /= num_samples; ay_off /= num_samples;
  }
}

void loop() {
  if (Serial.available() >= 9) {
    if (Serial.read() == 0xAA && Serial.read() == 0x55) {
      int16_t pwm_l = (int16_t)((Serial.read() << 8) | Serial.read());
      int16_t pwm_r = (int16_t)((Serial.read() << 8) | Serial.read());
      int16_t pwm_aux = (int16_t)((Serial.read() << 8) | Serial.read());
      uint8_t crc = Serial.read();
      
      if (((pwm_l ^ pwm_r ^ pwm_aux) & 0xFF) == crc) {
        setMotors(pwm_l, pwm_r);
        setAuxMotor(pwm_aux);
        last_cmd_time = millis();
      }
    }
  }

  if (millis() - last_cmd_time > WATCHDOG_TIMEOUT) {
    setMotors(0, 0);
    setAuxMotor(0);
  }

  static unsigned long last_telemetry = 0;
  if (millis() - last_telemetry > 20) {
    sendTelemetry();
    last_telemetry = millis();
  }
}

void setMotors(int l, int r) {
  l = constrain(l, -255, 255);
  r = constrain(r, -255, 255);

  if (l >= 0) { analogWrite(PIN_L_PWM_F, l); analogWrite(PIN_L_PWM_B, 0); }
  else { analogWrite(PIN_L_PWM_F, 0); analogWrite(PIN_L_PWM_B, abs(l)); }
  
  if (r >= 0) { analogWrite(PIN_R_PWM_F, r); analogWrite(PIN_R_PWM_B, 0); }
  else { analogWrite(PIN_R_PWM_F, 0); analogWrite(PIN_R_PWM_B, abs(r)); }
}

void setAuxMotor(int speed) {
  if (speed > 0) {
    digitalWrite(PIN_AUX_IN1, HIGH);
    digitalWrite(PIN_AUX_IN2, LOW);
    digitalWrite(PIN_AUX_ENA, HIGH);
  } else if (speed < 0) {
    digitalWrite(PIN_AUX_IN1, LOW);
    digitalWrite(PIN_AUX_IN2, HIGH);
    digitalWrite(PIN_AUX_ENA, HIGH);
  } else {
    digitalWrite(PIN_AUX_IN1, LOW);
    digitalWrite(PIN_AUX_IN2, LOW);
    digitalWrite(PIN_AUX_ENA, LOW);
  }
}

void sendTelemetry() {
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  uint8_t buffer[23];
  buffer[0] = 0xAA;
  buffer[1] = 0x55;
  
  // Encoders (8 bytes)
  byte* l_ptr = (byte*)&left_ticks;
  byte* r_ptr = (byte*)&right_ticks;
  for (int i = 0; i < 4; i++) {
    buffer[2+i] = l_ptr[3-i]; // Big Endian
    buffer[6+i] = r_ptr[3-i];
  }

  // IMU Accel (6 bytes, scaled * 100)
  int16_t ax = (a.acceleration.x - ax_off) * 100;
  int16_t ay = (a.acceleration.y - ay_off) * 100;
  int16_t az = a.acceleration.z * 100;
  buffer[10] = ax >> 8; buffer[11] = ax & 0xFF;
  buffer[12] = ay >> 8; buffer[13] = ay & 0xFF;
  buffer[14] = az >> 8; buffer[15] = az & 0xFF;

  // IMU Gyro (6 bytes, scaled * 1000)
  int16_t gx = (g.gyro.x - gx_off) * 1000;
  int16_t gy = (g.gyro.y - gy_off) * 1000;
  int16_t gz = (g.gyro.z - gz_off) * 1000;
  buffer[16] = gx >> 8; buffer[17] = gx & 0xFF;
  buffer[18] = gy >> 8; buffer[19] = gy & 0xFF;
  buffer[20] = gz >> 8; buffer[21] = gz & 0xFF;
  
  // Byte-wise XOR CRC
  uint8_t crc = 0;
  for (int i = 2; i < 22; i++) crc ^= buffer[i];
  buffer[22] = crc;

  Serial.write(buffer, 23);
}

void handleL() {
  if (digitalRead(PIN_ENC_L_B) == HIGH) left_ticks++;
  else left_ticks--;
}

void handleR() {
  if (digitalRead(PIN_ENC_R_B) == HIGH) right_ticks++;
  else right_ticks--;
}
