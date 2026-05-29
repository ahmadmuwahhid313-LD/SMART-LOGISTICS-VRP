# =========================================================
# SMART LOGISTICS AI SYSTEM V6
# TRUE VRP + 3D BIN PACKING
# =========================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import folium 

from streamlit_folium import st_folium
ROUTE_COLORS = [
    "red",
    "blue",
    "green",
    "orange",
    "purple",
    "black"
]
from itertools import permutations
from math import radians, sin, cos, sqrt, atan2

from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="SMART LOGISTICS AI SYSTEM V6",
    layout="wide"
)

st.markdown("""
<div class='big-title'>
🚛 SMART LOGISTICS AI SYSTEM
</div>

<div class='sub-title'>
AI-Based Vehicle Routing + 3D Bin Packing Optimization
</div>
""", unsafe_allow_html=True)
# =========================================================
# MODERN UI DESIGN
# =========================================================

st.markdown("""
<style>

/* MAIN BACKGROUND */
.main {
    background-color: #0E1117;
    color: white;
}

/* TITLE */
.big-title {
    font-size: 42px;
    font-weight: 800;
    color: #00E5FF;
    text-align: center;
    margin-bottom: 0px;
}

.sub-title {
    font-size: 18px;
    color: #A0AEC0;
    text-align: center;
    margin-top: 0px;
    margin-bottom: 30px;
}

/* METRIC CARD */
.metric-card {
    background: linear-gradient(145deg, #1A1F2B, #111827);
    padding: 25px;
    border-radius: 20px;
    border: 1px solid #2D3748;
    box-shadow: 0 8px 20px rgba(0,0,0,0.3);
    text-align: center;
    transition: 0.3s;
}

.metric-card:hover {
    transform: translateY(-5px);
    border: 1px solid #00E5FF;
}

.metric-value {
    font-size: 32px;
    font-weight: bold;
    color: #00E5FF;
}

.metric-label {
    color: #CBD5E0;
    font-size: 14px;
}

/* SECTION TITLE */
.section-title {
    font-size: 28px;
    font-weight: bold;
    margin-top: 40px;
    margin-bottom: 20px;
    color: white;
}

/* SIDEBAR */
section[data-testid="stSidebar"] {
    background-color: #111827;
}

/* TABLE */
[data-testid="stDataFrame"] {
    border-radius: 15px;
    overflow: hidden;
}

/* BUTTON */
.stButton>button {
    background: linear-gradient(90deg, #00E5FF, #007CF0);
    color: white;
    border-radius: 12px;
    border: none;
    height: 45px;
    font-weight: bold;
}

</style>
""", unsafe_allow_html=True)

# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.markdown("""
<h2 style='color:#00E5FF'>
🚚 Truck Configuration
</h2>
""", unsafe_allow_html=True)

truck_length = st.sidebar.number_input(
    "Truck Length (cm)",
    value=600
)

truck_width = st.sidebar.number_input(
    "Truck Width (cm)",
    value=240
)

truck_height = st.sidebar.number_input(
    "Truck Height (cm)",
    value=260
)

max_trucks = st.sidebar.number_input(
    "Maximum Trucks",
    value=3
)

target_utilization = st.sidebar.slider(
    "Target Utilization (%)",
    70,
    100,
    95
)

# =========================================================
# DEPOT CONFIG
# =========================================================

st.sidebar.header("🏭 Depot")

depot_lat = st.sidebar.number_input(
    "Depot Latitude",
    value=-6.2615
)

depot_lon = st.sidebar.number_input(
    "Depot Longitude",
    value=107.1520
)

# =========================================================
# INPUT DATA
# =========================================================

st.header("📦 Goods Input")

default_data = pd.DataFrame({

    "Item": ["A", "B", "C", "D"],

    "Customer": [
        "Customer 1",
        "Customer 2",
        "Customer 3",
        "Customer 4"
    ],

  "Latitude": [
    -6.2088,   
    -6.4025,   
    -6.1702,   
    -6.3031    
],

"Longitude": [
    106.8456,
    106.7942,
    106.6403,
    107.0176
],

    "Length": [120, 100, 80, 60],

    "Width": [80, 70, 60, 50],

    "Height": [60, 50, 40, 30],

    "Weight": [100, 80, 50, 20],

    "Quantity": [2, 3, 4, 5],

    "Color": ["red", "blue", "green", "orange"]
})

df = st.data_editor(
    default_data,
    num_rows="dynamic",
    use_container_width=True
)

# =========================================================
# CREATE ITEMS
# =========================================================

items = []

for _, row in df.iterrows():

    for i in range(int(row["Quantity"])):

        items.append({

            "id": f"{row['Item']}_{i}",

            "name": row["Item"],

            "customer": row["Customer"],

            "latitude": row["Latitude"],

            "longitude": row["Longitude"],

            "length": row["Length"],

            "width": row["Width"],

            "height": row["Height"],

            "weight": row["Weight"],

            "color": row["Color"],

            "volume": (
                row["Length"] *
                row["Width"] *
                row["Height"]
            )
        })

# =========================================================
# SORT BIGGEST FIRST
# =========================================================

items = sorted(
    items,
    key=lambda x: x["volume"],
    reverse=True
)

# =========================================================
# ROTATION FUNCTION
# =========================================================

def get_rotations(item):

    dims = [

        item["length"],
        item["width"],
        item["height"]
    ]

    return list(
        set(permutations(dims))
    )

# =========================================================
# COLLISION CHECK
# =========================================================

def check_collision(box1, box2):

    return not (

        box1["x"] + box1["l"] <= box2["x"] or
        box1["x"] >= box2["x"] + box2["l"] or

        box1["y"] + box1["w"] <= box2["y"] or
        box1["y"] >= box2["y"] + box2["w"] or

        box1["z"] + box1["h"] <= box2["z"] or
        box1["z"] >= box2["z"] + box2["h"]
    )

# =========================================================
# DISTANCE FUNCTION
# =========================================================

def calculate_distance(
    lat1,
    lon1,
    lat2,
    lon2
):

    R = 6371

    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (

        sin(dlat / 2) ** 2

        +

        cos(radians(lat1))

        *

        cos(radians(lat2))

        *

        sin(dlon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a)
    )

    return R * c

# =========================================================
# DISTANCE MATRIX
# =========================================================

def create_distance_matrix(customers):

    locations = [

        (
            depot_lat,
            depot_lon
        )
    ]

    for c in customers:

        locations.append(
            (
                c["lat"],
                c["lon"]
            )
        )

    matrix = []

    for from_node in locations:

        row = []

        for to_node in locations:

            dist = calculate_distance(

                from_node[0],
                from_node[1],

                to_node[0],
                to_node[1]
            )

            row.append(
                int(dist * 1000)
            )

        matrix.append(row)

    return matrix

# =========================================================
# INITIALIZE TRUCKS
# =========================================================

truck_volume = (

    truck_length *
    truck_width *
    truck_height
)

trucks = []

for truck_id in range(max_trucks):

    trucks.append({

        "id": truck_id + 1,

        "items": [],

        "used_volume": 0,

        "total_weight": 0,

        "customers": [],

        "route": []
    })

unpacked = []

# =========================================================
# PACKING FUNCTION
# =========================================================

def try_pack_item(item, truck):

    best_fit = None

    best_score = float("inf")

    positions = [(0, 0, 0)]

    # =====================================================
    # EXTREME POINTS
    # =====================================================

    for existing in truck["items"]:

        positions.extend([

            (
                existing["x"] + existing["l"],
                existing["y"],
                existing["z"]
            ),

            (
                existing["x"],
                existing["y"] + existing["w"],
                existing["z"]
            ),

            (
                existing["x"],
                existing["y"],
                existing["z"] + existing["h"]
            )
        ])

    positions = list(set(positions))

    positions = sorted(
        positions,
        key=lambda p: (
            p[2],
            p[1],
            p[0]
        )
    )

    # =====================================================
    # TRY ALL ROTATIONS
    # =====================================================

    for rotation in get_rotations(item):

        l, w, h = rotation

        for pos in positions:

            x, y, z = pos

            # =================================================
            # BOUNDARY CHECK
            # =================================================

            if (
                x + l > truck_length or
                y + w > truck_width or
                z + h > truck_height
            ):
                continue

            new_box = {

                "id": item["id"],

                "name": item["name"],

                "customer": item["customer"],

                "latitude": item["latitude"],

                "longitude": item["longitude"],

                "x": x,
                "y": y,
                "z": z,

                "l": l,
                "w": w,
                "h": h,

                "weight": item["weight"],

                "volume": l * w * h,

                "color": item["color"]
            }

            # =================================================
            # COLLISION CHECK
            # =================================================

            collision = False

            for existing in truck["items"]:

                if check_collision(
                    new_box,
                    existing
                ):

                    collision = True
                    break

            if collision:
                continue

            # =================================================
            # COMPACT SCORE
            # =================================================

            remaining_x = (
                truck_length - (x + l)
            )

            remaining_y = (
                truck_width - (y + w)
            )

            remaining_z = (
                truck_height - (z + h)
            )

            gap_penalty = (

                remaining_x +
                remaining_y +
                remaining_z
            )

            score = (

                z * 100000 +

                gap_penalty * 100 +

                y * 1000 +

                x
            )

            # =================================================
            # SAVE BEST FIT
            # =================================================

            if score < best_score:

                best_score = score
                best_fit = new_box

    # =====================================================
    # PLACE BOX
    # =====================================================

    if best_fit:

        truck["items"].append(best_fit)

        truck["used_volume"] += (
            best_fit["volume"]
        )

        truck["total_weight"] += (
            best_fit["weight"]
        )

        return True

    return False

# =========================================================
# SEQUENTIAL FULL TRUCK OPTIMIZATION
# =========================================================

active_truck_index = 0

for item in items:

    packed = False

    while (
        active_truck_index < len(trucks)
    ):

        truck = trucks[active_truck_index]

        success = try_pack_item(
            item,
            truck
        )

        if success:

            packed = True

            utilization = (

                truck["used_volume"] /
                truck_volume

            ) * 100

            if utilization >= target_utilization:

                active_truck_index += 1

            break

        else:

            active_truck_index += 1

    if not packed:

        unpacked.append(item)

# =========================================================
# CUSTOMER GROUPING
# =========================================================

for truck in trucks:

    customer_map = {}

    for item in truck["items"]:

        customer_map[item["customer"]] = {

            "customer": item["customer"],

            "lat": item["latitude"],

            "lon": item["longitude"]
        }

    truck["customers"] = list(
        customer_map.values()
    )

# =========================================================
# TRUE VRP OPTIMIZATION
# =========================================================

for truck in trucks:

    if len(truck["customers"]) == 0:
        continue

    customers = truck["customers"]

    distance_matrix = create_distance_matrix(
        customers
    )

    manager = pywrapcp.RoutingIndexManager(

        len(distance_matrix),

        1,

        0
    )

    routing = pywrapcp.RoutingModel(
        manager
    )

    # =====================================================
    # DISTANCE CALLBACK
    # =====================================================

    def distance_callback(
        from_index,
        to_index
    ):

        from_node = manager.IndexToNode(
            from_index
        )

        to_node = manager.IndexToNode(
            to_index
        )

        return distance_matrix[
            from_node
        ][
            to_node
        ]

    transit_callback_index = (

        routing.RegisterTransitCallback(
            distance_callback
        )
    )

    routing.SetArcCostEvaluatorOfAllVehicles(
        transit_callback_index
    )

    # =====================================================
    # SEARCH PARAMETERS
    # =====================================================

    search_parameters = (
        pywrapcp.DefaultRoutingSearchParameters()
    )

    search_parameters.first_solution_strategy = (

        routing_enums_pb2.FirstSolutionStrategy
        .PATH_CHEAPEST_ARC
    )

    solution = routing.SolveWithParameters(
        search_parameters
    )

    route = []

    if solution:

        index = routing.Start(0)

        while not routing.IsEnd(index):

            node_index = manager.IndexToNode(index)

            if node_index != 0:

                route.append(
                    customers[node_index - 1]
                )

            index = solution.Value(
                routing.NextVar(index)
            )

    truck["route"] = route

# =========================================================
# DASHBOARD
# =========================================================

st.header("📊 Fleet Analytics")

total_used = sum(
    t["used_volume"]
    for t in trucks
)

fleet_utilization = (

    total_used /

    (
        truck_volume *
        max_trucks
    )

) * 100

used_trucks = len([

    t for t in trucks

    if len(t["items"]) > 0
])

c1, c2, c3, c4 = st.columns(4)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{used_trucks}</div>
        <div class="metric-label">Used Trucks</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{total_used:,.0f}</div>
        <div class="metric-label">Used Volume</div>
    </div>
    """, unsafe_allow_html=True)


with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-value">{len(unpacked)}</div>
        <div class="metric-label">Unpacked Items</div>
    </div>
    """, unsafe_allow_html=True)

# =========================================================
# VRP SUMMARY
# =========================================================

st.header("🗺 FLEET Route")

for idx, truck in enumerate(trucks):

    if len(truck["items"]) == 0:
        continue

    # =====================================================
    # ROUTE TEXT
    # =====================================================

    route_text = "🏭 Depot"

    total_distance = 0

    prev_lat = depot_lat
    prev_lon = depot_lon

    for customer in truck["route"]:

        route_text += (
            f" → {customer['customer']}"
        )

        dist = calculate_distance(
            prev_lat,
            prev_lon,
            customer["lat"],
            customer["lon"]
        )

        total_distance += dist

        prev_lat = customer["lat"]
        prev_lon = customer["lon"]

    # kembali ke depot
    total_distance += calculate_distance(
        prev_lat,
        prev_lon,
        depot_lat,
        depot_lon
    )

    st.markdown(f"""
<div style="
background:#111827;
padding:20px;
border-radius:15px;
margin-bottom:15px;
border-left:5px solid #00E5FF;
">

<h4 style='color:#00E5FF'>
🚚 Truck {truck['id']}
</h4>

<p style='color:white'>
{route_text}
</p>

<p style='color:#CBD5E0'>
📏 Total Distance: {total_distance:.2f} km
</p>

</div>
""", unsafe_allow_html=True)

# ==========================================
# ROUTE MAP
# ==========================================

route_points = []

# Depot
route_points.append([depot_lat, depot_lon])

for customer in truck["route"]:
    route_points.append([
        customer["lat"],
        customer["lon"]
    ])

# Kembali ke depot
route_points.append([depot_lat, depot_lon])

# Center map
center_lat = np.mean([p[0] for p in route_points])
center_lon = np.mean([p[1] for p in route_points])

m = folium.Map(
    location=[center_lat, center_lon],
    zoom_start=12,
    tiles="CartoDB Dark_Matter"
)

# ==========================================
# DEPOT MARKER
# ==========================================

folium.Marker(
    [depot_lat, depot_lon],
    popup="Depot",
    tooltip="Depot",
    icon=folium.Icon(
        color="red",
        icon="home",
        prefix="fa"
    )
).add_to(m)

# ==========================================
# CUSTOMER MARKERS
# ==========================================

for idx_customer, customer in enumerate(truck["route"], start=1):

    folium.Marker(
        [customer["lat"], customer["lon"]],
        popup=f"{idx_customer}. {customer['customer']}",
        tooltip=f"Stop {idx_customer}",
        icon=folium.Icon(
            color="blue",
            icon="truck",
            prefix="fa"
        )
    ).add_to(m)

# ==========================================
# ROUTE LINE
# ==========================================

folium.PolyLine(
    route_points,
    color="#00E5FF",
    weight=8,
    opacity=0.9,
    dash_array="10,10",
    tooltip=f"Truck {truck['id']} Route"
).add_to(m)

    # =====================================================
    # CREATE MAP
    # =====================================================

m = folium.Map(
    location=[depot_lat, depot_lon],
    )

# =========================================================
# 3D VISUALIZATION
# =========================================================

st.header("📦 3D Packing Visualization")

available_trucks = [

    t["id"]

    for t in trucks

    if len(t["items"]) > 0
]

if not available_trucks:

    st.warning("No packed items")

    st.stop()

selected_truck = st.selectbox(
    "Select Truck",
    available_trucks
)

truck = trucks[selected_truck - 1]

fig = go.Figure()

# =========================================================
# CONTAINER
# =========================================================

container_vertices = np.array([

    [0, 0, 0],

    [truck_length, 0, 0],

    [truck_length, truck_width, 0],

    [0, truck_width, 0],

    [0, 0, truck_height],

    [truck_length, 0, truck_height],

    [truck_length, truck_width, truck_height],

    [0, truck_width, truck_height]
])

fig.add_trace(go.Mesh3d(

    x=container_vertices[:,0],
    y=container_vertices[:,1],
    z=container_vertices[:,2],

    opacity=0.08,

    color="gray",

    showscale=False
))

# =========================================================
# SOLID BOX
# =========================================================

def create_box(item):

    x = item["x"]
    y = item["y"]
    z = item["z"]

    l = item["l"]
    w = item["w"]
    h = item["h"]

    color = item["color"]

    vertices = np.array([

        [x, y, z],
        [x+l, y, z],
        [x+l, y+w, z],
        [x, y+w, z],

        [x, y, z+h],
        [x+l, y, z+h],
        [x+l, y+w, z+h],
        [x, y+w, z+h]

    ])

    i = [

        0,0,
        4,4,

        0,0,
        1,1,

        2,2,
        3,3
    ]

    j = [

        1,2,
        5,6,

        1,5,
        2,6,

        3,7,
        0,4
    ]

    k = [

        2,3,
        6,7,

        5,4,
        6,5,

        7,6,
        4,7
    ]

    return go.Mesh3d(

        x=vertices[:,0],
        y=vertices[:,1],
        z=vertices[:,2],

        i=i,
        j=j,
        k=k,

        color=color,

        opacity=1.0,

        flatshading=True,

        lighting=dict(

            ambient=0.7,

            diffuse=1,

            roughness=0.2,

            specular=0.4
        ),

        lightposition=dict(

            x=1000,
            y=1000,
            z=1000
        ),

        showscale=False
    )
# =========================================================
# DRAW ITEMS
# =========================================================

for item in truck["items"]:

    fig.add_trace(
        create_box(item)
    )

    fig.add_trace(go.Scatter3d(

        x=[
            item["x"] + item["l"]/2
        ],

        y=[
            item["y"] + item["w"]/2
        ],

        z=[
            item["z"] + item["h"]/2
        ],

        mode='text',

        text=[item["name"]],

        showlegend=False
    ))

# =========================================================
# LAYOUT
# =========================================================

fig.update_layout(

    scene=dict(

        xaxis=dict(
            range=[0, truck_length],
            showgrid=True
        ),

        yaxis=dict(
            range=[0, truck_width],
            showgrid=True
        ),

        zaxis=dict(
            range=[0, truck_height],
            showgrid=True
        ),

        xaxis_title='Length',

        yaxis_title='Width',

        zaxis_title='Height',

        aspectmode='data'
    ),

    height=900
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# =========================================================
# PACKING DETAIL
# =========================================================

st.header("📋 Packing Detail")

table_data = []

for t in trucks:

    for item in t["items"]:

        table_data.append({

            "Truck": t["id"],

            "Customer": item["customer"],

            "Item": item["name"],

            "X": item["x"],
            "Y": item["y"],
            "Z": item["z"],

            "Length": item["l"],
            "Width": item["w"],
            "Height": item["h"],

            "Weight": item["weight"],

            "Volume": item["volume"]
        })

packing_df = pd.DataFrame(
    table_data
)

st.dataframe(
    packing_df,
    use_container_width=True
)

# =========================================================
# EXECUTIVE SUMMARY
# =========================================================

st.header("RINGKASAN")

for truck in trucks:

    if len(truck["items"]) == 0:
        continue

    util = (

        truck["used_volume"] /

        truck_volume

    ) * 100

    st.success(f"""

    🚚 Truck {truck['id']}

    PRESENTASE PENGGUNAAN RUANG:
    {util:.2f}%

    TOTAL VOLUME TERPAKAI:
    {truck['used_volume']:,.0f}

    TOTAL BERAT:
    {truck['total_weight']:,.0f} kg

    TOTAL ITEM:
    {len(truck['items'])}

    """)

if unpacked:

    st.error(f"""

    ❌ {len(unpacked)} items
    could not be packed.

    """)

# =========================================================
# FOOTER
# =========================================================

st.markdown("---")

st.caption(
    "SMART LOGISTICS SYSTEM"
)
