import os
import sys
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import math

# --- Configuration ---
FASTEST_LAP_REPO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../Fastest-Lap"))
DATABASE_DIR = os.path.join(FASTEST_LAP_REPO_PATH, "database")
TRACKS_DIR = os.path.join(DATABASE_DIR, "tracks")
VEHICLES_DIR = os.path.join(DATABASE_DIR, "vehicles")

# Add library path
LIB_PATH = os.path.join(FASTEST_LAP_REPO_PATH, "bin") # bin contains the DLL
INCLUDE_PATH = os.path.join(FASTEST_LAP_REPO_PATH, "include")

if os.path.exists(INCLUDE_PATH):
    sys.path.append(INCLUDE_PATH)

if os.path.exists(LIB_PATH):
    sys.path.append(LIB_PATH)
    os.environ["PATH"] += os.pathsep + LIB_PATH
    
    # For Python 3.8+ on Windows, we need to explicitly add the DLL directory
    if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
        os.add_dll_directory(LIB_PATH)
        # Also add common dependency locations if they exist
        deps = [
            os.path.join(FASTEST_LAP_REPO_PATH, "build/lion/build/lapack/build/bin"),
            os.path.join(FASTEST_LAP_REPO_PATH, "build/lion/build/tinyxml/build"),
            os.path.join(FASTEST_LAP_REPO_PATH, "build/thirdparty/bin"),
            r"C:\msys64\ucrt64\bin"
        ]
        for d in deps:
            if os.path.exists(d):
                os.add_dll_directory(d)

# --- Wrapper & Mock ---

class FastestLapWrapper:
    def __init__(self):
        self.mock_mode = False
        try:
            import fastest_lap
            self.lib = fastest_lap
            print("Successfully loaded fastest_lap library.")
        except ImportError:
            print("Could not load fastest_lap library. Using MOCK MODE.")
            self.mock_mode = True
            self.lib = None

    def create_vehicle(self, vehicle_def, vehicle_file):
        if self.mock_mode:
            return
        # Try to delete first to avoid "already exists" error
        try:
            self.lib.delete_variable(vehicle_def)
        except:
            pass
        self.lib.create_vehicle_from_xml(vehicle_def, vehicle_file)

    def create_track(self, track_name, track_file):
        if self.mock_mode:
            return
        # Try to delete first to avoid "already exists" error
        try:
            self.lib.delete_variable(track_name)
        except:
            pass
        self.lib.create_track_from_xml(track_name, track_file)

    def optimize(self, vehicle_def, track_name, n_points=400):
        if self.mock_mode:
            # Generate fake telemetry for visualization testing
            return self._generate_mock_data(n_points, track_name, vehicle_name=vehicle_def)
        
        # Real simulation
        try:
            # Pre-flight checks
            track_xml = TrackManager().get_track_xml_path(track_name)
            if not os.path.exists(track_xml):
                print(f"Track file not found: {track_xml}")
                return None
                
            # 1. Download track data (arclength)
            s = self.lib.track_download_data(track_name, "arclength")
            
            # 2. Run Optimization
            options = "<options>"
            options += "    <output_variables>"
            options += "        <prefix>run/</prefix>"
            options += "    </output_variables>"
            options += "    <print_level> 0 </print_level>" # Less output
            options += "</options>"
            
            ret = self.lib.optimal_laptime(vehicle_def, track_name, s, options)
            run_data = self.lib.download_variables(*ret)
            self.lib.delete_variable("run/*")
            
            # Combine into a nice dict/df
            try:
                # Helper to find key
                def get_var(keys, preferred):
                     for k in preferred:
                         if k in keys: return keys[k]
                     raise KeyError(f"Could not find any of {preferred}")

                return {
                    "x": get_var(run_data, ["x", "chassis.position.x"]),
                    "y": get_var(run_data, ["y", "chassis.position.y"]),
                    "u": get_var(run_data, ["u", "chassis.velocity.x", "vehicle.velocity.x"]), # speed usually
                    "time": get_var(run_data, ["time"]),
                    "s": s
                }
            except KeyError as e:
                print(f"Missing key in simulation result: {e}")
                print(f"Available keys: {list(run_data.keys())}")
                return None
        except Exception as e:
            print(f"Error in optimization for {vehicle_def} at {track_name}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _generate_mock_data(self, n_points, track_name=None, vehicle_name="vehicle"):
        # Default to circle if no track found
        x = []
        y = []
        
        if track_name:
            try:
                # Instantiate here to avoid circular dependency issues at module level if any
                # (Though they are in same file, this is safe)
                tm = TrackManager()
                data = tm.load_track_data(track_name)
                if data and 'centerline' in data:
                    x = np.array(data['centerline']['x'])
                    y = np.array(data['centerline']['y'])
                    # Ignore n_points, use track resolution
                    n_points = len(x)
            except Exception as e:
                print(f"Mock data generation failed for track {track_name}: {e}")

        if len(x) == 0:
            # Fallback Circle
            t = np.linspace(0, 2*np.pi, n_points)
            x = 500 * np.cos(t)
            y = 300 * np.sin(t)
        
        # Calculate Mock Physics
        # 1. Calculate path distance (s)
        s = np.zeros(n_points)
        for i in range(1, n_points):
            dist = np.sqrt((x[i]-x[i-1])**2 + (y[i]-y[i-1])**2)
            s[i] = s[i-1] + dist
            
        # 2. Calculate Curvature for Speed Profile
        # Simple method: changes in direction
        dx = np.gradient(x)
        dy = np.gradient(y)
        ddx = np.gradient(dx)
        ddy = np.gradient(dy)
        
        # curvature = |x'y'' - y'x''| / (x'^2 + y'^2)^(3/2)
        numerator = np.abs(dx * ddy - dy * ddx)
        denominator = (dx**2 + dy**2)**1.5
        # Avoid division by zero
        denominator[denominator < 1e-6] = 1e-6
        curvature = numerator / denominator
        
        # 3. Generate Speed (u)
        # Vary max speed based on vehicle name hash to show difference
        import hashlib
        h = int(hashlib.sha256(vehicle_name.encode('utf-8')).hexdigest(), 16) % 100
        speed_factor = 1.0 + (h - 50) / 500.0 # +/- 10%
        
        max_speed = (300 / 3.6) * speed_factor
        min_speed = (60 / 3.6) * speed_factor
        
        # Normalize curvature 0..1 (roughly)
        k_norm = curvature / (np.max(curvature) + 1e-6)
        
        # Simple inv relation
        u = max_speed - (max_speed - min_speed) * (k_norm ** 0.3)
        
        # Smooth output
        u = pd.Series(u).rolling(10, center=True, min_periods=1).mean().to_numpy()

        # 4. Integrate time
        # t = sum(ds / v)
        time = np.zeros(n_points)
        for i in range(1, n_points):
            ds = s[i] - s[i-1]
            avg_v = (u[i] + u[i-1]) / 2
            if avg_v < 1.0: avg_v = 1.0
            time[i] = time[i-1] + ds / avg_v
        
        return {
            "x": x.tolist(),
            "y": y.tolist(),
            "u": u.tolist(), 
            "time": time.tolist(),
            "s": s.tolist()
        }

# --- Data Managers ---

class TrackManager:
    def list_tracks(self):
        """Returns list of available track names (folder names)."""
        if not os.path.exists(TRACKS_DIR):
            return ["No Tracks Found"]
        return [d for d in os.listdir(TRACKS_DIR) if os.path.isdir(os.path.join(TRACKS_DIR, d))]

    def load_track_data(self, track_name):
        """Parses the track XML to get coordinates, elevation, and banking."""
        # Try finding the best file: _3d.xml > _adapted.xml > .xml
        base_path = os.path.join(TRACKS_DIR, track_name)
        possible_files = [f"{track_name}_3d.xml", f"{track_name}_adapted.xml", f"{track_name}.xml"]
        
        xml_path = None
        for f in possible_files:
            p = os.path.join(base_path, f)
            if os.path.exists(p):
                xml_path = p
                break
        
        if not xml_path:
            return None

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            data_node = root.find("data")
            if data_node is None: return None
            
            def parse_csv_node(node, key):
                child = node.find(key)
                if child is not None and child.text:
                    return [float(v) for v in child.text.split(',')]
                return None

            def get_coords(section_name):
                sec = data_node.find(section_name)
                if sec is None: return None, None, None
                
                xs = parse_csv_node(sec, "x")
                ys = parse_csv_node(sec, "y")
                zs = parse_csv_node(sec, "z")
                
                # Handling if xs or ys are missing (shouldn't happen for valid tracks)
                if xs is None or ys is None: return [], [], []
                
                # If Z is missing, fill with zeros
                if zs is None:
                    zs = [0.0] * len(xs)
                    
                return xs, ys, zs

            # Get coordinates
            cl_x, cl_y, cl_z = get_coords("centerline")
            left_x, left_y, left_z = get_coords("left_boundary")
            
            # Right boundary naming check
            right_sec = data_node.find("right_boundary")
            if right_sec is None:
                right_x, right_y, right_z = get_coords("right_measured_boundary")
            else:
                right_x, right_y, right_z = get_coords("right_boundary")

            # Arclength
            s = parse_csv_node(data_node, "arclength")
            if s is None and cl_x:
                # Approximate s if missing
                s = [0.0]
                for i in range(1, len(cl_x)):
                    dist = math.sqrt((cl_x[i]-cl_x[i-1])**2 + (cl_y[i]-cl_y[i-1])**2)
                    s.append(s[-1] + dist)

            # Compute Banking
            # Banking ~= arctan( dz / d_horizontal )
            banking = []
            if left_z and right_z and len(left_z) == len(right_z):
                for i in range(len(left_z)):
                    dx = right_x[i] - left_x[i]
                    dy = right_y[i] - left_y[i]
                    dz = right_z[i] - left_z[i]
                    w_horiz = math.sqrt(dx*dx + dy*dy)
                    
                    if w_horiz > 0.1: # Avoid div/0
                        # Positive banking usually means inside is lower. 
                        # This calc gives angle of right relative to left.
                        # We might need to know which way the turn is to define "positive" banking correctly (superelevation).
                        # For simple visualization, just showing the tilt angle is good.
                        angle = math.degrees(math.atan2(dz, w_horiz))
                        banking.append(angle)
                    else:
                        banking.append(0.0)
            else:
                banking = [0.0] * len(cl_x)

            return {
                "centerline": {"x": cl_x, "y": cl_y, "z": cl_z},
                "left": {"x": left_x, "y": left_y, "z": left_z},
                "right": {"x": right_x, "y": right_y, "z": right_z},
                "s": s,
                "banking": banking
            }

        except Exception as e:
            print(f"Error parsing track XML: {e}")
            return None

    
    def get_track_xml_path(self, track_name):
        """Returns the path to the best available track XML file."""
        base_path = os.path.join(TRACKS_DIR, track_name)
        possible_files = [f"{track_name}_3d.xml", f"{track_name}_adapted.xml", f"{track_name}.xml"]
        
        for f in possible_files:
            p = os.path.join(base_path, f)
            if os.path.exists(p):
                return p
        
        # If none found, return the _adapted.xml path anyway (will error, but at least it's explicit)
        return os.path.join(base_path, f"{track_name}_adapted.xml")

class VehicleManager:
    def list_vehicles(self):
        """Returns dict of type -> list of files."""
        vehicles = {}
        if not os.path.exists(VEHICLES_DIR):
            return {}
            
        for v_type in os.listdir(VEHICLES_DIR):
            type_dir = os.path.join(VEHICLES_DIR, v_type)
            if os.path.isdir(type_dir):
                files = [f for f in os.listdir(type_dir) if f.endswith(".xml")]
                vehicles[v_type] = files
        return vehicles

    def load_vehicle_params(self, v_type, filename):
        """Parses vehicle XML to editable dict."""
        path = os.path.join(VEHICLES_DIR, v_type, filename)
        tree = ET.parse(path)
        root = tree.getroot()
        
        # Helper to find interesting nodes
        params = {}
        
        # Mass
        chassis = root.find("chassis")
        if chassis is not None:
            mass = chassis.find("mass")
            if mass is not None:
                params["mass_kg"] = float(mass.text)
        
        # Power (rear axle usually)
        rear_axle = root.find("rear-axle")
        if rear_axle is not None:
            engine = rear_axle.find("engine")
            if engine is not None:
                power = engine.find("maximum-power")
                if power is not None:
                    params["power_kw"] = float(power.text)
        
        # Aero
        if chassis is not None:
            aero = chassis.find("aerodynamics")
            if aero is not None:
                cd = aero.find("cd")
                cl = aero.find("cl")
                area = aero.find("area")
                if cd is not None: params["aero_cd"] = float(cd.text)
                if cl is not None: params["aero_cl"] = float(cl.text)
                if area is not None: params["aero_area"] = float(area.text)

        return params, path

    def save_vehicle_params(self, path, new_params):
        """Updates the XML file."""
        tree = ET.parse(path)
        root = tree.getroot()
        
        # Update Mass
        if "mass_kg" in new_params:
            root.find("chassis").find("mass").text = str(new_params["mass_kg"])
            
        # Update Power
        if "power_kw" in new_params:
            # Need to be robust if path doesn't exist
            eng = root.find("rear-axle").find("engine")
            if eng:
                eng.find("maximum-power").text = str(new_params["power_kw"])
        
        # Update Aero
        if "aero_cd" in new_params:
            root.find("chassis").find("aerodynamics").find("cd").text = str(new_params["aero_cd"])
        
        tree.write(path)


# --- Result Persistence ---

class ResultManager:
    def __init__(self):
        self.base_dir = os.path.abspath(os.path.join(DATABASE_DIR, "..", "data", "results"))
        self.telemetry_dir = os.path.join(self.base_dir, "telemetry")
        self.summary_file = os.path.join(self.base_dir, "summary.csv")
        
        # Ensure directories exist
        os.makedirs(self.telemetry_dir, exist_ok=True)

    def save_run(self, vehicle, track, run_data, run_id=None):
        import datetime
        import uuid
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if not run_id:
            run_id = str(uuid.uuid4())[:8]

        # 1. Save Telemetry
        # Need to ensure run_data['x'] etc are lists, not just raw dict
        # run_data is usually a dict of lists
        df = pd.DataFrame(run_data)
        
        telem_filename = f"{timestamp.replace(':','-').replace(' ','_')}_{vehicle}_{track}.csv"
        telem_path = os.path.join(self.telemetry_dir, telem_filename)
        df.to_csv(telem_path, index=False)
        
        # 2. Append to Summary
        # Safely get scalar values
        lap_time = run_data['time'][-1]
        max_speed = max(run_data['u']) * 3.6
        
        summary_record = {
            "timestamp": timestamp,
            "run_id": run_id,
            "vehicle": vehicle,
            "track": track,
            "lap_time_s": lap_time,
            "max_speed_kmh": max_speed,
            "telemetry_file": telem_filename
        }
        
        # Convert to DF for easy CSV handling
        df_summary = pd.DataFrame([summary_record])
        
        if not os.path.exists(self.summary_file):
            df_summary.to_csv(self.summary_file, index=False)
        else:
            df_summary.to_csv(self.summary_file, mode='a', header=False, index=False)
            
        print(f"Saved run {run_id} to {self.summary_file}")
        return run_id
