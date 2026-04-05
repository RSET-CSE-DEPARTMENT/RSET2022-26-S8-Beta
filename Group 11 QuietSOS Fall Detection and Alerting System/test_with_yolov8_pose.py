import cv2
import numpy as np
import tensorflow as tf
from ultralytics import YOLO
from collections import deque

# ============================================================
# CONFIGURATION
# ============================================================

VIDEO_PATH = r"C:\Users\91807\Downloads\GokulJef3.mp4"
MODEL_PATH = "quiet_sos_lstm_fall_detector.h5"

SEQUENCE_LENGTH = 30
NUM_KEYPOINTS = 17
FEATURES_PER_KEYPOINT = 3
NUM_FEATURES = NUM_KEYPOINTS * FEATURES_PER_KEYPOINT

FALL_THRESHOLD = 0.75
GROUND_TIME_SECONDS = 15
GROUND_Y_RATIO = 0.65

# ============================================================
# LOAD MODELS
# ============================================================

pose_model = YOLO("yolov8n-pose.pt")
lstm_model = tf.keras.models.load_model(MODEL_PATH)

# ============================================================
# VIDEO SETUP
# ============================================================

cap = cv2.VideoCapture(VIDEO_PATH)
assert cap.isOpened(), "❌ Cannot open video file"

fps = cap.get(cv2.CAP_PROP_FPS)
GROUND_FRAMES_REQUIRED = int(GROUND_TIME_SECONDS * fps)

pose_buffer = deque(maxlen=SEQUENCE_LENGTH)
frame_index = 0

# ============================================================
# STATE VARIABLES
# ============================================================

fall_candidate_active = False
ground_start_frame = None
alert_sent = False   # ✅ single source of truth

# ============================================================
# PROCESS VIDEO
# ============================================================

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    h, w, _ = frame.shape
    results = pose_model(frame, verbose=False)

    fall_prob = None
    fall_detected = False
    on_ground = False

    # --------------------------------------------------------
    # POSE EXTRACTION
    # --------------------------------------------------------
    if len(results[0].keypoints) > 0:
        kps = results[0].keypoints.xy[0].cpu().numpy()
        confs = results[0].keypoints.conf[0].cpu().numpy()

        feature_vector = []
        for i in range(NUM_KEYPOINTS):
            feature_vector.extend([kps[i][0], kps[i][1], confs[i]])

        pose_buffer.append(feature_vector)

        if len(pose_buffer) == SEQUENCE_LENGTH:
            sequence = np.array(pose_buffer, dtype=np.float32)
            sequence = sequence.reshape(1, SEQUENCE_LENGTH, NUM_FEATURES)
            fall_prob = lstm_model.predict(sequence, verbose=0)[0][0]
            fall_detected = fall_prob > FALL_THRESHOLD

        mean_hip_y = (kps[11][1] + kps[12][1]) / 2
        on_ground = mean_hip_y > GROUND_Y_RATIO * h

    else:
        pose_buffer.clear()

    # ========================================================
    # FALL CONFIRMATION LOGIC
    # ========================================================

    if fall_detected and not fall_candidate_active and not alert_sent:
        fall_candidate_active = True
        ground_start_frame = None

    if fall_candidate_active and not alert_sent:
        if on_ground:
            if ground_start_frame is None:
                ground_start_frame = frame_index
            elif frame_index - ground_start_frame >= GROUND_FRAMES_REQUIRED:
                alert_sent = True   # ✅ LOCK STATE
        else:
            fall_candidate_active = False
            ground_start_frame = None

    # ========================================================
    # DRAW UI
    # ========================================================

    x = w - 380
    y = 40

    # 🔴 AFTER ALERT → SHOW ONLY ALERT
    if alert_sent:
        cv2.putText(frame, "ALERT SENT : FALL CONFIRMED",
                    (x - 40, y + 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, (0, 0, 255), 3)

    # 🟢 BEFORE ALERT → FULL UI
    else:
        if fall_prob is not None:
            if fall_prob < 0.40:
                prob_color = (0, 255, 0)
                prob_state = "Normal"
            elif fall_prob < FALL_THRESHOLD:
                prob_color = (0, 255, 255)
                prob_state = "Warning"
            else:
                prob_color = (0, 0, 255)
                prob_state = "High Risk"

            cv2.putText(frame, f"Fall Prob     : {fall_prob:.2f}",
                        (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.75, prob_color, 2)
            y += 30

            cv2.putText(frame, f"Fall Status   : {prob_state}",
                        (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, prob_color, 2)
            y += 30

        if fall_candidate_active:
            if ground_start_frame is not None:
                seconds = (frame_index - ground_start_frame) / fps
                ground_text = f"On Ground ({seconds:.1f}s)"
                ground_color = (0, 0, 255)
            else:
                ground_text = "Ground Check Started"
                ground_color = (0, 255, 255)
        else:
            ground_text = "Standing / Moving"
            ground_color = (0, 255, 0)

        cv2.putText(frame, f"Ground Status : {ground_text}",
                    (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, ground_color, 2)
        y += 30

        if fall_candidate_active:
            cv2.putText(frame, "System State : Verifying...",
                        (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (0, 255, 255), 2)
        else:
            cv2.putText(frame, "System State : Monitoring",
                        (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (0, 255, 0), 2)

    # ========================================================
    # DISPLAY
    # ========================================================

    cv2.imshow("QuietSOS – Fall Detection Validation", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

    frame_index += 1

cap.release()
cv2.destroyAllWindows()
print("✅ Finished")
