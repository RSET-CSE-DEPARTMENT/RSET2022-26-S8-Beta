from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_SRC = "models/darkbert/checkpoint-378"
MODEL_DST = "models/darkbert-final"

model = AutoModelForSequenceClassification.from_pretrained(MODEL_SRC)
tokenizer = AutoTokenizer.from_pretrained("s2w-ai/DarkBERT")

model.save_pretrained(MODEL_DST)
tokenizer.save_pretrained(MODEL_DST)

print("Final DarkBERT saved to", MODEL_DST)
