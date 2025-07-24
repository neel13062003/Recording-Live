import streamlit as st
import mysql.connector
import pandas as pd
import datetime

# --------------------- CONFIG ---------------------
st.set_page_config(page_title="📞 Agent Disposition Viewer", layout="wide")

db_config = {
    'host': '103.180.186.249',
    'user': 'qrt',
    'password': 'sHMNG||111@0#',
    'database': 'crm_call_master'
}

def get_phone_number_with_email_id(email):
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("SELECT phone, Name FROM employee_master WHERE email = %s", (email,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        st.error(f"DB Error: {e}")
        return None

# --------------------- MAIN ---------------------
try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)

    st.title("📊 Agent Disposition Dashboard")

    with st.sidebar:
        st.header("🧭 Filters")
        default_from = datetime.date.today() - datetime.timedelta(days=1)
        default_to = datetime.date.today()
        from_date, to_date = st.date_input("📅 Select Date Range", [default_from, default_to])

    if isinstance(from_date, list):
        from_date, to_date = from_date

    if from_date > to_date:
        st.error("⚠️ 'From Date' must be before 'To Date'")
        st.stop()

    query_dispo = """
        SELECT q_id, lead_id, agent_name, disposition_name, dispo_date_time
        FROM disposition_master
        WHERE DATE(dispo_date_time) BETWEEN %s AND %s
    """
    cursor.execute(query_dispo, (from_date, to_date))
    dispo_df = pd.DataFrame(cursor.fetchall())

    if dispo_df.empty:
        st.warning("⚠️ No disposition data found.")
        st.stop()

    agents = sorted(dispo_df['agent_name'].dropna().unique().tolist())
    selected_agent = st.selectbox("👤 Select Agent", ["All"] + agents)

    agent_data = dispo_df if selected_agent == "All" else dispo_df[dispo_df['agent_name'] == selected_agent]

    st.markdown("### 🗂️ Dispositions Summary")
    dispo_counts = (
        agent_data.groupby("disposition_name")
        .agg(count=("q_id", "count"))
        .reset_index()
        .sort_values("count", ascending=False)
    )

    col1, col2 = st.columns(2)
    col1.metric("📈 Total Entries", len(agent_data))
    col2.metric("🗃️ Unique Dispositions", len(dispo_counts))

    st.dataframe(dispo_counts, use_container_width=True)

    selected_dispo = st.selectbox("🎯 Select a Disposition", dispo_counts["disposition_name"].tolist())

    st.markdown("---")
    st.subheader(f"📞 Call Logs for: **{selected_dispo}**")

    selected_qids = agent_data[agent_data['disposition_name'] == selected_dispo]['q_id'].tolist()
    if not selected_qids:
        st.info("No matching call logs.")
        st.stop()

    # Avoid SQL injection - use placeholder formatting
    placeholders = ','.join(['%s'] * len(selected_qids))
    query_calls = f"""
        SELECT 
            call_id, caller_number, destination_number, 
            total_duration, ans_duration, call_type, call_status, lead_id,
            q_id, client_number, disposition_name, recording, dispo_date_time
        FROM crm_call_details
        WHERE q_id IN ({placeholders})
        ORDER BY dispo_date_time DESC
    """
    cursor.execute(query_calls, selected_qids)
    call_logs = pd.DataFrame(cursor.fetchall())

    if call_logs.empty:
        st.warning("⚠️ No call logs found.")
        st.stop()

    st.markdown("### 📞 Call Logs")

    # --- Dropdown for Selecting Call Recording ---
    call_options = [
        f"{row['call_id']} — {row['caller_number']} → {row['destination_number']} ({row['dispo_date_time']})"
        for idx, row in call_logs.iterrows()
    ]
    call_id_map = {opt: idx for opt, idx in zip(call_options, call_logs.index)}

    selected_call_display = st.selectbox(
        "🎧 Select a Call to Play Recording:",
        ["Select..."] + call_options
    )

    if selected_call_display != "Select...":
        selected_index = call_id_map[selected_call_display]
        selected_row = call_logs.iloc[selected_index]
        recording_url = selected_row["recording"]
        st.markdown(f"### 🎧 Playing Call ID: `{selected_row['call_id']}`")
        if recording_url:
            st.audio(recording_url, format="audio/mp3")
        else:
            st.warning("⚠️ No recording available.")
    else:
        st.info("Select a call from the dropdown above to play its recording.")

    # Show the tabular log data as a reference
    st.dataframe(call_logs, use_container_width=True)

    cursor.close()
    conn.close()

except Exception as e:
    st.error(f"❌ Error: {e}")
