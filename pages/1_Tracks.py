import streamlit as st
import altair as alt
import pandas as pd
import numpy as np
from utils import TrackManager

st.set_page_config(page_title="Tracks Database", page_icon="🏁", layout="wide")

st.title("🏁 Track Database")

tm = TrackManager()
tracks = tm.list_tracks()

selected_track = st.selectbox("Select a Track", tracks)

if selected_track:
    data = tm.load_track_data(selected_track)
    
    if data:
        st.markdown(f"### {selected_track}")
        
        # --- Prepare Data ---
        # Ensure all arrays have the same length for DataFrame
        cl_x = data['centerline']['x']
        cl_y = data['centerline']['y']
        cl_z = data['centerline']['z']
        
        # Determine minimum length
        n_points = min(len(cl_x), len(cl_y), len(cl_z))
        
        if 's' in data and len(data['s']) >= n_points:
            s_data = data['s'][:n_points]
        else:
            s_data = np.arange(n_points) # Fallback
            
        if 'banking' in data and len(data['banking']) >= n_points:
            bank_data = data['banking'][:n_points]
        else:
            bank_data = [0.0] * n_points

        df = pd.DataFrame({
            'x': cl_x[:n_points],
            'y': cl_y[:n_points],
            'z': cl_z[:n_points],
            's': s_data,
            'banking': bank_data,
            'idx': range(n_points)
        })

        # --- Calculate Domains for Equal Aspect Ratio ---
        min_x, max_x = df['x'].min(), df['x'].max()
        min_y, max_y = df['y'].min(), df['y'].max()
        
        # Add some padding (5%)
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
        # Y is flipped so [max, min]
        domain_y = [mid_y + max_range/2, mid_y - max_range/2]

        # --- Altair Charts ---
        
        # Shared Selector
        # We select based on the index (idx) using nearest interaction
        hover = alt.selection_point(
            fields=['idx'], 
            nearest=True, 
            on='mouseover', 
            empty=False,
            clear='mouseout'
        )

        # 1. Map Chart
        # Color by Elevation (Z)
        chart_map = alt.Chart(df).mark_circle(size=30).encode(
            x=alt.X('x', axis=None, title='', scale=alt.Scale(domain=domain_x)),
            y=alt.Y('y', axis=None, title='', scale=alt.Scale(domain=domain_y)),
            color=alt.Color('z', title='Elevation (m)', scale=alt.Scale(scheme='turbo')),
            tooltip=['s', 'x', 'y', 'z', 'banking'],
            opacity=alt.condition(hover, alt.value(1), alt.value(0.5))
        ).add_params(
            hover
        ).properties(
            title="Track Map (Color=Elevation)",
            height=500,
            width=500 # Force square plot so equal domains = equal aspect ratio
        )
        
        # 1b. Map Highlight Point (Selected)
        map_point = alt.Chart(df).mark_circle(color='red', size=100).encode(
            x='x', y='y'
        ).transform_filter(
            hover
        )
        
        map_layer = (chart_map + map_point).interactive()

        # 2. Elevation Profile
        elev_base = alt.Chart(df).encode(x=alt.X('s', title='Distance (m)'))
        
        elev_line = elev_base.mark_line(color='orange').encode(
            y=alt.Y('z', title='Elevation (m)')
        )
        
        elev_point = elev_base.mark_circle(color='red', size=100).encode(
            y='z'
        ).transform_filter(
            hover
        )
        
        elev_rule = elev_base.mark_rule(color='gray').encode(
        ).transform_filter(
            hover
        )
        
        elev_layer = (elev_line + elev_point + elev_rule).interactive()

        # 3. Banking Profile
        bank_base = alt.Chart(df).encode(x=alt.X('s', title='Distance (m)'))
        
        bank_line = bank_base.mark_line(color='purple').encode(
            y=alt.Y('banking', title='Banking (deg)')
        )
        
        bank_point = bank_base.mark_circle(color='red', size=100).encode(
            y='banking'
        ).transform_filter(
            hover
        )
        
        bank_rule = bank_base.mark_rule(color='gray').encode(
        ).transform_filter(
            hover
        )
        
        bank_layer = (bank_line + bank_point + bank_rule).interactive()

        # --- Layout ---
        # Combine Layouts
        # Map on top (or left), Profiles on bottom (or right)
        
        combined_profiles = elev_layer.properties(height=200) & bank_layer.properties(height=200)
        
        final_chart = (map_layer | combined_profiles).resolve_scale(color='independent')

        st.altair_chart(final_chart, width='stretch')
        
        st.info("Hover over any plot to see the corresponding position on the others.")

    else:
        st.error("Could not load track data. The XML might be missing or malformed.")
