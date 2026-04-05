import pandas as pd
import torch
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_PATH = "models/darkbert/checkpoint-378"

# Load data
df = pd.read_csv("data/bert_dataset.csv")

label_map = {
    0: "benign",
    1: "credential_leak",
    2: "forum",
    3: "marketplace",
    4: "scam"
}

X_train, X_test, y_train, y_test = train_test_split(
    df["clean_text"],
    df["label_id"],
    test_size=0.2,
    random_state=42,
    stratify=df["label_id"]
)

# Load model + tokenizer
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
model.eval()

# Tokenize test set
enc = tokenizer(
    X_test.tolist(),
    padding=True,
    truncation=True,
    max_length=512,
    return_tensors="pt"
)

with torch.no_grad():
    outputs = model(**enc)
    preds = torch.argmax(outputs.logits, dim=1).numpy()



print("Accuracy:", accuracy_score(y_test, preds))
print("\nClassification Report:")
print(classification_report(y_test, preds))
