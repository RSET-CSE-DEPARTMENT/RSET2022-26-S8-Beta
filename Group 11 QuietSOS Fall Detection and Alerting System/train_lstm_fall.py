
# FALL DETECTION USING LSTM FROM POSE CSV FILES

import os
import numpy as np
import pandas as pd
import tensorflow as tf

from sklearn.model_selection import train_test_split
from sklearn.utils import class_weight
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, BatchNormalization, Masking


# 1. CONFIGURATION

DATASET_DIR = "."

SEQUENCE_LENGTH = 30
STRIDE = 5

KEYPOINTS = [
    "Nose","Left Eye","Right Eye","Left Ear","Right Ear",
    "Left Shoulder","Right Shoulder","Left Elbow","Right Elbow",
    "Left Wrist","Right Wrist","Left Hip","Right Hip",
    "Left Knee","Right Knee","Left Ankle","Right Ankle"
]

FEATURES_PER_KEYPOINT = 3  # X, Y, Confidence
NUM_FEATURES = len(KEYPOINTS) * FEATURES_PER_KEYPOINT

MODEL_SAVE_PATH = "quiet_sos_lstm_fall_detector_v3.h5"

# 2. CSV → SEQUENCES

def csv_to_sequences(csv_path):
    df = pd.read_csv(csv_path)

    frames = sorted(df["Frame"].unique())
    all_frames = []

    for frame in frames:
        frame_data = df[df["Frame"] == frame]
        feature_vector = []

        for kp in KEYPOINTS:
            kp_row = frame_data[frame_data["Keypoint"] == kp]

            if len(kp_row) == 0:
                feature_vector.extend([0.0, 0.0, 0.0])
            else:
                feature_vector.extend([
                    kp_row["X"].values[0],
                    kp_row["Y"].values[0],
                    kp_row["Confidence"].values[0]
                ])

        all_frames.append(feature_vector)

    all_frames = np.array(all_frames, dtype=np.float32)

    sequences = []
    for i in range(0, len(all_frames) - SEQUENCE_LENGTH + 1, STRIDE):
        sequences.append(all_frames[i:i + SEQUENCE_LENGTH])

    return np.array(sequences, dtype=np.float32)

# 3. LOAD DATASET

X = []
y = []

class_folders = {
    "No_Fall": 0,
    "Fall": 1
}

print("\nLoading dataset...")

for class_name, label in class_folders.items():
    csv_dir = os.path.join(
        DATASET_DIR,
        class_name,
        "Keypoints_CSV"
    )

    if not os.path.exists(csv_dir):
        raise FileNotFoundError(f"Missing folder: {csv_dir}")

    for file in os.listdir(csv_dir):
        if file.endswith(".csv"):
            csv_path = os.path.join(csv_dir, file)
            print("Processing:", file)
            sequences = csv_to_sequences(csv_path)

            if len(sequences) == 0:
                continue

            X.extend(sequences)
            y.extend([label] * len(sequences))

X = np.array(X, dtype=np.float32)
y = np.array(y, dtype=np.int32)

print("Dataset loaded successfully")
print("X shape:", X.shape)
print("y shape:", y.shape)


# 4. TRAIN / VAL / TEST SPLIT


X_train, X_temp, y_train, y_temp = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

X_val, X_test, y_val, y_test = train_test_split(
    X_temp, y_temp,
    test_size=0.5,
    random_state=42,
    stratify=y_temp
)

class_weights = class_weight.compute_class_weight(
    class_weight="balanced",
    classes=np.unique(y_train),
    y=y_train
)

class_weights = {i: class_weights[i] for i in range(len(class_weights))}

print("Class weights:", class_weights)

# 5. MODEL


model = Sequential([
    Masking(mask_value=0.0, input_shape=(SEQUENCE_LENGTH, NUM_FEATURES)),

    LSTM(64, return_sequences=True),
    BatchNormalization(),
    Dropout(0.4),

    LSTM(32),
    Dropout(0.4),

    Dense(32, activation="relu"),
    Dropout(0.3),

    Dense(1, activation="sigmoid")
])

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss="binary_crossentropy",
    metrics=[
        "accuracy",
        tf.keras.metrics.Precision(name="precision"),
        tf.keras.metrics.Recall(name="recall")
    ]
)

model.summary()


# 6. TRAINING


early_stop = tf.keras.callbacks.EarlyStopping(
    monitor="val_loss",
    patience=8,
    restore_best_weights=True
)

print("\nStarting training...")

history = model.fit(
    X_train, y_train,
    validation_data=(X_val, y_val),
    epochs=80,
    batch_size=64,
    class_weight=class_weights,
    callbacks=[early_stop],
    verbose=1
)


# 7. EVALUATION


print("\nEvaluating on test set...")

loss, acc, prec, rec = model.evaluate(X_test, y_test, verbose=0)

print(f"Test Loss      : {loss:.4f}")
print(f"Test Accuracy  : {acc*100:.2f}%")
print(f"Test Precision : {prec:.4f}")
print(f"Test Recall    : {rec:.4f}")


# 8. SAVE MODEL


model.save(MODEL_SAVE_PATH)
print(f"\nModel saved as: {MODEL_SAVE_PATH}")
