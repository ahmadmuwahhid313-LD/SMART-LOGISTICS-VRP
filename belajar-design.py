import streamlit as st
st.markdown(
    "<h1 style='text-align: center: color:red;'>SMART LOGISTICS SYSTEM</h1>",
    unsafe_allow_html=True
)
st.markdown("<h2 style='text-align: center; color:blue;'>ini adalah header</h2>", unsafe_allow_html=True)
st.markdown("<h3>ini adalah sub header</h3>", unsafe_allow_html=True)
st.metric("data kendaraan", "1000", "100%")
st.sidebar.selectbox("pilih jenis kendaraan", ["mobil", "Motor", "sepeda"], key="jenis_kendaraan")
st.sidebar.slider("pilih jumlah kendaraan", 0, 1000, 500, key="jumlah_kendaraan")
                     


