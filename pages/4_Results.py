import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
import io
from utils import ResultManager, FastestLapWrapper
from plot_generator import generate_track_plot, generate_comparison_plot

st.set_page_config(page_title="Results Viewer", page_icon="📈", layout="wide")
st.title("📈 Simulation Results Viewer")

# Initialize Managers
rm = ResultManager()
wrapper = FastestLapWrapper()

# 1. Load History
history = rm.get_all_results()

if not history:
    st.info("No simulation results found. Run some simulations in the 'pages/3_Simulation.py' page first.")
    st.stop()

# Prepare Dataframe
df_history = pd.DataFrame(history)

# Process timestamp
if 'timestamp' in df_history.columns:
    df_history['timestamp'] = pd.to_datetime(df_history['timestamp'])
    df_history = df_history.sort_values('timestamp', ascending=False)
    # Format for display
    df_history['date_str'] = df_history['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
else:
    df_history['date_str'] = "Unknown"

# Create a readable label
df_history['label'] = df_history.apply(
    lambda x: f"{x['date_str']} | {x['vehicle']} @ {x['track']} | {x['lap_time_s']:.3f}s", axis=1
)

# Display History Table
st.subheader("📜 History")
st.dataframe(
    df_history[['date_str', 'vehicle', 'track', 'lap_time_s', 'max_speed_kmh', 'run_id']],
    use_container_width=True,
    column_config={
        "date_str": "Date",
        "lap_time_s": st.column_config.NumberColumn("Lap Time (s)", format="%.3f"),
        "max_speed_kmh": st.column_config.NumberColumn("Max Speed (km/h)", format="%.1f"),
    },
    hide_index=True
)

st.divider()

# 2. Select Runs
st.subheader("🔍 Analyze & Compare")

selected_ids = st.multiselect(
    "Select runs to load:",
    options=df_history['run_id'].tolist(),
    format_func=lambda x: df_history[df_history['run_id'] == x]['label'].iloc[0]
)

if selected_ids:
    loaded_data = {}
    
    # Load Data
    for run_id in selected_ids:
        record = df_history[df_history['run_id'] == run_id].iloc[0]
        vehicle_name = record['vehicle']
        track_name = record['track']
        run_label = f"{vehicle_name} ({record['date_str']})"
        
        # Load telemetry
        df = rm.load_telemetry(run_id=run_id)
        
        if df is not None:
            # Structuring for Plot Generator
            loaded_data[run_label] = {
                'x': df['x'].tolist(),
                'y': df['y'].tolist(),
                'u': df['u'].tolist(), # m/s from CSV
                's': df['s'].tolist(),
                'time': df['time'].tolist(),
                'meta': record.to_dict()
            }
        else:
            st.error(f"Could not load telemetry for {run_label}. File might be missing.")

    if loaded_data:
        # Group by track (we can only compare runs on the same track)
        runs_by_track = {}
        for label, data in loaded_data.items():
            t_name = data['meta']['track']
            if t_name not in runs_by_track:
                runs_by_track[t_name] = {}
            runs_by_track[t_name][label] = data
            
        # Display per Track
        for track_name, group_data in runs_by_track.items():
            st.markdown(f"## 📍 Track: {track_name}")
            
            # --- Interactive Charts (Altair) ---
            st.markdown("### Interactive Telemetry")
            
            # Combine into single DF for Altair
            altair_dfs = []
            for label, d in group_data.items():
                temp_df = pd.DataFrame({
                    's': d['s'],
                    'u_kmh': np.array(d['u']) * 3.6, # Convert for display
                    'run': label
                })
                altair_dfs.append(temp_df)
                
            if altair_dfs:
                combined_df = pd.concat(altair_dfs)
                
                # Speed Profile Chart
                chart = alt.Chart(combined_df).mark_line().encode(
                    x=alt.X('s', title='Distance (m)'),
                    y=alt.Y('u_kmh', title='Speed (km/h)'),
                    color='run',
                    tooltip=['run', 's', 'u_kmh']
                ).properties(
                    height=400,
                    title="Speed vs Distance"
                ).interactive()
                
                st.altair_chart(chart, width='stretch')
            
            # --- Static Plots (Matplotlib) ---
            st.markdown("### 📥 High-Quality Exports")
            
            # Get track coordinates for this track
            coords = wrapper.get_track_coordinates(track_name)
            
            # 1. Comparison Plot (if > 1 run)
            if len(group_data) > 1:
                col1, col2 = st.columns([2, 1])
                with col1:
                    with st.spinner("Generating comparison plot..."):
                        buf = generate_comparison_plot(track_name, group_data, coords)
                        st.image(buf, caption="Comparison Plot", use_column_width=True)
                        
                        st.download_button(
                            label="📥 Download Comparison Plot",
                            data=buf,
                            file_name=f"{track_name}_comparison.png",
                            mime="image/png"
                        )
            
            # 2. Individual Plots
            st.markdown("#### Individual Run Exports")
            cols = st.columns(min(len(group_data), 3))
            for i, (label, d) in enumerate(group_data.items()):
                with cols[i % 3]:
                    if st.button(f"Generate {label}", key=f"gen_{i}"):
                        with st.spinner(f"Generating {label}..."):
                            buf = generate_track_plot(
                                vehicle_name=label, 
                                track_name=track_name, 
                                run_data=d, 
                                track_coords=coords
                            )
                            st.image(buf, use_column_width=True)
                            st.download_button(
                                label="📥 Download",
                                data=buf,
                                file_name=f"{label.replace(' ', '_')}.png",
                                mime="image/png",
                                key=f"dl_{i}"
                            )

    # --- Delete Section ---
    st.divider()
    with st.expander("🗑️ Manage Runs"):
        run_to_delete = st.selectbox(
            "Select run to delete:", 
            options=[""] + df_history['run_id'].tolist(),
            format_func=lambda x: "Select a run..." if x == "" else df_history[df_history['run_id'] == x]['label'].iloc[0]
        )
        
        if run_to_delete:
            if st.button("Permanently Delete", type="primary"):
                if rm.delete_run(run_to_delete):
                    st.success("Run deleted successfully!")
                    st.rerun()
                else:
                    st.error("Failed to delete run.")

