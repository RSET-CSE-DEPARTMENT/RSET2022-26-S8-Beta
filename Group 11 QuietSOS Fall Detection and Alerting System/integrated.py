import time
import requests
from datetime import datetime
import cv2
import numpy as np
import tensorflow as tf
from ultralytics import YOLO
from collections import deque

# ==========================================
# CONFIGURATION
# ==========================================

ALERT_SERVER_URL = "http://127.0.0.1:5000/trigger-alert"
CAMERA_ID = "CAM-01"   
VIDEO_PATH = r"C:\Users\91807\Downloads\GokulJef4.mp4"
MODEL_PATH = "quiet_sos_lstm_fall_detector.h5"

ABNORMAL_THRESHOLD = 0.5
EMA_ALPHA = 0.2
LOOKBACK_FRAMES = 60

SEQUENCE_LENGTH = 30
NUM_KEYPOINTS = 17
FEATURES_PER_KEYPOINT = 3
NUM_FEATURES = NUM_KEYPOINTS * FEATURES_PER_KEYPOINT

FALL_THRESHOLD = 0.75
GROUND_TIME_SECONDS = 15
GROUND_Y_RATIO = 0.65

# ==========================================
# UTILS
# ==========================================

def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def aspect_ratio_score(w, h):
    return sigmoid((w / h - 1.2) * 4)

# ==========================================
# LOAD MODELS
# ==========================================

det_model = YOLO("yolov8n.pt").to("cuda:0")
pose_model = YOLO("yolov8n-pose.pt")
lstm_model = tf.keras.models.load_model(MODEL_PATH)

# ==========================================
# VIDEO SETUP
# ==========================================

cap = cv2.VideoCapture(VIDEO_PATH)
assert cap.isOpened(), " Cannot open video"

fps = cap.get(cv2.CAP_PROP_FPS)
if fps == 0 or np.isnan(fps):
    fps = 30.0  

frame_duration = 1.0 / fps  
GROUND_FRAMES_REQUIRED = int(GROUND_TIME_SECONDS * fps)

# ==========================================
# BUFFERS & STATES
# ==========================================

frame_buffer = deque(maxlen=LOOKBACK_FRAMES)
pose_buffer = deque(maxlen=SEQUENCE_LENGTH)

prefilter_active = True
model_active = False

aspect_score = 0.0
frame_index = 0

fall_candidate_active = False
ground_start_frame = None
alert_sent = False

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
            print(" ALERT SENT SUCCESSFULLY")
        else:
            print(" Alert failed:", response.text)
    except Exception as e:
        print(" Alert server not reachable:", e)

# ==========================================
# MAIN LOOP
# ==========================================

# Establish the rigid schedule right before we start
next_frame_target_time = time.time()

while cap.isOpened():
    
    if model_active and buffered_frames:
        current_frame = buffered_frames.pop(0)
    else:
        ret, frame = cap.read()
        if not ret:
            break
        current_frame = frame

    h, w, _ = current_frame.shape
    display_frame = current_frame.copy()

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
            label = "ABNORMAL" if aspect_score > ABNORMAL_THRESHOLD else "NORMAL"

            cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(display_frame, f"{label} | Score: {aspect_score:.2f}",
                        (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            if aspect_score > ABNORMAL_THRESHOLD:
                prefilter_active = False
                model_active = True
                buffered_frames = list(frame_buffer)
                frame_buffer.clear()

    # -------------------------------------------------
    # MODEL ACTIVE 
    # -------------------------------------------------
    if model_active:
        on_ground = False
        
        results = pose_model(current_frame, device="cuda:0", half=True, imgsz=320, verbose=False)

        if len(results[0].keypoints) > 0 and results[0].keypoints.xy.nelement() > 0:
            kps = results[0].keypoints.xy[0].cpu().numpy()
            confs = results[0].keypoints.conf[0].cpu().numpy()

            mean_hip_y = (kps[11][1] + kps[12][1]) / 2
            on_ground = mean_hip_y > GROUND_Y_RATIO * h

            # DISABLE LSTM WHILE ON GROUND TO SAVE GPU POWER
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
        else:
            if not fall_candidate_active:
                pose_buffer.clear()
            on_ground = False

        # FALL CONFIRMATION & GET UP LOGIC
        if fall_detected and not fall_candidate_active and not alert_sent:
            fall_candidate_active = True
            ground_start_frame = frame_index 

        if fall_candidate_active and not alert_sent:
            if on_ground:
                if ground_start_frame is None:
                    ground_start_frame = frame_index
                elif frame_index - ground_start_frame >= GROUND_FRAMES_REQUIRED:
                    alert_sent = True
                    send_alert_once(CAMERA_ID)
            else:
                # User stood back up
                fall_candidate_active = False
                ground_start_frame = None
                fall_detected = False
                pose_buffer.clear() 

        # GROUND TIME CALCULATION
        seconds_on_ground = None
        if ground_start_frame is not None:
            seconds_on_ground = (frame_index - ground_start_frame) / fps

        # UI
        x, y = w - 380, 40

        if alert_sent:
            cv2.putText(display_frame, "ALERT SENT : FALL CONFIRMED",
                        (x - 40, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)

            if seconds_on_ground is not None:
                cv2.putText(display_frame, f"On Ground : {seconds_on_ground:.1f}s",
                            (x, y + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        else:
            if last_fall_prob is not None:
                prob_color = (0, 255, 0) if last_fall_prob < 0.40 else ((0, 255, 255) if last_fall_prob < FALL_THRESHOLD else (0, 0, 255))
                prob_state = "Normal" if last_fall_prob < 0.40 else ("Warning" if last_fall_prob < FALL_THRESHOLD else "High Risk")

                cv2.putText(display_frame, f"Fall Prob     : {last_fall_prob:.2f}",
                            (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.75, prob_color, 2)
                y += 30
                cv2.putText(display_frame, f"Fall Status   : {prob_state}",
                            (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, prob_color, 2)
                y += 30

            if fall_candidate_active:
                ground_text = f"On Ground ({seconds_on_ground:.1f}s)" if seconds_on_ground is not None else "Ground Check Started"
                ground_color = (0, 0, 255) if seconds_on_ground is not None else (0, 255, 255)
            else:
                ground_text = "Standing / Moving"
                ground_color = (0, 255, 0)

            cv2.putText(display_frame, f"Ground Status : {ground_text}",
                        (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, ground_color, 2)

    # -------------------------------------------------
    # DISPLAY
    # -------------------------------------------------
    cv2.imshow("QuietSOS Real-Time Sync", display_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    frame_index += 1

    # -------------------------------------------------
    # DYNAMIC REAL-TIME SYNC LOGIC (ABSOLUTE CLOCK)
    # -------------------------------------------------
    next_frame_target_time += frame_duration
    current_time = time.time()
    
    if current_time < next_frame_target_time:
        # We finished early. Sleep exactly until the real-world clock catches up.
        time.sleep(next_frame_target_time - current_time)
    else:
        if not buffered_frames:
            # We fell behind schedule. Fast-forward frames until we catch back up to reality.
            while time.time() > next_frame_target_time + frame_duration:
                if cap.grab():
                    frame_index += 1
                    next_frame_target_time += frame_duration
                else:
                    break
        else:
            # Prevent massive frame drops while clearing the prefilter buffer
            next_frame_target_time = time.time()

# ==========================================
# CLEANUP
# ==========================================
cap.release()
cv2.destroyAllWindows()
print("✅ QuietSOS finished successfully.")