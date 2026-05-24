import streamlit as st

st.set_page_config(
    page_title="SMART LOGISTIC AI",
    layout="wide"
)

st.title("🚚 SMART LOGISTIC AI SYSTEM")

st.markdown("### Vehicle Routing Problem + AI + Machine Learning")

st.sidebar.title("Navigation")

menu = st.sidebar.selectbox(
    "Select Menu",
    [
        "Dashboard",
        "VRP Optimization",
        "Traffic Prediction",
        "Map Visualization",
        "Analytics"
    ]
)

if menu == "Dashboard":
    st.subheader("Dashboard")

    col1, col2, col3 = st.columns(3)

    col1.metric("Vehicles", "5")
    col2.metric("Customers", "20")
    col3.metric("Total Distance", "120 KM")

elif menu == "VRP Optimization":
    st.subheader("Vehicle Routing Optimization")

elif menu == "Traffic Prediction":
    st.subheader("AI Traffic Prediction")

elif menu == "Map Visualization":
    st.subheader("Map Visualization")

elif menu == "Analytics":
    st.subheader("Logistic Analytics")