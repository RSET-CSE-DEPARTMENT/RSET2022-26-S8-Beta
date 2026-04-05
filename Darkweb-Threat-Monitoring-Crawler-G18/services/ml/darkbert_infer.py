import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_PATH = "models/darkbert-final"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
model.to(device)
model.eval()


# ---------------------------------------------------
# Safe prediction function
# ---------------------------------------------------
def predict_text(text):

    if not text or len(text) < 30:
        return None, 0.0

    # limit size for speed
    text = text[:1500]

    enc = tokenizer(
        text,
        truncation=True,
        padding=True,
        max_length=512,
        return_tensors="pt"
    )

    enc = {k: v.to(device) for k, v in enc.items()}

    with torch.no_grad():
        logits = model(**enc).logits

    probs = torch.softmax(logits, dim=1)
    conf, label = torch.max(probs, dim=1)

    return int(label.item()), float(conf.item())
