import streamlit as st
import pandas as pd
import plotly.graph_objects as plg


# =====================================================
# SMART LOGISTICS - FLEET SPACE OPTIMIZATION
# =====================================================

st.set_page_config(
    page_title="Smart Logistics",
    page_icon="🚚",
    layout="wide"
)

# =====================================================
# DATABASE ARMADA
# =====================================================

fleet = [
    {
        "name": "Van",
        "volume": 10,
        "payload": 1000,
        "cost": 500000
    },
    {
        "name": "Truck CDE",
        "volume": 30,
        "payload": 3000,
        "cost": 1000000
    },
    {
        "name": "Truck CDD",
        "volume": 45,
        "payload": 5000,
        "cost": 1500000
    },
    {
        "name": "Fuso",
        "volume": 60,
        "payload": 8000,
        "cost": 2200000
    }
]

# =====================================================
# HEADER
# =====================================================

st.title("🚚 Smart Logistics Fleet Space Optimization")
st.markdown("---")

# =====================================================
# INPUT BARANG
# =====================================================

st.subheader("📦 Input Barang")

jumlah_barang = st.number_input(
    "Jumlah Jenis Barang",
    min_value=1,
    max_value=20,
    value=3
)

data_barang = []

for i in range(jumlah_barang):

    st.markdown(f"### Barang {i+1}")

    col1, col2, col3 = st.columns(3)

    with col1:
        nama = st.text_input(
            f"Nama Barang {i+1}",
            value=f"Barang {i+1}"
        )

    with col2:
        qty = st.number_input(
            f"Qty {i+1}",
            min_value=1,
            value=10,
            key=f"qty{i}"
        )

    with col3:
        berat = st.number_input(
            f"Berat per Unit (kg) {i+1}",
            min_value=0.1,
            value=10.0,
            key=f"berat{i}"
        )

    c1, c2, c3 = st.columns(3)

    with c1:
        panjang = st.number_input(
            f"Panjang (m) {i+1}",
            min_value=0.1,
            value=1.0,
            key=f"p{i}"
        )

    with c2:
        lebar = st.number_input(
            f"Lebar (m) {i+1}",
            min_value=0.1,
            value=1.0,
            key=f"l{i}"
        )

    with c3:
        tinggi = st.number_input(
            f"Tinggi (m) {i+1}",
            min_value=0.1,
            value=1.0,
            key=f"t{i}"
        )

    volume = panjang * lebar * tinggi

    data_barang.append({
        "Nama": nama,
        "Qty": qty,
        "Volume/unit": volume,
        "Total Volume": volume * qty,
        "Berat/unit": berat,
        "Total Berat": berat * qty
    })

# =====================================================
# HITUNG TOTAL
# =====================================================

df = pd.DataFrame(data_barang)

total_volume = df["Total Volume"].sum()
total_berat = df["Total Berat"].sum()

# =====================================================
# REKOMENDASI ARMADA
# =====================================================

selected_truck = None

for truck in fleet:

    if (
        total_volume <= truck["volume"]
        and total_berat <= truck["payload"]
    ):
        selected_truck = truck
        break

# =====================================================
# HASIL
# =====================================================

st.markdown("---")
st.subheader("📊 Dashboard")

if selected_truck:

    utilization = (
        total_volume /
        selected_truck["volume"]
    ) * 100

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Volume Barang",
            f"{total_volume:.2f} m³"
        )

    with col2:
        st.metric(
            "Berat Barang",
            f"{total_berat:.0f} kg"
        )

    with col3:
        st.metric(
            "Truck",
            selected_truck["name"]
        )

    with col4:
        st.metric(
            "Utilization",
            f"{utilization:.1f}%"
        )

    # Gauge

    fig = plg.Figure(plg.Indicator(
        mode="gauge+number",
        value=utilization,
        title={"text": "Space Utilization (%)"},
        gauge={
            "axis": {"range": [0, 100]}
        }
    ))

    st.plotly_chart(
        fig,
        use_container_width=True
    )

    st.success(
        f"Rekomendasi Armada: {selected_truck['name']}"
    )

    st.info(
        f"Estimasi Biaya Operasional: Rp {selected_truck['cost']:,.0f}"
    )

else:

    st.error(
        "Tidak ada armada yang dapat menampung barang."
    )

# =====================================================
# TABEL BARANG
# =====================================================

st.markdown("---")
st.subheader("📦 Detail Barang")

st.dataframe(
    df,
    use_container_width=True
)

# =====================================================
# ANALISIS
# =====================================================

st.markdown("---")
st.subheader("📈 Executive Summary")

if selected_truck:

    sisa_volume = (
        selected_truck["volume"]
        - total_volume
    )

    sisa_berat = (
        selected_truck["payload"]
        - total_berat
    )

    st.write(
        f"""
        ### Ringkasan

        - Total Volume Barang : **{total_volume:.2f} m³**
        - Total Berat Barang : **{total_berat:.0f} kg**
        - Armada Terpilih : **{selected_truck['name']}**
        - Utilisasi Ruang : **{utilization:.2f}%**
        - Sisa Volume : **{sisa_volume:.2f} m³**
        - Sisa Payload : **{sisa_berat:.0f} kg**
        - Estimasi Biaya : **Rp {selected_truck['cost']:,.0f}**
        """
    )

st.markdown("---")
st.caption("Smart Logistics Fleet Space Optimization")