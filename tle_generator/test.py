from skyfield.api import EarthSatellite, load
import datetime

# --- Load TLEs ---
tle_file = "synthetic_tles.txt"

satellites = []

with open(tle_file, "r") as f:
    lines = [line.strip() for line in f if line.strip()]

i = 0
while i < len(lines):
    satname = lines[i]
    line1 = lines[i + 1]
    line2 = lines[i + 2]
    try:
        sat = EarthSatellite(line1, line2, satname)
        satellites.append(sat)
    except Exception as e:
        print(f"Error parsing {satname}: {e}")
    i += 3

print(f"Loaded {len(satellites)} satellites successfully.\n")

# --- Check positions at a given UTC time ---
ts = load.timescale()
t = ts.utc(2025, 9, 26, 0, 0, 0)  # Example epoch

for sat in satellites:
    geocentric = sat.at(t)
    subpoint = geocentric.subpoint()
    print(f"{sat.name}: Lat {subpoint.latitude.degrees:.4f}°, "
          f"Lon {subpoint.longitude.degrees:.4f}°, "
          f"Height {subpoint.elevation.km:.2f} km")
