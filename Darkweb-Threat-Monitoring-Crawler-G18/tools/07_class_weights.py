import pandas as pd
import numpy as np

df = pd.read_csv("data/bert_dataset.csv")

labels = df["label_id"].values
counts = np.bincount(labels)

weights = 1.0 / counts
weights = weights / weights.sum()

print("Class counts:", counts)
print("Class weights:", weights)
