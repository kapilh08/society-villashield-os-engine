import streamlit as st
import requests
import pandas as pd

API_URL = "http://web:8000/api/v1"

st.set_page_config(page_title="VillaShield OS Terminal", layout="wide")

# --- Initialize Global Framework Session Memory safely without external packages ---
if "token" not in st.session_state:
    st.session_state.token = None
if "role" not in st.session_state:
    st.session_state.role = None
if "username" not in st.session_state:
    st.session_state.username = None

st.title("🛡️ VillaShield OS")
st.caption("Custom Villa Society Access Control & Infrastructure Dashboard")
st.divider()

# ==================== AUTH SYSTEM PORTAL ====================
if not st.session_state.token:
    st.write("### 🔐 Secure Terminal Gate Access")
    username = st.text_input("Username Identifier")
    password = st.text_input("Password String", type="password")
    
    if st.button("Authenticate Session Pipeline", use_container_width=True):
        res = requests.post(f"{API_URL}/auth/login", json={
            "username": username, "password": password, "role": "GUARD"
        })
        if res.status_code == 200:
            token_data = res.json()
            
            st.session_state.token = token_data["access_token"]
            st.session_state.username = username
            
            if "admin" in username.lower():
                st.session_state.role = "ADMIN"
            elif "guard" in username.lower():
                st.session_state.role = "GUARD"
            else:
                st.session_state.role = "RESIDENT"
            st.rerun()
        else:
            st.error("Invalid database system credential pair provided.")

# ==================== LOGGED IN SYSTEM STATES ====================
else:
    st.sidebar.subheader("🔒 Session Profile Tracker")
    st.sidebar.write(f"Identity: **{st.session_state.username}**")
    st.sidebar.write(f"Access Level: `{st.session_state.role}`")
    if st.sidebar.button("Terminate Session (Logout)", use_container_width=True):
        st.session_state.token = None
        st.session_state.role = None
        st.session_state.username = None
        st.rerun()

    headers = {"Authorization": f"Bearer {st.session_state.token}"}

    # ==================== ADMIN ANALYSIS DASHBOARD ====================
    if st.session_state.role == "ADMIN":
        st.write("## 📊 Executive Committee Command Tower")
        st.write("Real-time society perimeter metrics and traffic audit trails.")
        
        res = requests.get(f"{API_URL}/admin/metrics", headers=headers)
        if res.status_code == 200:
            metrics = res.json()
            cards = metrics["cards"]
            
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("Total Perimeter Crossings", cards["total_visitors"])
            m_col2.metric("Approved Entries", cards["approved"], delta="Authorized")
            m_col3.metric("Turned Away (Denied)", cards["denied"], delta="- Risk Blocked", delta_color="inverse")
            m_col4.metric("Domestic Staff Inside", cards["active_staff"], delta="Active Operations")
            st.divider()

            st.write("### 📈 Peak Perimeter Load Times (Hourly Traffic Density)")
            hourly_map = metrics["hourly_distribution"]
            
            if not hourly_map:
                hourly_map = {"08:00": 12, "10:00": 45, "12:00": 30, "14:00": 55, "17:00": 80, "20:00": 25}
            
            chart_df = pd.DataFrame(list(hourly_map.items()), columns=["Hour of Day", "Traffic Volume Logs"])
            st.bar_chart(chart_df.set_index("Hour of Day"), color="#2C5282")
        else:
            st.error("Unable to parse telemetry parameters from database pipeline controller.")

    # ==================== GUARD ENTRANCE LOGISTICS GATE ====================
    elif st.session_state.role == "GUARD":
        st.write("## 🔏 Guard Gate Control Terminal")
        tab1, tab2 = st.tabs(["Visitor Management System", "Staff Punch Engine"])
        
        with tab1:
            villa_id = st.number_input("Target Villa User ID", min_value=1, step=1)
            v_name = st.text_input("Visitor Full Name")
            v_phone = st.text_input("Contact Mobile String")
            v_vehicle = st.text_input("Vehicle Plate Details")
            v_purpose = st.selectbox("Action Purpose", ["Delivery", "Guest", "Cab", "Maintenance"])
            
            if st.button("Transmit Approval Request to Villa"):
                payload = {"villa_id": int(villa_id), "visitor_name": v_name, "phone_number": v_phone, "vehicle_number": v_vehicle if v_vehicle else None, "purpose": v_purpose}
                if requests.post(f"{API_URL}/visitors/register", json=payload, headers=headers).status_code == 201:
                    st.success("Notification broadcasted successfully!")

        with tab2:
            staff_pin = st.text_input("Scan Card / Input Badge PIN", type="password")
            if st.button("Punch Clock In/Out"):
                res = requests.post(f"{API_URL}/staff/clock-io", json={"passcode": staff_pin})
                if res.status_code == 200:
                    st.success(f"SUCCESS: {res.json()['staff_name']} registered.")

    # ==================== RESIDENT PERMISSION LAYER ====================
    elif st.session_state.role == "RESIDENT":
        st.write("## 🏡 Resident Authorization Panel")
        log_id_to_act = st.number_input("Enter Pending Visitor Log ID to Action", min_value=1, step=1)
        r_col1, r_col2 = st.columns(2)
        with r_col1:
            if st.button("👍 APPROVE ENTRY", use_container_width=True):
                if requests.patch(f"{API_URL}/visitors/{log_id_to_act}/action", json={"status": "APPROVED"}, headers=headers).status_code == 200:
                    st.success("Access Granted.")
        with r_col2:
            if st.button("👎 DENY ACCESS", use_container_width=True):
                if requests.patch(f"{API_URL}/visitors/{log_id_to_act}/action", json={"status": "DENIED"}, headers=headers).status_code == 200:
                    st.warning("Access Denied.")
