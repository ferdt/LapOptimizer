import streamlit as st
import altair as alt
import pandas as pd
import numpy as np
from utils import FastestLapWrapper, TrackManager, VehicleManager, ResultManager, DATABASE_DIR
from plot_generator import generate_track_plot
import os

st.set_page_config(page_title="Simulation", page_icon="⏱️", layout="wide")

st.title("⏱️ Optimal Lap Time Simulation")

# --- Setup ---
wrapper = FastestLapWrapper()
tm = TrackManager()
vm = VehicleManager()

if wrapper.mock_mode:
    st.warning("⚠️ **MOCK MODE ACTIVE**: The `fastest_lap` library was not found. Simulations are generating fake data for visualization testing only.")

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
        try:
            # We need unique names for the vehicle instance in the lib
            wrapper.create_vehicle(label, vehicle_xml)
            wrapper.create_track(track_name, track_xml) 
            return wrapper.optimize(label, track_name)
        except Exception as e:
            print(f"Error in run_sim for {v_file}: {e}")
            return None

    with st.spinner("Running Simulations..."):
        try:
            for idx, v_raw in enumerate(selected_vehicles_raw):
                v_type, v_file = v_raw.split(" / ")
                label = f"car_{idx}"
                res = run_sim(v_type, v_file, label)
                if res is not None:
                    results[v_file] = res
                    # Auto-save results
                    try:
                        rm = ResultManager()
                        run_id = rm.save_run(v_file, track_name, res)
                        print(f"✓ Saved telemetry for {v_file} (ID: {run_id})")
                    except Exception as e:
                        st.error(f"Failed to save results for {v_file}: {e}")
                        print(f"Failed to auto-save results for {v_file}: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    st.warning(f"⚠️ Simulation failed for {v_file}. Skipping.")
                
            st.session_state.sim_results = results
            
        except Exception as e:
            st.error(f"Simulation loop crashed: {e}")

# --- Visualization ---

if st.session_state.sim_results:
    results = st.session_state.sim_results
    
    # 1. Summary Table
    st.subheader("📊 Results Summary")
    summary_data = []

    def format_time(seconds):
        m = int(seconds // 60)
        s = seconds % 60
        return f"{m:02d}:{s:06.3f}"

    for name, res in results.items():
        if res is None: continue
        summary_data.append({
            "Vehicle": name,
            "Lap Time": format_time(res['time'][-1]),
            "Max Speed (km/h)": f"{max(res['u']) * 3.6:.2f}"
        })
    st.table(pd.DataFrame(summary_data))
    
    # --- Export Section ---
    st.subheader("📥 Export High-Quality Plots")
    st.markdown("Generate publication-quality matplotlib plots for each vehicle")
    
    # Create columns for export buttons
    cols = st.columns(min(len(results), 4))  # Max 4 columns
    
    for idx, (name, res) in enumerate(results.items()):
        if res is None:
            continue
            
        col_idx = idx % 4
        with cols[col_idx]:
            # Generate filename
            safe_name = name.replace('.xml', '').replace(' ', '_')
            filename = f"{track_name}_{safe_name}_plot.png"
            
            # Generate plot data on-demand
            try:
                # Get track coordinates
                track_coords = wrapper.get_track_coordinates(track_name)
                
                # Generate plot
                img_buffer = generate_track_plot(
                    vehicle_name=name,
                    track_name=track_name,
                    run_data=res,
                    track_coords=track_coords,
                    dpi=150
                )
                
                # Single download button
                st.download_button(
                    label=f"📥 Export {name}",
                    data=img_buffer,
                    file_name=filename,
                    mime="image/png",
                    key=f"download_{idx}"
                )
                
            except Exception as e:
                st.error(f"Error: {e}")
    
    # --- Export All Vehicles Comparison ---
    if len(results) > 1:  # Only show if there are multiple vehicles
        st.markdown("---")
        st.markdown("### 🏁 Export Comparison Plot")
        
        try:
            # Filter out None results
            valid_results = {name: res for name, res in results.items() if res is not None}
            
            if len(valid_results) > 1:
                # Get track coordinates
                track_coords = wrapper.get_track_coordinates(track_name)
                
                # Import comparison function
                from plot_generator import generate_comparison_plot
                
                # Generate comparison plot
                comparison_buffer = generate_comparison_plot(
                    track_name=track_name,
                    results_dict=valid_results,
                    track_coords=track_coords,
                    dpi=150
                )
                
                # Show stats to confirm difference
                lap_times = [res['time'][-1] for res in valid_results.values()]
                diff_t = max(lap_times) - min(lap_times)
                st.info(f"📊 Comparing {len(valid_results)} vehicles. Lap time spread: {diff_t:.3f}s")

                # Single download button for comparison
                st.download_button(
                    label=f"📥 Export All Vehicles Comparison",
                    data=comparison_buffer,
                    file_name=f"{track_name}_comparison.png",
                    mime="image/png",
                    key="download_comparison"
                )
        except Exception as e:
            st.error(f"Error generating comparison: {e}")
    
    st.divider()
    
    # Prepare Combined DataFrame
    dfs = []
    for name, res in results.items():
        if res is None: continue
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
        
    if not dfs:
        st.error("No simulations succeeded. Please check your configuration or logs.")
        st.stop()
    else:
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
    
    # --- Debug Info ---
    # st.write("Debug: DataFrame Head", df.head())
    # st.write(f"Debug: Domain X: {domain_x}, Domain Y: {domain_y}")

    # --- Altair Charts ---
    
    hover = alt.selection_point(
        name="hover_pt",
        fields=['idx'], 
        nearest=True, 
        on='mouseover', 
        empty=False,
        clear='mouseout'
    )
    
    color_scale = alt.Scale(scheme='category10')

    # --- Load Track Limits ---
    track_data = tm.load_track_data(track_name)
    limits_layers = []
    
    if track_data:
        # Prepare DataFrames for limits (Optimized: Minimal columns)
        # Slicing to reduce data size if track is huge could be good, but full res is fine for now
        df_left = pd.DataFrame({'x': track_data['left']['x'], 'y': track_data['left']['y']})
        df_right = pd.DataFrame({'x': track_data['right']['x'], 'y': track_data['right']['y']})
        
        # DEBUG
        # st.write(f"Track Limits Loaded: Left={len(df_left)} pts, Right={len(df_right)} pts")
        
        # We need to make sure these don't interfere with the map domain/scale. 
        # Explicitly using the same scale/domain is correct as done in map_base for x/y
        
        l_layer = alt.Chart(df_left).mark_line(color='black', strokeDash=[5,5]).encode(
             x=alt.X('x', scale=alt.Scale(domain=domain_x)),
             y=alt.Y('y', scale=alt.Scale(domain=domain_y))
        )
        r_layer = alt.Chart(df_right).mark_line(color='black', strokeDash=[5,5]).encode(
             x=alt.X('x', scale=alt.Scale(domain=domain_x)),
             y=alt.Y('y', scale=alt.Scale(domain=domain_y))
        )
        limits_layers = [l_layer, r_layer]

    # 1. Track Map
    map_base = alt.Chart(df).encode(
        x=alt.X('x', axis=None, title='', scale=alt.Scale(domain=domain_x)),
        y=alt.Y('y', axis=None, title='', scale=alt.Scale(domain=domain_y)),
        color=alt.Color('Vehicle', scale=color_scale)
    ).properties(
        title=f"Track Map & Trajectory: {track_name}",
        width='container',
        height=600 # Keeping fixed height for aspect ratio sanity, but width fills
    )

    map_scatter = map_base.mark_circle(size=30).encode(
        tooltip=['Vehicle', 's', 'time', 'u'],
        opacity=alt.condition(hover, alt.value(1), alt.value(0.1))
    )
    
    map_point = map_base.mark_circle(size=100, color='red').encode().transform_filter(hover)
    
    # Add interaction to map
    map_layer = (map_scatter + map_point).add_params(hover).interactive()
    
    
    # Track limits disabled temporarily - they break rendering
    # if limits_layers:
    #     map_layer = alt.layer(limits_layers[0], limits_layers[1], map_layer)

    # 2. Speed Profile
    telem_base = alt.Chart(df).encode(
        x=alt.X('s', title='Distance (m)'),
        color=alt.Color('Vehicle', scale=color_scale)
    ).properties(
        title="Speed Profile",
        width='container',
        height=400
    )
    
    telem_line = telem_base.mark_line().encode(y=alt.Y('u', title='Speed (km/h)'))
    
    telem_point = telem_base.mark_circle(size=100).encode(
        y='u',
        tooltip=['Vehicle', 'u', 's', 'time']
    ).transform_filter(hover)
    
    telem_rule = telem_base.mark_rule(color='gray').encode().transform_filter(hover)
    
    telem_layer = (telem_line + telem_point + telem_rule)

    # Layout: Stacking vertically & resolver
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
    
    # DEBUG: Try rendering ONLY the map layer first
    # final_chart = map_layer.properties(title="Debug Map Layer")
    
    # Using new Streamlit syntax for responsive width
    st.altair_chart(final_chart, width='stretch')
    
elif not run_btn:
    st.info("Configure simulation in the sidebar.")
