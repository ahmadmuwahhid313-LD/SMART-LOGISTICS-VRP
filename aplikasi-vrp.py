import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from py3dbp import Packer, Bin, Item
import math
import itertools

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Smart Logistics AI - 3D Packing + CVRP",
    layout="wide",
    page_icon="🚚"
)

st.title("🚚 Smart Logistics AI")
st.markdown("**Integrasi 3D Bin Packing + Capacitated Vehicle Routing Problem (Opsi B)**")
st.markdown("Setiap kali VRP meng-assign pelanggan ke truck, 3D Bin Packing langsung mengecek apakah barang fisik muat.")
st.markdown("---")

MAX_CUSTOMERS = 10  # Batas performa

# ============================================================
# HELPER - HAVERSINE
# ============================================================
def haversine(coord1, coord2):
    R = 6371
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def build_distance_matrix(locations):
    n = len(locations)
    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                dist[i][j] = haversine(locations[i], locations[j])
    return dist

def route_distance(route, dist_matrix):
    if not route:
        return 0.0
    d = dist_matrix[0][route[0]]
    for i in range(len(route) - 1):
        d += dist_matrix[route[i]][route[i+1]]
    d += dist_matrix[route[-1]][0]
    return d

# ============================================================
# HELPER - 3D BIN PACKING CHECK (INTEGRASI PENUH)
# Dipanggil setiap kali VRP mencoba assign pelanggan ke truck
# ============================================================
def check_3d_feasibility(truck_cfg, assigned_customers, item_catalog):
    """
    Cek apakah kumpulan pelanggan (assigned_customers) secara FISIK muat
    dalam truck menggunakan 3D Bin Packing.
    Mengembalikan (feasible: bool, packer result, used_volume, utilization%)
    """
    packer = Packer()
    packer.add_bin(Bin(
        truck_cfg["name"],
        truck_cfg["width"],
        truck_cfg["height"],
        truck_cfg["depth"],
        truck_cfg["max_weight"]
    ))

    item_count = 0
    for cust in assigned_customers:
        cust_items = item_catalog.get(cust["id"], [])
        for item in cust_items:
            for q in range(int(item["qty"])):
                packer.add_item(Item(
                    f'{cust["id"]}_{item["name"]}_{q}',
                    item["width"],
                    item["height"],
                    item["depth"],
                    item["weight"]
                ))
                item_count += 1

    if item_count == 0:
        return True, None, 0.0, 0.0

    # Kompatibel semua versi py3dbp
    import inspect
    _params = inspect.signature(Packer.pack).parameters
    _kwargs = {"bigger_first": True}
    if "distribute_items"      in _params: _kwargs["distribute_items"]      = False
    if "fix_point"             in _params: _kwargs["fix_point"]             = True
    if "check_stable"          in _params: _kwargs["check_stable"]          = True
    if "support_surface_ratio" in _params: _kwargs["support_surface_ratio"] = 0.75
    if "number_of_decimals"    in _params: _kwargs["number_of_decimals"]    = 0
    packer.pack(**_kwargs)

    truck_bin  = packer.bins[0]
    fitted     = truck_bin.items
    unfitted   = truck_bin.unfitted_items
    truck_vol  = truck_cfg["width"] * truck_cfg["height"] * truck_cfg["depth"]
    used_vol    = float(sum(float(i.width) * float(i.height) * float(i.depth) for i in fitted))
    utilization = (used_vol / truck_vol) * 100 if truck_vol > 0 else 0.0

    feasible = len(unfitted) == 0
    return feasible, truck_bin, used_vol, utilization

# ============================================================
# HELPER - 2-OPT (OPTIMASI RUTE)
# ============================================================
def two_opt(route, dist_matrix, max_iterations=100):
    if len(route) < 4:
        return route
    best      = route[:]
    best_dist = route_distance(best, dist_matrix)
    improved  = True
    iteration = 0

    while improved and iteration < max_iterations:
        improved  = False
        iteration += 1
        for i in range(len(best) - 1):
            for j in range(i + 2, len(best)):
                fp = [0] + best + [0]
                a, b = fp[i], fp[i+1]
                c, d = fp[j], fp[j+1]
                old_cost = dist_matrix[a][b] + dist_matrix[c][d]
                new_cost = dist_matrix[a][c] + dist_matrix[b][d]
                if new_cost < old_cost - 1e-10:
                    best[i+1:j+1] = best[i+1:j+1][::-1]
                    best_dist     = best_dist - old_cost + new_cost
                    improved      = True
    return best

# ============================================================
# CORE ALGORITHM - INTEGRATED CVRP + 3D BIN PACKING (OPSI B)
# ============================================================
def solve_integrated(customers, item_catalog, truck_cfg, use_2opt=True):
    """
    Nearest Neighbor CVRP dimana setiap assignment dicek oleh 3D Bin Packing.
    Jika barang pelanggan tidak muat secara fisik, pelanggan dilewati dan
    dimasukkan ke truck berikutnya.
    """
    depot      = customers[0]  # index 0 = depot
    unvisited  = set(range(1, len(customers)))
    routes     = []
    packing_results = []

    all_coords = [(c["lat"], c["lon"]) for c in customers]
    dist_matrix = build_distance_matrix(all_coords)

    while unvisited:
        route           = []
        current         = 0
        assigned_custs  = []

        while unvisited:
            # Cari kandidat terdekat
            candidates = list(unvisited)
            if not candidates:
                break

            # Urutkan berdasarkan jarak dari posisi saat ini
            sorted_cands = sorted(candidates, key=lambda c: dist_matrix[current][c])

            assigned = False
            for nearest in sorted_cands:
                # ── INTEGRASI PENUH: cek 3D fisik sebelum assign ──
                trial_custs = assigned_custs + [customers[nearest]]
                feasible, _, _, _ = check_3d_feasibility(truck_cfg, trial_custs, item_catalog)

                if feasible:
                    route.append(nearest)
                    assigned_custs.append(customers[nearest])
                    unvisited.remove(nearest)
                    current  = nearest
                    assigned = True
                    break  # lanjut ke iterasi berikutnya

            if not assigned:
                # Tidak ada kandidat yang muat secara 3D → tutup route ini
                break

        if route:
            # Optimasi rute dengan 2-opt
            if use_2opt and len(route) > 2:
                route = two_opt(route, dist_matrix)

            # Jalankan sekali lagi packing final untuk visualisasi
            _, truck_bin, used_vol, utilization = check_3d_feasibility(
                truck_cfg, assigned_custs, item_catalog
            )
            routes.append({
                "route"       : route,
                "customers"   : assigned_custs,
                "truck_bin"   : truck_bin,
                "used_vol"    : used_vol,
                "utilization" : utilization,
                "distance"    : route_distance(route, dist_matrix),
            })
            packing_results.append(truck_bin)

    return routes, dist_matrix

# ============================================================
# SESSION STATE
# ============================================================
defaults = {
    "customers"  : [],
    "item_catalog": {},   # {customer_id: [{name, width, height, depth, weight, qty}]}
    "solved"     : False,
    "results"    : None,
    "dist_matrix": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

COLORS = ["red","blue","green","purple","orange","darkred","darkblue","darkgreen","cadetblue","pink"]
PLOTLY_COLORS = ["#e74c3c","#3498db","#2ecc71","#9b59b6","#e67e22",
                 "#c0392b","#2980b9","#27ae60","#8e44ad","#d35400"]

# ============================================================
# STEP 1 — KONFIGURASI TRUCK
# ============================================================
st.header("🚛 Step 1: Konfigurasi Truck")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Dimensi Truck (cm)")
    truck_name       = st.text_input("Nama Truck", value="Truck A")
    truck_width      = st.number_input("Lebar (cm)",  min_value=1, value=240)
    truck_height     = st.number_input("Tinggi (cm)", min_value=1, value=240)
    truck_depth      = st.number_input("Panjang (cm)",min_value=1, value=600)
    truck_max_weight = st.number_input("Max Berat (kg)", min_value=1, value=10000)

with col2:
    st.subheader("Info Volume Truck")
    truck_vol = truck_width * truck_height * truck_depth
    st.metric("Volume Total Truck", f"{truck_vol:,.0f} cm³")
    st.metric("Max Berat", f"{truck_max_weight:,} kg")
    st.info(
        "Setiap truck dalam sistem ini memiliki dimensi yang sama. "
        "Jumlah truck menyesuaikan kebutuhan secara otomatis."
    )

truck_cfg = {
    "name"      : truck_name,
    "width"     : truck_width,
    "height"    : truck_height,
    "depth"     : truck_depth,
    "max_weight": truck_max_weight,
}

# ============================================================
# STEP 2 — INPUT DEPOT & PELANGGAN
# ============================================================
st.markdown("---")
st.header(f"📍 Step 2: Input Depot & Pelanggan (maks. {MAX_CUSTOMERS} pelanggan)")

# Depot
st.subheader("Depot (Gudang)")
c1, c2, c3 = st.columns(3)
depot_name = c1.text_input("Nama Depot", value="Depot Utama")
depot_lat  = c2.number_input("Latitude Depot",  value=-6.2088, format="%.6f")
depot_lon  = c3.number_input("Longitude Depot", value=106.8456, format="%.6f")

st.markdown("---")

# Tambah pelanggan
n_custs = len(st.session_state.customers)
st.subheader(f"Tambah Pelanggan ({n_custs}/{MAX_CUSTOMERS})")

if n_custs >= MAX_CUSTOMERS:
    st.warning(f"🚫 Batas maksimal {MAX_CUSTOMERS} pelanggan sudah tercapai.")
else:
    with st.form("form_pelanggan", clear_on_submit=True):
        cc1, cc2, cc3 = st.columns(3)
        cust_name = cc1.text_input("Nama Pelanggan")
        cust_lat  = cc2.number_input("Latitude", value=-6.2000, format="%.6f")
        cust_lon  = cc3.number_input("Longitude", value=106.8400, format="%.6f")

        st.markdown("**Barang untuk pelanggan ini:**")
        ic1, ic2, ic3, ic4, ic5, ic6 = st.columns(6)
        item_name   = ic1.text_input("Nama Barang", value="Box A")
        item_width  = ic2.number_input("Lebar (cm)", min_value=1, value=50)
        item_height = ic3.number_input("Tinggi (cm)", min_value=1, value=40)
        item_depth  = ic4.number_input("Panjang (cm)", min_value=1, value=70)
        item_weight = ic5.number_input("Berat (kg)", min_value=0.1, value=5.0, format="%.1f")
        item_qty    = ic6.number_input("Qty", min_value=1, value=3)

        if st.form_submit_button("➕ Tambah Pelanggan") and cust_name:
            cust_id = f"C{len(st.session_state.customers)+1:02d}"
            st.session_state.customers.append({
                "id"  : cust_id,
                "name": cust_name,
                "lat" : cust_lat,
                "lon" : cust_lon,
            })
            st.session_state.item_catalog[cust_id] = [{
                "name"  : item_name,
                "width" : item_width,
                "height": item_height,
                "depth" : item_depth,
                "weight": item_weight,
                "qty"   : item_qty,
            }]
            st.session_state.solved = False
            st.success(f"✅ Pelanggan '{cust_name}' ditambahkan dengan {item_qty} unit {item_name}.")

# Contoh data
def load_sample():
    st.session_state.customers = [
        {"id":"C01","name":"Toko A - Sudirman",     "lat":-6.2076,"lon":106.8227},
        {"id":"C02","name":"Toko B - Kemang",        "lat":-6.2607,"lon":106.8136},
        {"id":"C03","name":"Toko C - Kelapa Gading", "lat":-6.1586,"lon":106.9054},
        {"id":"C04","name":"Toko D - Tangerang",     "lat":-6.1784,"lon":106.6319},
        {"id":"C05","name":"Toko E - Bekasi",        "lat":-6.2349,"lon":106.9896},
    ]
    st.session_state.item_catalog = {
        "C01": [{"name":"Box A","width":50,"height":40,"depth":70,"weight":5.0,"qty":3}],
        "C02": [{"name":"Box B","width":60,"height":50,"depth":80,"weight":8.0,"qty":2}],
        "C03": [{"name":"Box C","width":40,"height":30,"depth":60,"weight":3.0,"qty":5}],
        "C04": [{"name":"Box D","width":80,"height":60,"depth":100,"weight":15.0,"qty":2}],
        "C05": [{"name":"Box E","width":30,"height":20,"depth":40,"weight":2.0,"qty":8}],
    }
    st.session_state.solved = False

st.button("🎲 Contoh Data Jakarta (5 pelanggan)", on_click=load_sample)

# Tabel pelanggan
if st.session_state.customers:
    st.subheader("Daftar Pelanggan & Barang")
    rows = []
    for c in st.session_state.customers:
        items = st.session_state.item_catalog.get(c["id"], [])
        for it in items:
            vol = it["width"] * it["height"] * it["depth"] * it["qty"]
            rows.append({
                "ID"          : c["id"],
                "Pelanggan"   : c["name"],
                "Barang"      : it["name"],
                "W×H×D (cm)"  : f"{it['width']}×{it['height']}×{it['depth']}",
                "Berat (kg)"  : it["weight"],
                "Qty"         : it["qty"],
                "Vol Total (cm³)": f"{vol:,.0f}",
            })
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    col_del, col_clr = st.columns(2)
    with col_del:
        del_opts = {c["name"]: c["id"] for c in st.session_state.customers}
        del_name = st.selectbox("Hapus pelanggan:", list(del_opts.keys()))
        def hapus():
            cid = del_opts[del_name]
            st.session_state.customers = [c for c in st.session_state.customers if c["id"] != cid]
            st.session_state.item_catalog.pop(cid, None)
            st.session_state.solved = False
        st.button("🗑️ Hapus", on_click=hapus)

    with col_clr:
        def reset():
            st.session_state.customers   = []
            st.session_state.item_catalog = {}
            st.session_state.solved      = False
        st.button("🔄 Reset Semua", on_click=reset)
else:
    st.info("Belum ada pelanggan. Tambahkan atau gunakan contoh data.")

# ============================================================
# STEP 3 — SOLVING
# ============================================================
st.markdown("---")
st.header("⚙️ Step 3: Jalankan Solver Terintegrasi")

if st.session_state.customers:
    use_2opt = st.checkbox("Aktifkan 2-opt route improvement", value=True)

    st.info(
        "**Opsi B — Integrasi Penuh:** Setiap kali VRP mencoba assign pelanggan ke truck, "
        "3D Bin Packing langsung dicek. Jika barang tidak muat secara fisik, "
        "pelanggan dimasukkan ke truck berikutnya."
    )

    if st.button("🚀 Jalankan Solver", type="primary"):
        # Susun daftar: index 0 = depot, 1..n = pelanggan
        all_nodes = [{"id":"DEPOT","name":depot_name,"lat":depot_lat,"lon":depot_lon}] + \
                    st.session_state.customers

        progress = st.progress(0)
        with st.spinner("Solver berjalan — 3D Bin Packing dicek setiap assignment..."):
            results, dist_matrix = solve_integrated(
                all_nodes,
                st.session_state.item_catalog,
                truck_cfg,
                use_2opt=use_2opt
            )
        progress.progress(100)

        st.session_state.results     = results
        st.session_state.dist_matrix = dist_matrix.tolist()
        st.session_state.solved      = True
        st.session_state.all_nodes   = all_nodes
        st.session_state.truck_cfg   = truck_cfg
        st.success(f"✅ Selesai! {len(results)} truck digunakan.")
else:
    st.warning("Tambahkan minimal 1 pelanggan untuk menjalankan solver.")

# ============================================================
# STEP 4 — OUTPUT
# ============================================================
if st.session_state.solved and st.session_state.results:
    st.markdown("---")
    st.header("📤 Step 4: Hasil Optimasi")

    results     = st.session_state.results
    dist_matrix = np.array(st.session_state.dist_matrix)
    all_nodes   = st.session_state.all_nodes
    t_cfg       = st.session_state.truck_cfg
    truck_vol   = t_cfg["width"] * t_cfg["height"] * t_cfg["depth"]

    # ── 4a. Ringkasan per Truck ──────────────────────────────
    st.subheader("📋 Ringkasan Rute & Muatan")
    total_dist = 0.0
    summary_rows = []
    for i, res in enumerate(results):
        stops = [depot_name] + [c["name"] for c in res["customers"]] + [depot_name]
        total_dist += res["distance"]
        summary_rows.append({
            "Truck"           : f"Truck {i+1}",
            "Rute"            : " → ".join(stops),
            "Jml Pelanggan"   : len(res["route"]),
            "Utilisasi Ruang" : f"{res['utilization']:.1f}%",
            "Jarak (km)"      : f"{res['distance']:.2f}",
        })
    st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)
    st.metric("Total Jarak Semua Truck", f"{total_dist:.2f} km")

    # ── 4b. Peta Rute ────────────────────────────────────────
    st.subheader("🗺️ Visualisasi Rute di Peta")
    all_coords  = [(n["lat"], n["lon"]) for n in all_nodes]
    center_lat  = np.mean([c[0] for c in all_coords])
    center_lon  = np.mean([c[1] for c in all_coords])
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11)

    folium.Marker(
        location=[all_nodes[0]["lat"], all_nodes[0]["lon"]],
        popup=f"<b>{depot_name}</b><br>Depot",
        tooltip=depot_name,
        icon=folium.Icon(color="black", icon="home", prefix="fa")
    ).add_to(m)

    for i, res in enumerate(results):
        color = COLORS[i % len(COLORS)]
        path  = [all_coords[0]] + [all_coords[r] for r in res["route"]] + [all_coords[0]]
        folium.PolyLine(path, color=color, weight=3, opacity=0.8,
                        tooltip=f"Truck {i+1}").add_to(m)
        for order, (r, cust) in enumerate(zip(res["route"], res["customers"]), 1):
            folium.Marker(
                location=[all_coords[r][0], all_coords[r][1]],
                popup=(f"<b>{cust['name']}</b><br>Truck {i+1} | Stop {order}"),
                tooltip=f"{order}. {cust['name']}",
                icon=folium.Icon(color=color, icon="shopping-cart", prefix="fa")
            ).add_to(m)

    st_folium(m, width="100%", height=500, returned_objects=[])

    # ── 4c. Utilisasi Kapasitas ──────────────────────────────
    st.subheader("📊 Utilisasi Kapasitas per Truck")
    for i, res in enumerate(results):
        pct      = float(res["utilization"])   # pastikan bukan Decimal
        used_vol = float(res["used_vol"])
        ind = "🟢" if pct < 70 else ("🟡" if pct < 90 else "🔴")
        st.write(f"### 🚛 Truck {i+1}")
        col_a, col_b = st.columns(2)
        with col_a:
            st.write(f"{ind} **Utilisasi Ruang:** {pct:.1f}%")
            st.progress(min(int(pct), 100))
            st.caption(f"Volume terpakai: {used_vol:,.0f} / {truck_vol:,.0f} cm³")
        with col_b:
            stops = " → ".join([depot_name] + [c["name"] for c in res["customers"]] + [depot_name])
            st.write(f"**Rute:** {stops}")
            st.write(f"**Jarak:** {res['distance']:.2f} km")
        st.markdown("---")

    # ── 4d. Visualisasi 3D per Truck ─────────────────────────
    st.subheader("📦 Visualisasi 3D Muatan Truck")

    truck_tabs = st.tabs([f"Truck {i+1}" for i in range(len(results))])
    for i, (res, tab) in enumerate(zip(results, truck_tabs)):
        with tab:
            if res["truck_bin"] is None:
                st.info("Tidak ada barang di truck ini.")
                continue

            fitted_items = res["truck_bin"].items
            if not fitted_items:
                st.info("Tidak ada barang yang berhasil dimuat.")
                continue

            fig = go.Figure()
            for idx, item in enumerate(fitted_items):
                x, y, z = item.position[0], item.position[1], item.position[2]
                w, h, d  = item.width, item.height, item.depth
                color    = PLOTLY_COLORS[idx % len(PLOTLY_COLORS)]

                fig.add_trace(go.Mesh3d(
                    x=[x,   x+w, x+w, x,   x,   x+w, x+w, x  ],
                    y=[y,   y,   y+h, y+h, y,   y,   y+h, y+h],
                    z=[z,   z,   z,   z,   z+d, z+d, z+d, z+d],
                    color=color,
                    opacity=0.55,
                    alphahull=0,
                    name=item.name,
                    hovertemplate=(
                        f"<b>{item.name}</b><br>"
                        f"Posisi: ({x},{y},{z})<br>"
                        f"Ukuran: {w}×{h}×{d} cm"
                    )
                ))

            # Garis rangka truck
            tw, th, td = t_cfg["width"], t_cfg["height"], t_cfg["depth"]
            edges = [
                [(0,0,0),(tw,0,0)],[(0,th,0),(tw,th,0)],
                [(0,0,td),(tw,0,td)],[(0,th,td),(tw,th,td)],
                [(0,0,0),(0,th,0)],[(tw,0,0),(tw,th,0)],
                [(0,0,td),(0,th,td)],[(tw,0,td),(tw,th,td)],
                [(0,0,0),(0,0,td)],[(tw,0,0),(tw,0,td)],
                [(0,th,0),(0,th,td)],[(tw,th,0),(tw,th,td)],
            ]
            for e in edges:
                fig.add_trace(go.Scatter3d(
                    x=[e[0][0],e[1][0]], y=[e[0][1],e[1][1]], z=[e[0][2],e[1][2]],
                    mode="lines",
                    line=dict(color="gray", width=2),
                    showlegend=False,
                    hoverinfo="skip"
                ))

            fig.update_layout(
                scene=dict(
                    xaxis=dict(title="Lebar (cm)", range=[0, tw]),
                    yaxis=dict(title="Tinggi (cm)", range=[0, th]),
                    zaxis=dict(title="Panjang (cm)", range=[0, td]),
                    aspectmode="manual",
                    aspectratio=dict(
                        x=tw/max(tw,th,td),
                        y=th/max(tw,th,td),
                        z=td/max(tw,th,td)
                    )
                ),
                height=550,
                margin=dict(l=0, r=0, b=0, t=30),
                title=f"Truck {i+1} — {res['utilization']:.1f}% terisi | {len(fitted_items)} item"
            )
            st.plotly_chart(fig, use_container_width=True)

            # Tabel item dalam truck ini
            item_rows = []
            for item in fitted_items:
                item_rows.append({
                    "Item"     : item.name,
                    "Posisi (x,y,z)" : str(item.position),
                    "W×H×D"   : f"{item.width}×{item.height}×{item.depth}",
                })
            st.dataframe(pd.DataFrame(item_rows), use_container_width=True)

    # ── 4e. KPI Dashboard ────────────────────────────────────
    st.subheader("📈 KPI Dashboard")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    avg_util = float(np.mean([float(r["utilization"]) for r in results]))
    total_items = sum(len(r["truck_bin"].items) if r["truck_bin"] else 0 for r in results)
    kpi1.metric("Jumlah Truck", len(results))
    kpi2.metric("Rata-rata Utilisasi", f"{avg_util:.1f}%")
    kpi3.metric("Total Jarak", f"{total_dist:.1f} km")
    kpi4.metric("Total Item Dimuat", total_items)

    # Pie chart utilisasi
    pie_fig = go.Figure(data=[go.Pie(
        labels=[f"Truck {i+1}" for i in range(len(results))],
        values=[float(r["utilization"]) for r in results],
        hole=0.4,
        hovertemplate="%{label}: %{value:.1f}%<extra></extra>"
    )])
    pie_fig.update_layout(title="Perbandingan Utilisasi Ruang per Truck", height=350)
    st.plotly_chart(pie_fig, use_container_width=True)

    # ── 4f. Export CSV ───────────────────────────────────────
    st.subheader("📥 Export Hasil")
    export_rows = []
    for i, res in enumerate(results):
        for order, cust in enumerate(res["customers"], 1):
            items = st.session_state.item_catalog.get(cust["id"], [])
            for it in items:
                export_rows.append({
                    "Truck"      : f"Truck {i+1}",
                    "Urutan Stop": order,
                    "Pelanggan"  : cust["name"],
                    "Latitude"   : cust["lat"],
                    "Longitude"  : cust["lon"],
                    "Barang"     : it["name"],
                    "W×H×D (cm)" : f"{it['width']}×{it['height']}×{it['depth']}",
                    "Qty"        : it["qty"],
                    "Utilisasi %": f"{res['utilization']:.1f}",
                    "Jarak (km)" : f"{res['distance']:.2f}",
                })
    df_export = pd.DataFrame(export_rows)
    st.download_button(
        "⬇️ Download Hasil CSV",
        data=df_export.to_csv(index=False).encode("utf-8"),
        file_name="smart_logistics_result.csv",
        mime="text/csv"
    )

# ============================================================
# FOOTER
# ============================================================
st.markdown("---")
st.markdown(
    "**Smart Logistics AI** — Integrasi 3D Bin Packing + CVRP (Opsi B) | "
    "Setiap assignment VRP dicek secara fisik oleh 3D Bin Packing"
)