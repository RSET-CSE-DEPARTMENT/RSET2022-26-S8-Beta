import os
import sys
import subprocess
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import plotly.express as px
import tempfile
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

# Fix import path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.llm.report_generator import generate_org_report
from services.utils.pdf_report import generate_pdf

# =============================
# STREAMLIT CONFIG
# =============================
st.set_page_config(page_title="DW Threat Monitor", layout="wide")

# =============================
# SESSION STATE
# =============================
if "selected_page" not in st.session_state:
    st.session_state.selected_page = None

if "run_query" not in st.session_state:
    st.session_state.run_query = False

# =============================
# DATABASE
# =============================
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://dev:dev@localhost:5432/dwthreat"
)

engine = create_engine(DATABASE_URL, future=True)

# ==========================================================
# LABEL MAP FOR ML CLASSES
# ==========================================================
label_map = {
    0: "Benign",
    1: "Credential Leak",
    2: "Forum",
    3: "Marketplace",
    4: "Scam"
}

# ==========================================================
# DB HELPERS
# ==========================================================
def load_crawled(org, since_days, limit):

    q = """
    SELECT cp.id, cp.url, cp.status_code, cp.fetched_at,
           substring(cp.content_snippet,1,400) AS snippet
    FROM crawled_pages cp
    JOIN orgs o ON o.id = cp.org_id
    WHERE (:org='' OR o.name ILIKE :orglike)
      AND cp.fetched_at > :since
    ORDER BY cp.fetched_at DESC
    LIMIT :lim
    """

    params = {
        "org": org,
        "orglike": f"%{org}%",
        "since": datetime.utcnow() - timedelta(days=since_days),
        "lim": limit
    }

    return pd.read_sql(text(q), engine.connect(), params=params)


def load_threats(org, since_days, min_sev, limit):

    sev_rank = {"low":1,"medium":2,"high":3,"critical":4}

    q = """
    SELECT t.*, o.name AS org_name, cp.url
    FROM threats t
    JOIN orgs o ON o.id = t.org_id
    JOIN crawled_pages cp ON cp.id = t.crawled_page_id
    WHERE (:org='' OR o.name ILIKE :orglike)
      AND t.created_at > :since
    ORDER BY t.created_at DESC
    LIMIT :lim
    """

    df = pd.read_sql(
        text(q),
        engine.connect(),
        params={
            "org": org,
            "orglike": f"%{org}%",
            "since": datetime.utcnow() - timedelta(days=since_days),
            "lim": limit
        }
    )

    if not df.empty:
        df["severity"] = df["severity"].str.lower()
        df = df[df["severity"].map(sev_rank) >= sev_rank[min_sev]]

    return df

def load_full_page(pid):

    q = """
    SELECT url, clean_text, fetched_at
    FROM crawled_pages
    WHERE id=:pid
    """

    return pd.read_sql(text(q), engine.connect(), params={"pid": pid})


def get_pages_for_org(org_name):

    if not org_name:
        return []

    q = """
    SELECT cp.clean_text
    FROM crawled_pages cp
    JOIN orgs o ON o.id = cp.org_id
    WHERE o.name ILIKE :org
      AND cp.clean_text IS NOT NULL
    ORDER BY cp.id DESC
    LIMIT 40
    """

    with engine.begin() as conn:
        rows = conn.execute(text(q), {"org": f"%{org_name}%"}).fetchall()

    return [r[0] for r in rows]

# ==========================================================
# PAGE VIEW MODE
# ==========================================================
if st.session_state.selected_page is not None:

    page = load_full_page(st.session_state.selected_page)

    st.header("Crawled Page Text")

    if not page.empty:

        st.write("URL:", page.iloc[0]["url"])
        st.write("Fetched:", page.iloc[0]["fetched_at"])

        st.text_area(
            "Clean Extracted Text",
            page.iloc[0]["clean_text"],
            height=650
        )

    else:
        st.warning("Page not found")

    if st.button("⬅ Back to Dashboard"):
        st.session_state.selected_page = None
        st.rerun()

    st.stop()

# ==========================================================
# DASHBOARD
# ==========================================================
st.title("Dark-Web Threat Monitor — Dashboard")

# =============================
# SIDEBAR
# =============================
with st.sidebar:

    st.header("Search Filters")

    org = st.text_input("Organization", "")
    since_days = st.number_input("Days Back", 1, 365, 30)

    min_severity = st.selectbox(
        "Minimum Severity",
        ["low","medium","high","critical"]
    )

    max_rows = st.slider("Max Rows", 10, 2000, 200)

    if st.button("Refresh Crawled Data"):
        st.session_state.run_query = True

# =============================
# RUN SCAN
# =============================
st.header("Run Dark-Web Scan")

new_org = st.text_input("Organization to scan", "")

if st.button("Generate Seeds + Crawl") and new_org:

    with st.spinner("Generating seeds..."):
        subprocess.run(["python","-m","tools.seed_generator",new_org], check=False)

    seed_file = f"seeds/{new_org}.txt"

    if os.path.exists(seed_file):

        with st.spinner("Crawling via Tor..."):
            subprocess.run([
                "python","-m","services.crawler.crawler_tor",
                new_org,
                seed_file,
                "--rotate"
            ], check=False)

        st.success("Crawl Completed")

    else:
        st.error("Seed generation failed")

# =============================
# DISPLAY DATA
# =============================
severity_img = None
type_img = None

ml_indicator_map = {
    "ml-class-0": "Benign",
    "ml-class-1": "Credential Leak",
    "ml-class-2": "Forum",
    "ml-class-3": "Marketplace",
    "ml-class-4": "Scam"
}

if st.session_state.run_query:

    crawled = load_crawled(org, since_days, max_rows)
    threats = load_threats(org, since_days, min_severity, max_rows)

    col1,col2,col3,col4 = st.columns(4)

    col1.metric("Pages", len(crawled))
    col2.metric("Threats", len(threats))
    col3.metric("High", (threats.severity=="high").sum() if not threats.empty else 0)
    col4.metric("Critical", (threats.severity=="critical").sum() if not threats.empty else 0)

    # ==========================================================
    # ML CLASSIFICATION PIE CHART
    # ==========================================================
    if not threats.empty and "ml_label" in threats.columns:

        ml_counts = threats["ml_label"].value_counts().sort_index()
        ml_counts.index = ml_counts.index.map(label_map)

        # remove benign for demo clarity
        ml_counts = ml_counts.drop("Benign", errors="ignore")

        if not ml_counts.empty:

            fig = px.pie(
                values=ml_counts.values,
                names=ml_counts.index,
                title="ML Threat Classification Distribution"
            )

            st.plotly_chart(fig, use_container_width=True)
            # Save chart for PDF
            ml_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
            fig.write_image(ml_img)

    # ---------- severity graph ----------
    if not threats.empty:

        st.subheader("Threat Severity Distribution")

        fig,ax = plt.subplots()

        threats["severity"].value_counts().plot.bar(ax=ax)

        severity_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
        fig.savefig(severity_img)

        st.pyplot(fig)

        # ---------- threat type ----------
        st.subheader("Threat Type Distribution")

        fig2, ax2 = plt.subplots()

        # Replace ML indicator names
        indicator_series = threats["indicator"].replace(ml_indicator_map)

        counts = indicator_series.value_counts()

        # Remove benign entries if desired
        counts = counts.drop("Benign", errors="ignore")

        # Keep top indicators only for readability
        counts = counts.head(6)

        import numpy as np
        colors = plt.cm.tab20(np.linspace(0,1,len(counts)))

        counts.plot.pie(
            autopct="%1.0f%%",
            ax=ax2,
            colors=colors
        )

        ax2.set_ylabel("")

        type_img = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name
        fig2.savefig(type_img, bbox_inches="tight", dpi=300)

        st.pyplot(fig2)
    # ---------- suspicious links ----------
    st.subheader("Most Suspicious Links")

    if not threats.empty:

        top = threats.sort_values(by="severity", ascending=False).head(10)

        for _,r in top.iterrows():

            st.markdown(f"**{r['severity'].upper()}** — {r['indicator']}")

            st.code(r.get("url","no url"))

    st.subheader("Crawled Pages")

    st.dataframe(crawled, use_container_width=True)

else:
    st.info("Enter org and click Refresh Crawled Data")

# ==========================================================
# AI REPORT
# ==========================================================
st.markdown("---")
st.header("AI Threat Intelligence Report")

if st.button("Generate Threat Intelligence Report"):

    if not org:
        st.warning("Enter organization in sidebar first")

    else:

        with st.spinner("Generating AI threat report..."):

            texts = get_pages_for_org(org)

            if not texts:

                st.error("No crawled data found for this org")

            else:

                report = generate_org_report(org, texts)

                st.subheader("Generated Intelligence Report")
                st.write(report)

                pdf_path = generate_pdf(report,severity_chart=severity_img,type_chart=type_img,ml_chart=ml_img)

                with open(pdf_path, "rb") as f:

                    st.download_button(
                        label="Download Full Threat Report (PDF)",
                        data=f,
                        file_name="darkweb_threat_report.pdf",
                        mime="application/pdf"
                    )