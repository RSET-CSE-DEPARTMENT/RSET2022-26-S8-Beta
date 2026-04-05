import csv
import json
import subprocess
from pathlib import Path

INPUT = Path("data/darkweb_pages_frozen.csv")
OUTPUT = Path("data/labeled_pages.csv")

LABELS = [
    "credential_leak",
    "marketplace",
    "forum",
    "scam",
    "benign",
]

def call_llm(text: str):
    prompt = f"""
You are a cybersecurity analyst.

Choose EXACTLY ONE label from:
{", ".join(LABELS)}

Rules:
- Exposed usernames/passwords → credential_leak
- Products/services for sale → marketplace
- Discussions, threads, replies → forum
- Phishing, impersonation, fake services → scam
- Otherwise → benign

Text:
\"\"\"{text[:3500]}\"\"\"

Respond ONLY in valid JSON:
{{"label": "<label>", "confidence": 0.0}}
"""
    result = subprocess.run(
        ["ollama", "run", "llama3", prompt],
        capture_output=True,
        text=True,
    )

    # Robust JSON extraction
    try:
        start = result.stdout.find("{")
        end = result.stdout.rfind("}") + 1
        return json.loads(result.stdout[start:end])
    except Exception:
        return {"label": "benign", "confidence": 0.5}


def main():
    with INPUT.open(newline="", encoding="utf-8") as fin, \
         OUTPUT.open("w", newline="", encoding="utf-8") as fout:

        reader = csv.DictReader(fin)
        writer = csv.writer(fout)
        writer.writerow(["page_id", "label", "confidence", "clean_text"])

        for row in reader:
            text = row["clean_text"].strip()
            if not text:
                continue

            out = call_llm(text)

            writer.writerow([
                row["page_id"],
                out["label"],
                out["confidence"],
                text,
            ])

            print(f"Labeled page {row['page_id']} → {out['label']} ({out['confidence']})")

    print("\n[SUCCESS] Labeled dataset written to:", OUTPUT)


if __name__ == "__main__":
    main()
