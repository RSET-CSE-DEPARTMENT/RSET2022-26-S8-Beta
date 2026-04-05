from sqlalchemy import text
from services.ml.darkbert_infer import predict_text
from services.llm.intel_engine import analyze_darkweb_content


# -------------------------------------------------------
# Indicators
# -------------------------------------------------------
INDICATORS = [
    "leak",
    "database",
    "dump",
    "credentials",
    "password",
    "access for sale",
    "ransomware",
    "breach",
]


# -------------------------------------------------------
# Text Chunking (CRITICAL FIX)
# -------------------------------------------------------
def chunk_text(text, size=512):
    words = text.split()
    for i in range(0, len(words), size):
        yield " ".join(words[i:i+size])


# -------------------------------------------------------
# Snippet Extraction
# -------------------------------------------------------
def extract_snippet(text_data, keyword, window=220):

    idx = text_data.lower().find(keyword.lower())

    if idx == -1:
        return text_data[:window]

    start = max(0, idx - window)
    end = idx + window
    return text_data[start:end]


# -------------------------------------------------------
# Rule Detection
# -------------------------------------------------------
def detect_rules(clean_text):

    lower = clean_text.lower()
    return [ind for ind in INDICATORS if ind in lower]


# -------------------------------------------------------
# ML Prediction on Chunks
# -------------------------------------------------------
def ml_predict_page(clean_text):

    best_conf = 0
    best_label = None

    for chunk in chunk_text(clean_text):
        label, conf = predict_text(chunk)

        if conf > best_conf:
            best_conf = conf
            best_label = label

    return best_label, best_conf


# -------------------------------------------------------
# Hybrid Severity (Improved)
# -------------------------------------------------------
def compute_severity(rule_hits, ml_conf):

    if rule_hits and ml_conf > 0.75:
        return "CRITICAL"

    if rule_hits:
        return "HIGH"

    if ml_conf > 0.85:
        return "HIGH"

    if ml_conf > 0.65:
        return "MEDIUM"

    return "LOW"


# -------------------------------------------------------
# MAIN ENTRY
# -------------------------------------------------------
def analyze_page(engine, org_id, page_id, clean_text, org_name=None):

    print("HYBRID DETECTOR RUNNING")

    if not clean_text or len(clean_text) < 200:
        return

    # Optional org relevance boost
    if org_name and org_name.lower() not in clean_text.lower():
        print("Skipping — org not mentioned")
        return

    # Rules
    rule_hits = detect_rules(clean_text)

    # ML
    ml_label, ml_conf = ml_predict_page(clean_text)

    print("ML RESULT:", ml_label, ml_conf)

    severity = compute_severity(rule_hits, ml_conf)

    
    # Evidence
    if rule_hits:
     indicator = rule_hits[0]
     snippet = extract_snippet(clean_text, indicator)

    elif ml_conf > 0.5:
        indicator = f"ml-class-{ml_label}"
        snippet = clean_text[:400]

    else:
        return
    # Save
    try:

        if ml_label is None:
            ml_label = 0
            ml_conf = 0.0

        print("Saving threat →", indicator)

        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO threats (
                    org_id,
                    crawled_page_id,
                    indicator_type,
                    indicator,
                    severity,
                    evidence,
                    ml_label,
                    ml_confidence
                )
                VALUES (
                    :org_id,
                    :page_id,
                    'hybrid',
                    :indicator,
                    :severity,
                    :evidence,
                    :ml_label,
                    :ml_conf
                )
            """), {
                "org_id": org_id,
                "page_id": page_id,
                "indicator": indicator,
                "severity": severity,
                "evidence": snippet,
                "ml_label": ml_label,
                "ml_conf": ml_conf
            })

        print("Threat inserted successfully")

    except Exception as e:
        print("DB INSERT ERROR:", e)