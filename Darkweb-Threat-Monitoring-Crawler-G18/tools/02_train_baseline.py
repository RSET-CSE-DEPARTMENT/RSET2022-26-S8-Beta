import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score


# Load dataset
df = pd.read_csv("data/labeled_pages.csv")

X = df["clean_text"]
y = df["label"]

# Train-test split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# TF-IDF vectorizer
tfidf = TfidfVectorizer(
    max_features=5000,
    stop_words="english"
)

X_train_vec = tfidf.fit_transform(X_train)
X_test_vec = tfidf.transform(X_test)

# Logistic Regression
model = LogisticRegression(max_iter=1000)
model.fit(X_train_vec, y_train)

# Predictions
y_pred = model.predict(X_test_vec)

# Evaluation
print("Accuracy:", accuracy_score(y_test, y_pred))
print("\nClassification Report:")
print(classification_report(y_test, y_pred))

# Save errors
test_df = X_test.to_frame()
test_df["true"] = y_test.values
test_df["pred"] = y_pred

errors = test_df[test_df["true"] != test_df["pred"]]
errors.to_csv("data/baseline_errors.csv", index=False)

print("Saved baseline_errors.csv with", len(errors), "errors")


joblib.dump(model, "models/baseline_lr.pkl")
joblib.dump(tfidf, "models/tfidf.pkl")
