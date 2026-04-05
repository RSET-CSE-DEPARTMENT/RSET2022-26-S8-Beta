import sys
import time
import requests
from datetime import datetime
import cv2
import numpy as np
import tensorflow as tf
from ultralytics import YOLO
from collections import deque
import threading
import os
from dotenv import load_dotenv   # ADD THIS

load_dotenv()  # ADD THIS
# ==========================================
# CONFIGURATION
# ==========================================

ALERT_SERVER_URL = os.getenv("ALERT_SERVER_URL")
CAMERA_ID = "CAM-01"   
IP_CAMERA_URL = os.getenv("IP_CAMERA_URL")
MODEL_PATH = "quiet_sos_lstm_fall_detector.h5"

ABNORMAL_THRESHOLD = 0.5
EMA_ALPHA = 0.2
LOOKBACK_FRAMES = 60

SEQUENCE_LENGTH = 30
NUM_KEYPOINTS = 17
FEATURES_PER_KEYPOINT = 3
NUM_FEATURES = NUM_KEYPOINTS * FEATURES_PER_KEYPOINT

FALL_THRESHOLD = 0.75
GROUND_TIME_SECONDS = 10
GROUND_Y_RATIO = 0.65

# ==========================================
# UTILS & THREADED CAMERA
# ==========================================

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def aspect_ratio_score(w, h):
    return sigmoid((w / h - 1.2) * 4)

class RealTimeVideoStream:
    """ Continuously fetches the latest frame in a background thread to prevent OpenCV buffer lag. """
    def __init__(self, src):
        self.stream = cv2.VideoCapture(src)
        self.stream.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        
        self.ret, self.frame = self.stream.read()
        self.stopped = False
        
        self.thread = threading.Thread(target=self.update, args=())
        self.thread.daemon = True
        self.thread.start()

    def update(self):
        while not self.stopped:
            if not self.stream.isOpened():
                continue
            ret, frame = self.stream.read()
            if ret:
                self.ret, self.frame = ret, frame
            else:
                time.sleep(0.1)

    def read(self):
        return self.ret, self.frame

    def stop(self):
        self.stopped = True
        self.thread.join()
        self.stream.release()

# ==========================================
# LOAD MODELS
# ==========================================

print("Loading models... Please wait.")
det_model = YOLO("yolov8n.pt").to("cuda:0")
pose_model = YOLO("yolov8n-pose.pt")
lstm_model = tf.keras.models.load_model(MODEL_PATH)
print("Models loaded successfully!")

# ==========================================
# VIDEO SETUP
# ==========================================

print(f"Connecting to live stream at {IP_CAMERA_URL}...")
cap = RealTimeVideoStream(IP_CAMERA_URL)
time.sleep(2.0) # Give the camera time to warm up

# ==========================================
# BUFFERS & STATES
# ==========================================

frame_buffer = deque(maxlen=LOOKBACK_FRAMES)
pose_buffer = deque(maxlen=SEQUENCE_LENGTH)

prefilter_active = True
model_active = False

aspect_score = 0.0

fall_candidate_active = False
ground_start_time = None
alert_sent = False
recovery_frames = 0 # NEW: Prevents instant timer resets

fall_detected = False
last_fall_prob = 0.0  

last_bbox = None
buffered_frames = []

def send_alert_once(camera_id):
    try:
        payload = {
            "cameraId": camera_id,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        response = requests.post(ALERT_SERVER_URL, json=payload, timeout=3)
        if response.status_code == 200:
            print("\n[SUCCESS] ALERT SENT TO SERVER SUCCESSFULLY")
        else:
            print("\n[ERROR] Alert failed:", response.text)
    except Exception as e:
        print("\n[ERROR] Alert server not reachable:", e)

# ==========================================
# MAIN LOOP
# ==========================================

print("\nStarting QuietSOS Live Monitor. Press 'q' on the video window to quit.\n")

while True:
    
    if model_active and buffered_frames:
        current_frame = buffered_frames.pop(0)
    else:
        ret, frame = cap.read()
        if not ret or frame is None:
            continue
        current_frame = frame.copy()

    h, w, _ = current_frame.shape
    display_frame = current_frame.copy()

    term_state = "PREFILTER (Idle)"
    term_prob = last_fall_prob
    term_ground = "Upright"

    # -------------------------------------------------
    # PREFILTER
    # -------------------------------------------------
    if prefilter_active:
        frame_buffer.append(current_frame.copy())

        results = det_model.predict(
            current_frame,
            imgsz=320,
            conf=0.25,
            classes=[0],
            device="cuda:0",
            half=True, 
            verbose=False
        )[0]

        if len(results.boxes) > 0:
            box = results.boxes[results.boxes.conf.argmax().item()]
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            bw, bh = x2 - x1, y2 - y1

            last_bbox = (x1, y1, x2, y2)
            aspect_score = (1 - EMA_ALPHA) * aspect_score + EMA_ALPHA * aspect_ratio_score(bw, bh)

            color = (0, 0, 255) if aspect_score > ABNORMAL_THRESHOLD else (0, 255, 0)
            
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(display_frame, f"Aspect: {aspect_score:.2f}",
                        (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            term_state = f"PREFILTER (Aspect: {aspect_score:.2f})"

            if aspect_score > ABNORMAL_THRESHOLD:
                prefilter_active = False
                model_active = True
                buffered_frames = list(frame_buffer)
                frame_buffer.clear()

    # -------------------------------------------------
    # MODEL ACTIVE 
    # -------------------------------------------------
    seconds_on_ground = None
    
    if model_active:
        on_ground = False
        is_standing = False
        term_state = "LSTM POSE ACTIVE"
        
        results = pose_model(current_frame, device="cuda:0", half=True, imgsz=320, verbose=False)

        # 1. EVALUATE POSTURE
        if len(results[0].keypoints) > 0 and results[0].keypoints.xy.nelement() > 0:
            kps = results[0].keypoints.xy[0].cpu().numpy()
            confs = results[0].keypoints.conf[0].cpu().numpy()

            # Dynamic Horizontal Check (Robust against camera angles)
            valid_kps = [kp for i, kp in enumerate(kps) if confs[i] > 0.2]
            if len(valid_kps) > 3:
                xs = [kp[0] for kp in valid_kps]
                ys = [kp[1] for kp in valid_kps]
                kp_w = max(xs) - min(xs)
                kp_h = max(ys) - min(ys)
                is_horizontal = kp_w > (kp_h * 0.9) # Person is wider than they are tall
            else:
                is_horizontal = False

            mean_hip_y = (kps[11][1] + kps[12][1]) / 2
            is_low = mean_hip_y > GROUND_Y_RATIO * h
            
            on_ground = is_low or is_horizontal
            is_standing = not on_ground

            # 2. RUN LSTM (Only if not already confirmed as fallen)
            if not fall_candidate_active:
                feature_vector = []
                for i in range(NUM_KEYPOINTS):
                    feature_vector.extend([kps[i][0], kps[i][1], confs[i]])

                pose_buffer.append(feature_vector)

                if len(pose_buffer) == SEQUENCE_LENGTH:
                    sequence = np.array(pose_buffer, dtype=np.float32)
                    sequence = sequence.reshape(1, SEQUENCE_LENGTH, NUM_FEATURES)
                    
                    last_fall_prob = lstm_model(sequence, training=False).numpy()[0][0]
                    fall_detected = last_fall_prob > FALL_THRESHOLD
                    term_prob = last_fall_prob

        # 3. FALL CONFIRMATION & GET UP LOGIC (Debounced)
        if fall_detected and not fall_candidate_active and not alert_sent:
            fall_candidate_active = True
            ground_start_time = time.time()
            recovery_frames = 0

        if fall_candidate_active and not alert_sent:
            if is_standing:
                recovery_frames += 1
                # Must stand cleanly for 15 frames (~0.5 sec) to reset the fall timer
                if recovery_frames >= 15: 
                    fall_candidate_active = False
                    ground_start_time = None
                    fall_detected = False
                    pose_buffer.clear() 
                    recovery_frames = 0
            else:
                # Still down, or pose lost (assume still down)
                recovery_frames = 0 
                if ground_start_time is None:
                    ground_start_time = time.time()
                elif time.time() - ground_start_time >= GROUND_TIME_SECONDS:
                    alert_sent = True
                    print("\n[CRITICAL] Alert conditions met. Triggering webhook...") 
                    send_alert_once(CAMERA_ID)

        # 4. GROUND TIME CALCULATION
        if ground_start_time is not None:
            seconds_on_ground = time.time() - ground_start_time
            term_ground = f"{seconds_on_ground:.1f}s"
            
        if alert_sent:
            term_state = "ALERT TRIGGERED"

    # -------------------------------------------------
    # UI OVERLAY (HUD) ON VIDEO
    # -------------------------------------------------
    overlay = display_frame.copy()
    cv2.rectangle(overlay, (10, 10), (450, 180), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, display_frame, 0.4, 0, display_frame)

    hud_x = 20
    hud_y = 40
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    cv2.putText(display_frame, "QuietSOS Live Monitor", (hud_x, hud_y), font, 0.7, (255, 255, 255), 2)
    cv2.line(display_frame, (hud_x, hud_y + 10), (430, hud_y + 10), (255, 255, 255), 1)
    hud_y += 35

    cv2.putText(display_frame, f"State: {term_state}", (hud_x, hud_y), font, 0.6, (255, 200, 0), 2)
    hud_y += 30

    prob_color = (0, 255, 0) if term_prob < 0.40 else ((0, 255, 255) if term_prob < FALL_THRESHOLD else (0, 0, 255))
    cv2.putText(display_frame, f"Fall Prob: {term_prob:.2f}", (hud_x, hud_y), font, 0.6, prob_color, 2)
    hud_y += 30

    ground_color = (0, 0, 255) if seconds_on_ground is not None else (0, 255, 0)
    cv2.putText(display_frame, f"Ground Time: {term_ground}", (hud_x, hud_y), font, 0.6, ground_color, 2)

    # ===================================================
    # MASSIVE CENTRAL TIMER (Shows only during a fall)
    # ===================================================
    if fall_candidate_active and not alert_sent and seconds_on_ground is not None:
        center_text = f"FALL DETECTED: {seconds_on_ground:.1f}s"
        cv2.putText(display_frame, center_text, (w // 2 - 220, 80), font, 1.2, (0, 165, 255), 4)
        
    # Large Alert Banner
    if alert_sent:
        cv2.rectangle(display_frame, (0, h - 60), (w, h), (0, 0, 255), -1)
        cv2.putText(display_frame, "CRITICAL ALERT: EMERGENCY CONFIRMED", (w // 2 - 250, h - 20), font, 0.9, (255, 255, 255), 3)

    # -------------------------------------------------
    # TERMINAL OUTPUT
    # -------------------------------------------------
    sys.stdout.write(f"\r[LIVE FEED] Mode: {term_state:<28} | Fall Prob: {term_prob:.2f} | Ground Status: {term_ground:<10}")
    sys.stdout.flush()

    # -------------------------------------------------
    # DISPLAY
    # -------------------------------------------------
    cv2.imshow("QuietSOS Live Monitor", display_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        print("\n\nExiting stream...")
        break

# ==========================================
# CLEANUP
# ==========================================
cap.stop()
cv2.destroyAllWindows()
print("✅ QuietSOS live stream closed.")