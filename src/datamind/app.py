"""Streamlit UI. Run: ``streamlit run src/datamind/app.py``.

Layout target: question box -> answer -> expandable "How this was answered"
(explanation, assumptions) -> "Evidence" (executed SQL, Snowflake query ID,
result table, row count, truncation note) -> model/backend used.
"""

from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from datamind.config import available_datasets, load_dataset

load_dotenv()

st.set_page_config(page_title="DataMind", layout="wide")
st.title("DataMind")

dataset_name = st.sidebar.selectbox("Dataset", available_datasets())
dataset = load_dataset(dataset_name)
st.caption(dataset.display_name)

question = st.chat_input("Ask a question about the data")
if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        # TODO: build DataMindAgent once (st.cache_resource), call agent.ask(question, history),
        #       and render AgentAnswer: answer, explanation, assumptions, queries[*].result.
        st.warning("Agent not implemented yet — see src/datamind/agent.py.")
