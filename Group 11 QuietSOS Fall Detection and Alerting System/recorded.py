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
CAMERA_ID = "CAM-REC-01"

# 🎥 RECORDED VIDEO PATH
VIDEO_PATH = r"C:\Users\91807\Downloads\GokulJef4.mp4"

MODEL_PATH = "quiet_sos_lstm_fall_detector.h5"

ABNORMAL_THRESHOLD = 0.5
EMA_ALPHA = 0.2

# 🔴 MICRO BUFFER (RAW FRAMES)
MICRO_BUFFER_SIZE = 8   # ~250 ms @ 30 fps

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
# VIDEO SETUP (RECORDED FILE)
# ==========================================

cap = cv2.VideoCapture(VIDEO_PATH)
assert cap.isOpened(), "❌ Cannot open video file"

fps = cap.get(cv2.CAP_PROP_FPS)
if fps == 0 or np.isnan(fps):
    fps = 30.0

frame_duration = 1.0 / fps
GROUND_FRAMES_REQUIRED = int(GROUND_TIME_SECONDS * fps)

# ==========================================
# BUFFERS & STATES
# ==========================================

# 🔴 RAW FRAME MICRO BUFFER
frame_buffer = deque(maxlen=MICRO_BUFFER_SIZE)

# LSTM POSE BUFFER
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

buffered_frames = []

# ==========================================
# ALERT FUNCTION
# ==========================================

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

next_frame_target_time = time.time()

while cap.isOpened():

    # --------------------------------------
    # FRAME READ (RECORDED VIDEO)
    # --------------------------------------
    if model_active and buffered_frames:
        current_frame = buffered_frames.pop(0)
    else:
        ret, frame = cap.read()
        if not ret:
            break
        current_frame = frame
        frame_buffer.append(current_frame.copy())

    h, w, _ = current_frame.shape
    display_frame = current_frame.copy()

    # --------------------------------------
    # PREFILTER (YOLO BBOX)
    # --------------------------------------
    if prefilter_active:
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

    # --------------------------------------
    # MODEL ACTIVE (POSE + LSTM)
    # --------------------------------------
    if model_active:
        on_ground = False

        results = pose_model(current_frame, device="cuda:0", half=True, imgsz=320, verbose=False)

        if len(results[0].keypoints) > 0 and results[0].keypoints.xy.nelement() > 0:
            kps = results[0].keypoints.xy[0].cpu().numpy()
            confs = results[0].keypoints.conf[0].cpu().numpy()

            mean_hip_y = (kps[11][1] + kps[12][1]) / 2
            on_ground = mean_hip_y > GROUND_Y_RATIO * h

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
            pose_buffer.clear()

        if fall_detected and not fall_candidate_active and not alert_sent:
            fall_candidate_active = True
            ground_start_frame = frame_index

        if fall_candidate_active and not alert_sent:
            if on_ground:
                if frame_index - ground_start_frame >= GROUND_FRAMES_REQUIRED:
                    alert_sent = True
                    send_alert_once(CAMERA_ID)
            else:
                fall_candidate_active = False
                ground_start_frame = None
                fall_detected = False
                pose_buffer.clear()

    # --------------------------------------
    # DISPLAY
    # --------------------------------------
    cv2.imshow("QuietSOS – Micro Buffer (Recorded Video)", display_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    frame_index += 1

    # --------------------------------------
    # VIDEO-TIME SYNC (FILE PACING)
    # --------------------------------------
    next_frame_target_time += frame_duration
    now = time.time()
    if now < next_frame_target_time:
        time.sleep(next_frame_target_time - now)
    else:
        next_frame_target_time = now

# ==========================================
# CLEANUP
# ==========================================

cap.release()
cv2.destroyAllWindows()
print("✅ QuietSOS recorded-video run finished successfully.")