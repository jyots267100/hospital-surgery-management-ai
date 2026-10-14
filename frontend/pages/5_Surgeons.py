import datetime as dt

import pandas as pd
import streamlit as st
from utils.api_client import api_call, get

st.set_page_config(page_title="Surgeons - Hospital Surgery AI", page_icon="🩺", layout="wide")
st.title("🩺 Surgeons")

surgeons, err = api_call(get, "/api/v1/surgeons")
if err:
    st.error(err)
    st.stop()

st.dataframe(pd.DataFrame(surgeons), hide_index=True, use_container_width=True)

st.divider()
st.subheader("Surgeon schedule")

options = {f"{s['name']} ({s['surgeon_id']})": s["surgeon_id"] for s in surgeons}
col1, col2 = st.columns(2)
surgeon_label = col1.selectbox("Surgeon", options=list(options.keys()))
filter_date = col2.date_input("Date (optional)", value=None)

if st.button("Show schedule"):
    params = {}
    if filter_date:
        params["on_date"] = filter_date.isoformat()
    surgeries, err = api_call(get, f"/api/v1/surgeons/{options[surgeon_label]}/schedule", params=params)
    if err:
        st.error(err)
    elif surgeries:
        st.dataframe(pd.DataFrame(surgeries), hide_index=True, use_container_width=True)
    else:
        st.info("No surgeries found for this surgeon with the given filter.")
