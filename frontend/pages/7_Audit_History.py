import pandas as pd
import streamlit as st
from utils.api_client import api_call, get

st.set_page_config(page_title="Audit History - Hospital Surgery AI", page_icon="🧾", layout="wide")
st.title("🧾 Audit History")
st.caption("Immutable event history for a surgery -- created, rescheduled, delayed, status changes, cancellations.")

surgery_id = st.text_input("Surgery ID", placeholder="e.g. S1004")
if st.button("Load history") and surgery_id:
    events, err = api_call(get, f"/api/v1/surgeries/{surgery_id}/events")
    if err:
        st.error(err)
    elif events:
        st.dataframe(
            pd.DataFrame(events)[
                ["timestamp", "event_type", "description", "actor", "previous_value", "new_value"]
            ],
            hide_index=True, use_container_width=True,
        )
    else:
        st.info("No events recorded for this surgery yet.")
