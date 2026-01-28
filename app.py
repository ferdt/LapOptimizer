import streamlit as st
from utils import FastestLapWrapper

st.set_page_config(
    page_title="Lap Optimizer",
    page_icon="🏎️",
    layout="wide"
)

st.title("🏎️ Fastest-Lap Python Interface")

st.markdown("""
Welcome to the **Lap Optimizer**, a graphical interface for the `Fastest-Lap` library.

**Features:**
- **Tracks**: Inspect track layouts and limits.
- **Vehicles**: View and edit vehicle parameters.
- **Simulation**: Run optimal lap time simulations and visualize the results.
""")

# Check Backend Status
st.header("Backend Status")
wrapper = FastestLapWrapper()

if wrapper.mock_mode:
    st.warning("⚠️ **Mock Mode Active**: The `fastest_lap` binary was not found. Simulations will use generated dummy data.")
    st.info("To fix this, ensure the compiled `fastestlapc.dll` (or .so) is in the `Fastest-Lap/lib` or `bin` directory.")
else:
    st.success("✅ **Library Loaded**: `fastest_lap` backend is active and ready for real simulations.")

st.divider()
st.markdown("### Navigation")
st.markdown("Use the sidebar to navigate between **Tracks**, **Vehicles**, and **Simulation**.")
