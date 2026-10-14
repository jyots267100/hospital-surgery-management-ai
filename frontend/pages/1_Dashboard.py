import pandas as pd
import streamlit as st
from utils.api_client import api_call, get

st.set_page_config(page_title="Dashboard - Hospital Surgery AI", page_icon="📊", layout="wide")
st.title("📊 Operations Dashboard")

summary, err = api_call(get, "/api/v1/dashboard/summary")
if err:
    st.error(err)
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total surgeries", summary["total_surgeries"])
col2.metric("Today's surgeries", summary["todays_surgery_count"])
col3.metric("Avg. delay (min)", summary["average_delay_minutes"])
col4.metric("OR utilization", f"{summary['operating_room_utilization_pct']}%")

st.divider()
left, right = st.columns([1, 1])

with left:
    st.subheader("Status distribution")
    status_df = pd.DataFrame(
        {"status": list(summary["status_breakdown"].keys()), "count": list(summary["status_breakdown"].values())}
    ).set_index("status")
    st.bar_chart(status_df)

with right:
    st.subheader("Today's surgeries")
    todays, err = api_call(get, "/api/v1/surgeries", params={"today_only": True})
    if err:
        st.error(err)
    elif todays:
        df = pd.DataFrame(todays)[
            ["surgery_id", "patient_name", "surgery_type", "surgeon_name", "operating_room",
             "scheduled_time", "status", "priority"]
        ]
        st.dataframe(df, hide_index=True, use_container_width=True)
    else:
        st.info("No surgeries scheduled for today.")

st.divider()
st.subheader("Delayed surgeries")
delayed, err = api_call(get, "/api/v1/surgeries/delayed")
if err:
    st.error(err)
elif delayed:
    df = pd.DataFrame(delayed)[
        ["surgery_id", "surgery_type", "surgeon_name", "operating_room",
         "scheduled_time", "delay_minutes", "delay_reason", "status"]
    ]
    st.dataframe(df, hide_index=True, use_container_width=True)
else:
    st.info("No delayed surgeries right now.")
