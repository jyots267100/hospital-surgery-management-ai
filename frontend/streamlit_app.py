import streamlit as st
from utils.api_client import check_api_health

st.set_page_config(
    page_title="Hospital Surgery Management AI Agent",
    page_icon="🏥",
    layout="wide",
)

st.title("🏥 Hospital Surgery Management AI Agent")
st.caption(
    "Internal hospital operations console -- surgery scheduling, operating room "
    "and surgeon oversight, hospital policy search, and an AI assistant. "
    "All patient data and policies shown are synthetic, for demonstration only."
)

api_ok = check_api_health()
if api_ok:
    st.success("Connected to backend API.")
else:
    st.error(
        "Cannot reach the backend API. Start it with "
        "`uvicorn app.main:app --reload` and refresh this page."
    )

st.divider()
st.subheader("Navigate")

col1, col2, col3 = st.columns(3)
with col1:
    st.page_link("pages/1_Dashboard.py", label="📊 Dashboard", icon="📊")
    st.page_link("pages/2_AI_Assistant.py", label="💬 AI Assistant", icon="💬")
    st.page_link("pages/3_Surgery_Management.py", label="🗓️ Surgery Management", icon="🗓️")
with col2:
    st.page_link("pages/4_Operating_Rooms.py", label="🚪 Operating Rooms", icon="🚪")
    st.page_link("pages/5_Surgeons.py", label="🩺 Surgeons", icon="🩺")
with col3:
    st.page_link("pages/6_Policy_Search.py", label="📄 Policy Search", icon="📄")
    st.page_link("pages/7_Audit_History.py", label="🧾 Audit History", icon="🧾")

st.divider()
st.caption(
    "Portfolio project -- see README.md and docs/ for architecture, agent workflow, "
    "RAG pipeline, security guardrails, and production-scaling notes."
)
