import cv2
import numpy as np
import os
import time
from ultralytics import YOLO

# ------------------------------
# Utility functions
# ------------------------------
def sigmoid(x):
    return 1 / (1 + np.exp(-x))

def aspect_ratio_score(w, h):
    return sigmoid((w / h - 1.2) * 4)

# ------------------------------
# Setup
# ------------------------------
os.makedirs("abnormal_clips", exist_ok=True)

VIDEO_PATH = r"C:\fall dataset new\archive\Fall\Raw_Video\20240912_101331.mp4"   # 🔴 CHANGE THIS
cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    raise ValueError("❌ Cannot open video file")

model = YOLO("yolov8n.pt")
model.to("cuda:0")

# ------------------------------
# Single-person state
# ------------------------------
score = 0.0
writer = None
cooldown = 0
first_abnormal_saved = False

ABNORMAL_THRESHOLD = 0.5
COOLDOWN_FRAMES = 10
FIXED_SIZE = (224, 224)

# ------------------------------
# Main loop
# ------------------------------
while True:
    ret, frame = cap.read()
    if not ret:
        break

    results = model.predict(
        frame,
        device="cuda:0",
        imgsz=640,
        conf=0.25,
        classes=[0],
        verbose=False
    )[0]

    if len(results.boxes) > 0:
        boxes = results.boxes
        best_idx = boxes.conf.argmax().item()
        box = boxes[best_idx]

        x1, y1, x2, y2 = map(int, box.xyxy[0])
        w, h = x2 - x1, y2 - y1

        # EMA abnormal score
        score = 0.8 * score + 0.2 * aspect_ratio_score(w, h)
        abnormal = score > ABNORMAL_THRESHOLD

        # ------------------------------
        # Draw bounding box & label FIRST
        # ------------------------------
        color = (0, 0, 255) if abnormal else (0, 255, 0)
        label = "ABNORMAL" if abnormal else "NORMAL"

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            frame,
            f"{label} | Score: {score:.2f}",
            (x1, y1 - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2
        )

        # ------------------------------
        # Save FIRST abnormal full frame
        # (WITH bounding box)
        # ------------------------------
        if abnormal and not first_abnormal_saved:
            timestamp = int(time.time())
            frame_name = f"abnormal_clips/first_abnormal_frame_{timestamp}.jpg"
            cv2.imwrite(frame_name, frame)
            print(f"📸 Saved first abnormal full frame with bbox: {frame_name}")
            first_abnormal_saved = True

        # ------------------------------
        # Record abnormal cropped clip
        # ------------------------------
        if abnormal:
            cropped = frame[y1:y2, x1:x2]
            if cropped.size > 0:
                cropped_resized = cv2.resize(cropped, FIXED_SIZE)

                if writer is None:
                    clip_name = f"abnormal_clips/abnormal_clip_{timestamp}.mp4"
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    writer = cv2.VideoWriter(
                        clip_name, fourcc, 20.0, FIXED_SIZE
                    )
                    print(f"🎥 Started abnormal clip recording: {clip_name}")

                writer.write(cropped_resized)
                cooldown = COOLDOWN_FRAMES

        else:
            # Reset when normal again
            first_abnormal_saved = False

            if writer is not None:
                cooldown -= 1
                if cooldown <= 0:
                    writer.release()
                    writer = None
                    print("🛑 Stopped abnormal clip recording")

    cv2.imshow("QuietSOS – Stage I Prefilter", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# ------------------------------
# Cleanup
# ------------------------------
if writer is not None:
    writer.release()

cap.release()
cv2.destroyAllWindows()
print("✅ Processing finished.")
