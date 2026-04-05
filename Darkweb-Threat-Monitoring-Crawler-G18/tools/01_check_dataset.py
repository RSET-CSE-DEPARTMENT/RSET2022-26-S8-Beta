import pandas as pd

df = pd.read_csv("data/labeled_pages.csv")

print("Shape:", df.shape)
print("\nLabel distribution:")
print(df["label"].value_counts())

print("\nConfidence stats:")
print(df["confidence"].describe())

print("\nMissing values:")
print(df.isnull().sum())
