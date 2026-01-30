
import sys
import os
import time

# Set up paths
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from utils import FastestLapWrapper, TrackManager, VehicleManager, DATABASE_DIR

def run_test_case(wrapper, track_name, v_type, v_file):
    print(f"\n[TEST] Testing {v_type} : {v_file} on {track_name}...")
    
    vehicle_path = os.path.join(DATABASE_DIR, f"vehicles/{v_type}/{v_file}")
    if not os.path.exists(vehicle_path):
        print(f"[SKIP] Vehicle file not found: {vehicle_path}")
        return False

    label = f"test_{v_file.replace('.', '_')}"
    try:
        wrapper.create_vehicle(label, vehicle_path)
        # wrapper.create_track called globally now
        
        start_time = time.time()
        result = wrapper.optimize(label, track_name)
        elapsed = time.time() - start_time
        
        if result:
            print(f"[PASS] {v_type} simulation successful. Time: {result['time'][-1]:.3f}s (Compute: {elapsed:.2f}s)")
            return True
        else:
            print(f"[FAIL] {v_type} simulation returned None.")
            return False
            
    except Exception as e:
        print(f"[ERROR] Exception during test: {e}")
        return False

def main():
    print("--- Starting Automated Test Suite ---")
    
    wrapper = FastestLapWrapper()
    if wrapper.mock_mode:
        print("Wrapper is in Mock Mode. Tests will not cover real physics engine.")
    
    tm = TrackManager()
    track_name = "catalunya"
    
    # Initialize track ONCE
    try:
        track_xml = tm.get_track_xml_path(track_name)
        wrapper.create_track(track_name, track_xml)
        print(f"Initialized track: {track_name}")
    except Exception as e:
         print(f"Track initialization warning: {e}")
    
    # Test Cases
    vehicles_to_test = [
        ("f1", "ferrari-2022-australia.xml"),
        ("touring", "Alpine_A110S.xml"),
        ("kart", "rental-kart.xml"),
        ("touring", "Porsche_Boxster.xml")
    ]
    
    passed = 0
    total = len(vehicles_to_test)
    
    for v_type, v_file in vehicles_to_test:
        if run_test_case(wrapper, track_name, v_type, v_file):
            passed += 1
            
    print(f"\n--- Test Summary: {passed}/{total} Passed ---")
    if passed == total:
        print("ALL TESTS PASSED.")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
