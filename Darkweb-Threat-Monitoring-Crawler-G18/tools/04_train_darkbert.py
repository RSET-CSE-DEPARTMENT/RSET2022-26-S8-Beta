import os
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

import pandas as pd
import torch
import numpy as np
from sklearn.model_selection import train_test_split
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments,
    DataCollatorWithPadding
)
from torch.nn import CrossEntropyLoss

MODEL_NAME = "s2w-ai/DarkBERT"

# ===============================
# DATA
# ===============================
df = pd.read_csv("data/bert_dataset.csv")

labels = df["label_id"].values
class_counts = np.bincount(labels)

class_weights = len(labels) / (len(class_counts) * class_counts)
class_weights = torch.tensor(class_weights, dtype=torch.float)

print("Class counts:", class_counts)
print("Weights:", class_weights)

# ===============================
# SPLIT
# ===============================
X_train, X_test, y_train, y_test = train_test_split(
    df["clean_text"],
    df["label_id"],
    test_size=0.2,
    random_state=42,
    stratify=df["label_id"]
)

# ===============================
# TOKENIZER
# ===============================
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
data_collator = DataCollatorWithPadding(tokenizer)

def tokenize(texts):
    return tokenizer(texts.tolist(), truncation=True, max_length=512)

train_enc = tokenize(X_train)
test_enc = tokenize(X_test)

# ===============================
# DATASET
# ===============================
class DarkDataset(torch.utils.data.Dataset):

    def __init__(self, enc, labels):
        self.enc = enc
        self.labels = labels.tolist()

    def __getitem__(self, idx):
        item = {k: torch.tensor(v[idx]) for k,v in self.enc.items()}
        item["labels"] = torch.tensor(self.labels[idx])
        return item

    def __len__(self):
        return len(self.labels)

train_dataset = DarkDataset(train_enc, y_train)
test_dataset = DarkDataset(test_enc, y_test)

# ===============================
# MODEL
# ===============================
model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_NAME,
    num_labels=len(class_counts)
)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
class_weights = class_weights.to(device)

# ===============================
# CUSTOM TRAINER
# ===============================
class WeightedTrainer(Trainer):

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits

        loss_fct = CrossEntropyLoss(weight=class_weights)
        loss = loss_fct(logits, labels)

        return (loss, outputs) if return_outputs else loss


# ===============================
# TRAIN ARGS
# ===============================
args = TrainingArguments(
    output_dir="models/darkbert",
    num_train_epochs=6,
    per_device_train_batch_size=4,
    learning_rate=2e-5,
    weight_decay=0.01,
    warmup_steps=50,
    logging_steps=20,
    save_total_limit=2,
    report_to="none"
)

# ===============================
# TRAIN
# ===============================
trainer = WeightedTrainer(
    model=model,
    args=args,
    train_dataset=train_dataset,
    eval_dataset=test_dataset,
    data_collator=data_collator
)

trainer.train()
