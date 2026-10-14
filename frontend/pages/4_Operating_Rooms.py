import datetime as dt

import pandas as pd
import streamlit as st
from utils.api_client import api_call, get

st.set_page_config(page_title="Operating Rooms - Hospital Surgery AI", page_icon="🚪", layout="wide")
st.title("🚪 Operating Rooms")

rooms, err = api_call(get, "/api/v1/operating-rooms")
if err:
    st.error(err)
    st.stop()

st.dataframe(pd.DataFrame(rooms), hide_index=True, use_container_width=True)

st.divider()
st.subheader("Check availability")

room_options = {f"{r['room_id']} - {r['name']}": r["room_id"] for r in rooms}
col1, col2, col3, col4 = st.columns(4)
room_label = col1.selectbox("Room", options=["All rooms"] + list(room_options.keys()))
on_date = col2.date_input("Date", value=dt.date.today())
window_start = col3.time_input("Window start", value=dt.time(9, 0))
window_end = col4.time_input("Window end", value=dt.time(17, 0))

if st.button("Check availability"):
    if room_label == "All rooms":
        results = []
        for label, room_id in room_options.items():
            result, err = api_call(
                get, f"/api/v1/operating-rooms/{room_id}/availability",
                params={"on_date": on_date.isoformat(), "window_start": window_start.isoformat(),
                        "window_end": window_end.isoformat()},
            )
            if err:
                st.error(err)
                break
            results.append(result)
    else:
        room_id = room_options[room_label]
        result, err = api_call(
            get, f"/api/v1/operating-rooms/{room_id}/availability",
            params={"on_date": on_date.isoformat(), "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat()},
        )
        results = [result] if result else []
        if err:
            st.error(err)

    for r in results:
        if r["is_available"]:
            st.success(f"{r['room_id']}: available for the full window.")
        else:
            st.warning(f"{r['room_id']}: NOT available -- conflicting surgeries below.")
            st.dataframe(pd.DataFrame(r["conflicting_surgeries"]), hide_index=True, use_container_width=True)
