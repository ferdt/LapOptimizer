
import sys
import os

# Set up paths
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from utils import FastestLapWrapper, TrackManager, VehicleManager

def debug_run():
    print("--- Starting Debug Run ---")
    
    # 1. Initialize Wrapper
    wrapper = FastestLapWrapper()
    if wrapper.mock_mode:
        print("WARNING: Wrapper is in MOCK MODE. Library not loaded.")
        return

    # 2. Setup Track and Vehicle
    track_name = "catalunya"
    vehicle_type = "f1"
    vehicle_file = "ferrari-2022-australia.xml"
    vehicle_label = "test_car"
    
    tm = TrackManager()
    vm = VehicleManager()
    
    # Verify files
    track_xml_path = tm.get_track_xml_path(track_name)
    vehicle_xml_path = os.path.join(vm.VEHICLES_DIR if hasattr(vm, 'VEHICLES_DIR') else os.path.join(os.path.dirname(tm.TRACKS_DIR if hasattr(tm, 'TRACKS_DIR') else os.path.dirname(track_xml_path)), "../vehicles"), vehicle_type, vehicle_file)
    # The utils.py defines global variables for dirs, let's use the managers or imports
    from utils import DATABASE_DIR
    vehicle_xml_path = os.path.join(DATABASE_DIR, f"vehicles/{vehicle_type}/{vehicle_file}")

    print(f"Track XML: {track_xml_path}")
    print(f"Vehicle XML: {vehicle_xml_path}")
    
    if not os.path.exists(track_xml_path):
        print("ERROR: Track file missing!")
        return
    if not os.path.exists(vehicle_xml_path):
        print("ERROR: Vehicle file missing!")
        return

    # 3. Create Entities in Library
    print("Creating vehicle...")
    try:
        wrapper.create_vehicle(vehicle_label, vehicle_xml_path)
    except Exception as e:
        print(f"ERROR creating vehicle: {e}")
        return

    print("Creating track...")
    try:
        wrapper.create_track(track_name, track_xml_path)
    except Exception as e:
        print(f"ERROR creating track: {e}")
        return
        
    # 4. Optimize
    print("Running optimization...")
    try:
        result = wrapper.optimize(vehicle_label, track_name)
        if result is None:
            print("FAILURE: Optimization returned None.")
        else:
            print("SUCCESS: Simulation produced results.")
            print(f"Lap Time: {result['time'][-1]:.3f}s")
    except Exception as e:
        print(f"CRITICAL EXCEPTION during optimization: {e}")

if __name__ == "__main__":
    debug_run()
