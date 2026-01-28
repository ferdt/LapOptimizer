import os
from utils import TrackManager

tm = TrackManager()
track_name = "andalucia"
path = tm.get_track_xml_path(track_name)

print(f"Resolved path for {track_name}: {path}")

if os.path.exists(path):
    print("SUCCESS: Path exists!")
else:
    print("FAILURE: Path does not exist!")
    exit(1)
