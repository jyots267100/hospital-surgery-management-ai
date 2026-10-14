import streamlit as st
from utils.api_client import api_call, post

st.set_page_config(page_title="AI Assistant - Hospital Surgery AI", page_icon="💬", layout="wide")
st.title("💬 AI Assistant")
st.caption(
    "Ask about today's surgeries, delays, surgeon schedules, OR availability, or "
    "hospital policy. State-changing requests (cancel, schedule, reschedule, status "
    "changes) will always ask you to confirm before anything is changed."
)

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []  # [{role, content}]
if "chat_history_payload" not in st.session_state:
    st.session_state.chat_history_payload = []  # what we send back to the API
if "pending_action" not in st.session_state:
    st.session_state.pending_action = None

with st.sidebar:
    st.subheader("Session")
    actor = st.text_input("Acting as (staff id)", value="staff_user")
    if st.button("Clear conversation"):
        st.session_state.chat_messages = []
        st.session_state.chat_history_payload = []
        st.session_state.pending_action = None
        st.rerun()

for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("citations"):
            st.caption(" · ".join(msg["citations"]))

if st.session_state.pending_action:
    st.warning("⚠️ Awaiting your confirmation for a write operation (see assistant's last message above).")

user_input = st.chat_input("Ask the assistant...")
if user_input:
    st.session_state.chat_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result, err = api_call(
                post, "/api/v1/chat",
                json={
                    "message": user_input,
                    "history": st.session_state.chat_history_payload,
                    "actor": actor or "staff_user",
                },
            )
        if err:
            st.error(err)
        else:
            st.markdown(result["response"])
            if result.get("citations"):
                st.caption(" · ".join(result["citations"]))
            st.session_state.chat_messages.append({
                "role": "assistant", "content": result["response"], "citations": result.get("citations", []),
            })
            st.session_state.chat_history_payload = [
                {"role": h["role"], "content": h["content"]} for h in result["history"]
            ]
            st.session_state.pending_action = result.get("pending_action")
            if result.get("confirmation_status") == "pending":
                st.info("This assistant reply is proposing a change. Reply to confirm or decline.")
