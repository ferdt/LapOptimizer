import streamlit as st
import altair as alt
import pandas as pd
import numpy as np
from utils import FastestLapWrapper, TrackManager, VehicleManager, DATABASE_DIR
import os

st.set_page_config(page_title="Simulation", page_icon="⏱️", layout="wide")

st.title("⏱️ Optimal Lap Time Simulation")

# --- Setup ---
wrapper = FastestLapWrapper()
tm = TrackManager()
vm = VehicleManager()

if wrapper.mock_mode:
    st.warning("⚠️ **MOCK MODE ACTIVE**: The `fastest_lap` library was not found. Simulations are generating fake data for visualization testing only.")

import streamlit as st
import altair as alt
import pandas as pd
import numpy as np
from utils import FastestLapWrapper, TrackManager, VehicleManager, DATABASE_DIR
import os

st.set_page_config(page_title="Simulation", page_icon="⏱️", layout="wide")

st.title("⏱️ Optimal Lap Time Simulation")

# --- Setup ---
wrapper = FastestLapWrapper()
tm = TrackManager()
vm = VehicleManager()

# --- session_state initialization ---
if 'sim_results' not in st.session_state:
    st.session_state.sim_results = {}

# --- Sidebar Controls ---
with st.sidebar:
    st.header("Configuration")
    
    # Track Selection
    track_names = tm.list_tracks()
    track_name = st.selectbox("Select Track", track_names)
    
    st.divider()
    
    # Multiple Vehicle Selection
    st.subheader("Vehicles")
    vehicles_map = vm.list_vehicles()
    
    # Create flat list of vehicles for multiselect: "type / filename"
    available_vehicles = []
    for v_type, files in vehicles_map.items():
        for f in files:
            available_vehicles.append(f"{v_type} / {f}")
    
    selected_vehicles_raw = st.multiselect(
        "Select Vehicles", 
        available_vehicles,
        default=available_vehicles[:1] if available_vehicles else []
    )
    
    st.divider()
    run_btn = st.button("🚀 Run Simulation", type="primary")

# --- Logic ---

if run_btn:
    # Validation
    if not track_name:
        st.error("Please select a track.")
        st.stop()
    if not selected_vehicles_raw:
        st.error("Please select at least one vehicle.")
        st.stop()

    results = {}
    
    def run_sim(v_type, v_file, label):
        # Prepare paths
        track_xml = tm.get_track_xml_path(track_name)
        vehicle_xml = os.path.join(DATABASE_DIR, f"vehicles/{v_type}/{v_file}")
            
        # Load and Run
        # We need unique names for the vehicle instance in the lib
        wrapper.create_vehicle(label, vehicle_xml)
        wrapper.create_track(track_name, track_xml) 
        return wrapper.optimize(label, track_name)

    with st.spinner("Running Simulations..."):
        try:
            for idx, v_raw in enumerate(selected_vehicles_raw):
                v_type, v_file = v_raw.split(" / ")
                label = f"car_{idx}"
                results[v_file] = run_sim(v_type, v_file, label)
                
            st.session_state.sim_results = results
            
        except Exception as e:
            st.error(f"Simulation failed: {e}")

# --- Visualization ---

if st.session_state.sim_results:
    results = st.session_state.sim_results
    
    # 1. Summary Table
    st.subheader("📊 Results Summary")
    summary_data = []
    for name, res in results.items():
        summary_data.append({
            "Vehicle": name,
            "Lap Time (s)": f"{res['time'][-1]:.3f}",
            "Max Speed (km/h)": f"{max(res['u']) * 3.6:.2f}"
        })
    st.table(pd.DataFrame(summary_data))
    
    # Prepare Combined DataFrame
    dfs = []
    for name, res in results.items():
        d = pd.DataFrame({
            'x': res['x'],
            'y': res['y'],
            'u': [u * 3.6 for u in res['u']], # kph
            's': res['s'],
            'time': res['time'],
            'Vehicle': name,
            'idx': range(len(res['x'])) # Local index for linking
        })
        dfs.append(d)
        
    df = pd.concat(dfs)
    
    # --- Calculate Domains for Equal Aspect Ratio ---
    min_x, max_x = df['x'].min(), df['x'].max()
    min_y, max_y = df['y'].min(), df['y'].max()
    
    pad_x = (max_x - min_x) * 0.05
    pad_y = (max_y - min_y) * 0.05
    
    min_x -= pad_x
    max_x += pad_x
    min_y -= pad_y
    max_y += pad_y

    range_x = max_x - min_x
    range_y = max_y - min_y
    max_range = max(range_x, range_y)
    
    mid_x = (min_x + max_x) / 2
    mid_y = (min_y + max_y) / 2
    
    domain_x = [mid_x - max_range/2, mid_x + max_range/2]
    domain_y = [mid_y + max_range/2, mid_y - max_range/2]
    
    # --- Altair Charts ---
    
    hover = alt.selection_point(
        fields=['idx'], 
        nearest=True, 
        on='mouseover', 
        empty=False,
        clear='mouseout'
    )
    
    color_scale = alt.Scale(scheme='category10')

    # 1. Track Map
    map_base = alt.Chart(df).encode(
        x=alt.X('x', axis=None, title='', scale=alt.Scale(domain=domain_x)),
        y=alt.Y('y', axis=None, title='', scale=alt.Scale(domain=domain_y)),
        color=alt.Color('Vehicle', scale=color_scale)
    ).properties(
        title="Track Map & Trajectory",
        height=600,
        width=600
    )

    map_scatter = map_base.mark_circle(size=30).encode(
        tooltip=['Vehicle', 's', 'time', 'u'],
        opacity=alt.condition(hover, alt.value(1), alt.value(0.1))
    ).add_params(hover)
    
    map_point = map_base.mark_circle(size=100, color='red').encode().transform_filter(hover)
    
    map_layer = (map_scatter + map_point).interactive()

    # 2. Speed Profile
    telem_base = alt.Chart(df).encode(
        x=alt.X('s', title='Distance (m)'),
        color=alt.Color('Vehicle', scale=color_scale)
    ).properties(
        title="Speed Profile",
        height=400
    )
    
    telem_line = telem_base.mark_line().encode(y=alt.Y('u', title='Speed (km/h)'))
    
    telem_point = telem_base.mark_circle(size=100).encode(
        y='u',
        tooltip=['Vehicle', 'u', 's', 'time']
    ).transform_filter(hover)
    
    telem_rule = telem_base.mark_rule(color='gray').encode().transform_filter(hover)
    
    telem_layer = (telem_line + telem_point + telem_rule).interactive()

    # Layout: Stacking vertically & resolver
    final_chart = alt.vconcat(
        map_layer,
        telem_layer
    ).resolve_scale(
        color='shared'
    ).configure_title(
        fontSize=20,
        anchor='start',
        color='gray'
    )
    
    st.altair_chart(final_chart, use_container_width=True)
    
elif not run_btn:
    st.info("Configure simulation in the sidebar.")
