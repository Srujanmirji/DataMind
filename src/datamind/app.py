"""Streamlit Multimodal UI for DataMind.

Run: ``streamlit run src/datamind/app.py``

Features:
- Multimodal Input: Text, Audio (voice recordings), and Image (charts, screenshots)
- Live Snowflake Evidence: SQL queries, Query IDs, result tables, calculation claims
- Dataset selector: TPC-H Orders & UCI Wine Quality
"""

from __future__ import annotations

import os

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BACKEND_URL = os.environ.get("DATAMIND_BACKEND_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="DataMind — Talk to Your Data", page_icon="🧠", layout="wide")

# Custom styling for rich aesthetic
CSS_STYLES = """
<style>
.main-title { font-size: 2.2rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0.2rem; }
.subtitle { font-size: 1.05rem; color: #4B5563; margin-bottom: 1.5rem; }
.evidence-card {
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    padding: 16px;
    margin-top: 12px;
}
.query-tag {
    background-color: #DBEAFE;
    color: #1E40AF;
    padding: 4px 8px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 0.85rem;
}
.metric-badge {
    background-color: #ECFDF5;
    color: #065F46;
    padding: 4px 8px;
    border-radius: 4px;
    font-weight: 600;
}
</style>
"""
st.markdown(CSS_STYLES, unsafe_allow_html=True)

st.markdown('<div class="main-title">🧠 DataMind — Talk to Your Data</div>', unsafe_allow_html=True)
SUBTITLE_HTML = (
    '<div class="subtitle">'
    "Ask everyday questions in <b>Text</b>, <b>Voice (Audio)</b>, or with <b>Chart Images</b>"
    " — computed live in Snowflake with Gemma."
    "</div>"
)
st.markdown(SUBTITLE_HTML, unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("⚙️ Configuration")
    dataset_choice = st.selectbox(
        "Active Dataset",
        ["tpch_orders", "uci_wine_quality"],
        format_func=lambda x: (
            "TPC-H Orders (1.5M rows)" if x == "tpch_orders" else "UCI Wine Quality (6,497 samples)"
        ),
    )

    st.divider()
    st.markdown("### 🔌 Backend Status")
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=3)
        if resp.status_code == 200:
            info = resp.json()
            st.success(f"🟢 Connected ({info.get('model', 'Gemma')})")
        else:
            st.warning(f"🟡 Backend returned status {resp.status_code}")
    except Exception:
        st.error("🔴 Backend offline (`http://127.0.0.1:8000`)")

    st.caption("Powered by Google Gemma & Snowflake Warehouse")

# Multimodal Input Tabs
tab_text, tab_voice, tab_image = st.tabs(["💬 Text Question", "🎙️ Voice (Audio)", "🖼️ Image / Chart"])

question_text = ""
audio_file = None
image_file = None
submit_clicked = False

with tab_text:
    question_text = st.text_input(
        "Ask a plain-language question:",
        placeholder="e.g. Which five customer nations have the highest total order value?",
        key="text_question_input",
    )
    if st.button("Submit Question", type="primary", key="btn_text"):
        submit_clicked = True

with tab_voice:
    st.write("🎙️ **Record or Upload an Audio Question:**")
    voice_input = getattr(st, "audio_input", None)
    if voice_input is not None:
        audio_file = st.audio_input("Record your voice:")
    else:
        audio_file = st.file_uploader(
            "Upload audio (.wav, .mp3, .m4a):", type=["wav", "mp3", "m4a"], key="audio_upload"
        )
    if audio_file is not None:
        if st.button("Analyze Audio Question", type="primary", key="btn_audio"):
            submit_clicked = True

with tab_image:
    st.write("🖼️ **Upload a Chart or Screenshot to Analyze:**")
    image_file = st.file_uploader(
        "Upload image (.png, .jpg, .jpeg):", type=["png", "jpg", "jpeg", "webp"], key="img_upload"
    )
    if image_file is not None:
        st.image(image_file, caption="Uploaded image context", width=350)
        img_prompt = st.text_input(
            "Optional question for this image:",
            value="Analyze the metric shown in this visual data.",
        )
        if st.button("Submit Visual Query", type="primary", key="btn_image"):
            question_text = img_prompt
            submit_clicked = True

# Process and Render Results
if submit_clicked:
    with st.spinner("Processing with Gemma and executing in Snowflake..."):
        try:
            files_dict = {}
            data_dict = {"dataset_id": dataset_choice, "question": question_text or ""}

            if audio_file is not None:
                files_dict["audio"] = (
                    audio_file.name,
                    audio_file.getvalue(),
                    audio_file.type or "audio/wav",
                )
            if image_file is not None:
                files_dict["image"] = (
                    image_file.name,
                    image_file.getvalue(),
                    image_file.type or "image/png",
                )

            if files_dict:
                response = requests.post(
                    f"{BACKEND_URL}/questions/multimodal",
                    data=data_dict,
                    files=files_dict,
                    timeout=120,
                )
            else:
                response = requests.post(
                    f"{BACKEND_URL}/questions",
                    json={"question": question_text, "dataset_id": dataset_choice},
                    timeout=120,
                )

            if response.status_code == 200:
                result = response.json()
                status = result.get("status", "answered")

                if status == "answered":
                    st.success("### Answer")
                    st.write(result.get("answer", ""))

                    if result.get("explanation"):
                        with st.expander("📖 Explanation & Methodology", expanded=True):
                            st.write(result.get("explanation"))

                    # Claims & Grounding Evidence
                    claims = result.get("claims", [])
                    if claims:
                        with st.expander("🔍 Verified Grounding Claims", expanded=False):
                            for claim in claims:
                                metric_name = claim.get("metric", "Metric")
                                val = claim.get("value")
                                row_idx = claim.get("row_index", 0)
                                col_name = claim.get("column", "val")
                                st.markdown(
                                    f"• **{metric_name}**: `{val}` "
                                    f"(Lineage: row {row_idx}, column `{col_name}`)"
                                )

                    # Inspectable Snowflake Evidence
                    evidence = result.get("evidence", [])
                    if evidence:
                        st.subheader("❄️ Snowflake Execution Evidence")
                        for _idx, ev in enumerate(evidence, start=1):
                            query_id = ev.get("query_id", "N/A")
                            sql_text = ev.get("sql", "")
                            rows = ev.get("rows", [])
                            columns = ev.get("columns", [])

                            st.markdown(
                                f'<span class="query-tag">Snowflake Query ID: {query_id}</span>',
                                unsafe_allow_html=True,
                            )
                            st.code(sql_text, language="sql")

                            if rows and columns:
                                import pandas as pd

                                df = pd.DataFrame(rows, columns=columns)
                                st.dataframe(df, use_container_width=True)
                            elif rows:
                                st.write(rows)

                elif status == "needs_clarification":
                    st.warning("⚠️ **Clarification Needed:**")
                    st.write(
                        result.get("answer")
                        or result.get("explanation")
                        or "The question is ambiguous."
                    )

                elif status == "unsupported":
                    st.info("ℹ️ **Unsupported Query:**")
                    st.write(
                        result.get("answer")
                        or result.get("explanation")
                        or "Requested fields or data changes are not supported."
                    )

                elif status == "empty":
                    st.info("ℹ️ **No Data Found:**")
                    st.write(
                        result.get("answer")
                        or "The query executed successfully in Snowflake but returned 0 rows."
                    )

                else:
                    st.write(result)

            else:
                err_body = (
                    response.json()
                    if response.headers.get("content-type") == "application/json"
                    else {"message": response.text}
                )
                err_msg = err_body.get("error", {}).get(
                    "message", err_body.get("message", "Request failed")
                )
                st.error(f"Error ({response.status_code}): {err_msg}")

        except Exception as exc:
            st.error(f"Failed to communicate with backend: {exc}")
