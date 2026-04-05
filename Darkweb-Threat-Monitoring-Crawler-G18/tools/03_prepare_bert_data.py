import pandas as pd
from sklearn.preprocessing import LabelEncoder

df = pd.read_csv("data/labeled_pages.csv")

le = LabelEncoder()
df["label_id"] = le.fit_transform(df["label"])

df.to_csv("data/bert_dataset.csv", index=False)

print("Label mapping:")
for i, label in enumerate(le.classes_):
    print(i, "->", label)
