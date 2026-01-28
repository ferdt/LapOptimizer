import streamlit as st
from utils import VehicleManager

st.set_page_config(page_title="Vehicle Database", page_icon="🏎️")

st.title("🏎️ Vehicle Database")

vm = VehicleManager()
vehicles_map = vm.list_vehicles()

# Selection
col1, col2 = st.columns(2)
with col1:
    v_type = st.selectbox("Vehicle Type", list(vehicles_map.keys()))
with col2:
    v_file = st.selectbox("Vehicle File", vehicles_map.get(v_type, []))

if v_file:
    st.divider()
    st.subheader(f"Edit Parameters: {v_file}")
    
    # Load current params
    params, path = vm.load_vehicle_params(v_type, v_file)
    
    with st.form("vehicle_edit_form"):
        new_mass = st.number_input("Mass (kg)", value=params.get("mass_kg", 0.0))
        new_power = st.number_input("Max Power (kW)", value=params.get("power_kw", 0.0))
        
        st.markdown("#### Aerodynamics")
        c1, c2, c3 = st.columns(3)
        with c1:
            new_cd = st.number_input("Drag Coeff (Cd)", value=params.get("aero_cd", 0.0))
        with c2:
            st.number_input("Lift Coeff (Cl) [Read-only]", value=params.get("aero_cl", 0.0), disabled=True)
        with c3:
            st.number_input("Frontal Area (m2) [Read-only]", value=params.get("aero_area", 0.0), disabled=True)
            
        submitted = st.form_submit_button("Save Changes")
        
        if submitted:
            # Construct update dict
            updates = {
                "mass_kg": new_mass,
                "power_kw": new_power,
                "aero_cd": new_cd
            }
            try:
                vm.save_vehicle_params(path, updates)
                st.success(f"Saved changes to {v_file}")
            except Exception as e:
                st.error(f"Failed to save: {e}")

    with st.expander("Raw File Path"):
        st.code(path)
