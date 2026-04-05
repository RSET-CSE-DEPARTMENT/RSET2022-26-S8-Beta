// Pin Definitions (Avoiding your occupied pins)
const int motorEnable = 12; // ENA
const int motorDir1 = 7;    // IN1
const int motorDir2 = 8;    // IN2

void setup() {
  pinMode(motorEnable, OUTPUT);
  pinMode(motorDir1, OUTPUT);
  pinMode(motorDir2, OUTPUT);
  
  Serial.begin(115200);
  Serial.println("Binbot Motor Logic Initialized (Pins 12, 7, 8)");
  
  stopMotor(); // Start in a safe state
}

void moveForward() {
  digitalWrite(motorDir1, HIGH);
  digitalWrite(motorDir2, LOW);
  digitalWrite(motorEnable, HIGH);
  Serial.println("Moving Forward...");
}

void moveBackward() {
  digitalWrite(motorDir1, LOW);
  digitalWrite(motorDir2, HIGH);
  digitalWrite(motorEnable, HIGH);
  Serial.println("Moving Backward...");
}

void stopMotor() {
  digitalWrite(motorEnable, LOW);
  digitalWrite(motorDir1, LOW);
  digitalWrite(motorDir2, LOW);
  Serial.println("Motor Stopped.");
}

void loop() {
  // Move Forward 2 Seconds
  moveForward();
  delay(2000);

  // Short Brake for safety
  stopMotor();
  delay(500);

  // Move Backward 2 Seconds
  moveBackward();
  delay(2000);

  // Stop and wait
  stopMotor();
  Serial.println("Cycle complete. Waiting 5 seconds...");
  delay(5000);
}