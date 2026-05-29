import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from ortools.constraint_solver import pywrapcp
from ortools.constraint_solver import routing_enums_pb2
from math import radians, sin, cos, sqrt, atan2

st.set_page_config(page_title="VRP Maps Integration", layout="wide")

st.title("🚚 Vehicle Routing Problem (VRP) - Folium Integration")
st.write("Sistem sederhana optimasi rute menggunakan OR-Tools + Folium")

# =========================
# Fungsi Haversine
# =========================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1))
        * cos(radians(lat2))
        * sin(dlon / 2) ** 2
    )

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


# =========================
# Input Data
# =========================
st.sidebar.header("Input Data Lokasi")

uploaded_file = st.sidebar.file_uploader(
    "Upload File CSV",
    type=["csv"]
)

sample_data = pd.DataFrame({
    "nama": ["Depot", "Customer A", "Customer B", "Customer C"],
    "lat": [-6.200000, -6.210000, -6.220000, -6.215000],
    "lon": [106.816666, 106.826666, 106.836666, 106.845000]
})

if uploaded_file:
    df = pd.read_csv(uploaded_file)
else:
    st.info("Menggunakan sample data")
    df = sample_data

st.subheader("Data Lokasi")
st.dataframe(df)

# =========================
# Membuat Distance Matrix
# =========================
def create_distance_matrix(dataframe):
    locations = dataframe[["lat", "lon"]].values

    matrix = []

    for from_node in locations:
        row = []

        for to_node in locations:
            distance = haversine(
                from_node[0],
                from_node[1],
                to_node[0],
                to_node[1]
            )

            row.append(int(distance * 1000))

        matrix.append(row)

    return matrix


distance_matrix = create_distance_matrix(df)

# =========================
# OR-Tools Routing
# =========================
def solve_vrp(distance_matrix):

    manager = pywrapcp.RoutingIndexManager(
        len(distance_matrix),
        1,
        0
    )

    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)

        return distance_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(
        distance_callback
    )

    routing.SetArcCostEvaluatorOfAllVehicles(
        transit_callback_index
    )

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()

    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )

    solution = routing.SolveWithParameters(search_parameters)

    route = []

    if solution:
        index = routing.Start(0)

        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route.append(node_index)
            index = solution.Value(routing.NextVar(index))

        route.append(manager.IndexToNode(index))

    return route


route = solve_vrp(distance_matrix)

st.subheader("Hasil Rute Optimasi")
st.write(route)

# =========================
# Folium Map
# =========================
center_lat = df["lat"].mean()
center_lon = df["lon"].mean()

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=12
)

# Marker Lokasi
for idx, row in df.iterrows():

    if idx == 0:
        color = "red"
        icon = "home"
    else:
        color = "blue"
        icon = "shopping-cart"

    folium.Marker(
        location=[row["lat"], row["lon"]],
        popup=f"{row['nama']}",
        tooltip=row['nama'],
        icon=folium.Icon(color=color, icon=icon)
    ).add_to(m)

# =========================
# Routing Mengikuti Jalan
# =========================
import requests

route_coordinates = []

for i in range(len(route) - 1):

    start_node = route[i]
    end_node = route[i + 1]

    start_lat = df.iloc[start_node]["lat"]
    start_lon = df.iloc[start_node]["lon"]

    end_lat = df.iloc[end_node]["lat"]
    end_lon = df.iloc[end_node]["lon"]

    # API OSRM Gratis
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
        f"?overview=full&geometries=geojson"
    )

    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()

        coordinates = data['routes'][0]['geometry']['coordinates']

        # OSRM menggunakan format [lon, lat]
        road_path = [[coord[1], coord[0]] for coord in coordinates]

        folium.PolyLine(
            road_path,
            weight=5,
            opacity=0.8,
            color="blue"
        ).add_to(m)


st.subheader("Visualisasi Peta")

st_folium(m, width=1000, height=600)

# =========================
# Total Distance & Duration
# =========================
total_distance = 0
total_duration = 0

for i in range(len(route) - 1):

    start_node = route[i]
    end_node = route[i + 1]

    start_lat = df.iloc[start_node]["lat"]
    start_lon = df.iloc[start_node]["lon"]

    end_lat = df.iloc[end_node]["lat"]
    end_lon = df.iloc[end_node]["lon"]

    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
        f"?overview=false"
    )

    response = requests.get(url)

    if response.status_code == 200:

        data = response.json()

        distance = data['routes'][0]['distance']
        duration = data['routes'][0]['duration']

        total_distance += distance
        total_duration += duration

# Konversi
km_distance = total_distance / 1000
minute_duration = total_duration / 60
hour_duration = minute_duration / 60

st.subheader("Total Jarak")
st.write(f"{km_distance:.2f} KM")

st.subheader("Total Waktu Tempuh")

if hour_duration >= 1:
    st.write(f"{hour_duration:.2f} Jam")
else:
    st.write(f"{minute_duration:.2f} Menit")

# =========================
# Detail Perjalanan
# =========================
st.subheader("Detail Perjalanan")

travel_data = []

for i in range(len(route) - 1):

    start_node = route[i]
    end_node = route[i + 1]

    start_name = df.iloc[start_node]['nama']
    end_name = df.iloc[end_node]['nama']

    start_lat = df.iloc[start_node]['lat']
    start_lon = df.iloc[start_node]['lon']

    end_lat = df.iloc[end_node]['lat']
    end_lon = df.iloc[end_node]['lon']

    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
        f"?overview=false"
    )

    response = requests.get(url)

    if response.status_code == 200:

        data = response.json()

        distance = data['routes'][0]['distance'] / 1000
        duration = data['routes'][0]['duration'] / 60

        travel_data.append({
            "Dari": start_name,
            "Ke": end_name,
            "Jarak (KM)": round(distance, 2),
            "Waktu (Menit)": round(duration, 2)
        })

travel_df = pd.DataFrame(travel_data)

st.dataframe(travel_df)
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# =====================================
# CONFIG
# =====================================
st.set_page_config(
    page_title="Smart Logistics VRP",
    layout="wide",
    page_icon="🚚"
)

# =====================================
# CUSTOM CSS
# =====================================
st.markdown(
    """
    <style>
    .main {
        background-color: #f1f5f9;
    }

    .kpi-card {
        background: white;
        padding: 20px;
        border-radius: 20px;
        box-shadow: 0px 4px 12px rgba(0,0,0,0.08);
    }

    .title-text {
        font-size: 40px;
        font-weight: bold;
        color: white;
    }

    .subtitle-text {
        color: white;
        font-size: 18px;
    }

    .header-box {
        background: linear-gradient(90deg,#1d4ed8,#06b6d4);
        padding: 35px;
        border-radius: 25px;
        margin-bottom: 25px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# =====================================
# HEADER
# =====================================
st.markdown(
    """
    <div class="header-box">
        <div class="title-text">
            🚚 Smart Logistics VRP Dashboard
        </div>

        <div class="subtitle-text">
            Vehicle Routing Optimization System
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# =====================================
# SIDEBAR
# =====================================
st.sidebar.title("📌 Navigation")

menu = st.sidebar.radio(
    "Menu",
    [
        "Dashboard",
        "Routing Optimization",
        "Live Map",
        "Analytics",
        "Settings"
    ]
)

st.sidebar.markdown("---")

uploaded_file = st.sidebar.file_uploader(
    "Upload Customer Data",
    type=["csv", "xlsx"]
)

vehicle_count = st.sidebar.number_input(
    "Jumlah Kendaraan",
    min_value=1,
    value=3
)

optimize_button = st.sidebar.button("🚀 Optimize Route")

col1, col2, col3s, col4 = st.columns(4)

with col1:
    st.markdown(
        """
        <div class="kpi-card">
            <h4>🚚 Total Kendaraan</h4>
            <h1>12</h1>
            <p>Armada Aktif</p>
        </div>
        """,
        unsafe_allow_html=True
    )

with col2:
    st.markdown(
        """
        <div class="kpi-card">
            <h4>📍 Customer</h4>
            <h1>248</h1>
            <p>Titik Distribusi</p>
        </div>
        """,
        unsafe_allow_html=True
    )

with col3:
    st.markdown(
        """
        <div class="kpi-card">
            <h4>🛣️ Total Jarak</h4>
            <h1>1,248 KM</h1>
            <p>Estimasi Perjalanan</p>
        </div>
        """,
        unsafe_allow_html=True
    )

with col4:
    st.markdown(
        """
        <div class="kpi-card">
            <h4>⏱️ Waktu Tempuh</h4>
            <h1>32 Jam</h1>
            <p>Total Operasional</p>
        </div>
        """,
        unsafe_allow_html=True
    )

st.write("")

# =====================================
# MAIN LAYOUT
# =====================================
left_col, right_col = st.columns([2, 1])

# =====================================
# MAP SECTION
# =====================================
with left_col:

    st.subheader("🗺️ Live Distribution Map")

    # Default map
    m = folium.Map(
        location=[-6.200000, 106.816666],
        zoom_start=11
    )

    # Sample markers
    folium.Marker(
        [-6.200000, 106.816666],
        popup="Depot",
        icon=folium.Icon(color="red")
    ).add_to(m)

    folium.Marker(
        [-6.210000, 106.826666],
        popup="Customer A",
        icon=folium.Icon(color="blue")
    ).add_to(m)

    folium.Marker(
        [-6.220000, 106.836666],
        popup="Customer B",
        icon=folium.Icon(color="green")
    ).add_to(m)

    # Sample route
    route = [
        [-6.200000, 106.816666],
        [-6.210000, 106.826666],
        [-6.220000, 106.836666]
    ]

    folium.PolyLine(
        route,
        color="blue",
        weight=5
    ).add_to(m)

    st_folium(m, width=900, height=500)

# =====================================
# VEHICLE MONITORING
# =====================================
with right_col:

    st.subheader("🚚 Vehicle Monitoring")

    vehicle_data = pd.DataFrame({
        "Vehicle": ["Truck 01", "Truck 02", "Truck 03"],
        "Status": ["On Delivery", "Finished", "Waiting"],
        "ETA": ["14:30", "Done", "-"]
    })

    st.dataframe(vehicle_data, use_container_width=True)

    st.subheader("📈 Routing Analytics")

    st.progress(92)
    st.write("Efisiensi Rute: 92%")

    st.progress(81)
    st.write("Utilisasi Kendaraan: 81%")

    st.progress(96)
    st.write("Ketepatan Waktu: 96%")

# =====================================
# DETAIL TABLE
# =====================================
st.subheader("📋 Detail Perjalanan")

trip_data = pd.DataFrame({
    "Dari": ["Depot", "Customer A"],
    "Ke": ["Customer A", "Customer B"],
    "Jarak (KM)": [5.2, 3.1],
    "Waktu (Menit)": [12, 8]
})

st.dataframe(trip_data, use_container_width=True)

# =====================================
# FOOTER
# =====================================
st.markdown("---")

st.caption(
    "Smart Logistics Vehicle Routing System | OR-Tools + Folium + Streamlit"
)

# =====================================
# INSTALLATION
# =====================================
'''
INSTALL LIBRARY

pip install streamlit
pip install pandas
pip install folium
pip install streamlit-folium

JALANKAN PROGRAM

streamlit run app.py
'''
