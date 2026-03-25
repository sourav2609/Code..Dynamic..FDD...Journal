import json
from skyfield.api import wgs84, load
import numpy as np
from .components import UE, Satellite
from .synthetic_orbit import SyntheticOrbitLocation

class Network:
    def __init__(self, numSat, numUE, central_loc, radius_km, time):
        self.numSat = numSat
        self.numUE = numUE
        self.central_loc = central_loc
        self.radius_km = radius_km
        self.time = time
        self.ues = []
        self.satellites = []

    def generateLayout(self, Ns, Nu, satMaxPow, ueMaxPow, outfile):
        self.ues = [UE(loc, Nu, ueMaxPow) for loc in self.generateRandomLoc()]
        self.satellites = [Satellite(loc, Ns, satMaxPow) for loc in self.satSelection(outfile)] 
    
    def generateRandomLoc(self):
        earth_radius_km = 6371  # Approximate Earth radius in km       
        lat0, lon0 = self.central_loc.latitude.degrees, self.central_loc.longitude.degrees
        lat0_rad, lon0_rad = np.radians(lat0), np.radians(lon0)        
        random_locations = []
        for _ in range(self.numUE):
            # Generate a random distance within the circle
            r = self.radius_km * np.sqrt(np.random.uniform(0, 1))
            theta = np.random.uniform(0, 2 * np.pi)
            
            # Convert polar to Cartesian displacement
            delta_lat = (r / earth_radius_km) * np.cos(theta) * (180 / np.pi)
            delta_lon = (r / earth_radius_km) * np.sin(theta) * (180 / np.pi) / np.cos(lat0_rad)
            
            # Compute new latitude and longitude
            new_lat = lat0 + delta_lat
            new_lon = lon0 + delta_lon
            
            # Append as a Skyfield wgs84 location
            random_locations.append(wgs84.latlon(new_lat, new_lon))
        
        return random_locations
    
    def satSelection(self, outfile):
        with open(outfile, "r") as f:
            header = f.read(256).lstrip()

        if header.startswith("{"):
            with open(outfile, "r") as f:
                payload = json.load(f)
            if payload.get("format") == "synthetic_satellite_instances_v1":
                return [
                    SyntheticOrbitLocation.from_record(record)
                    for record in payload["satellites"]
                ]

        # Load satellite TLEs from Celestrak
        selectedSat = load.tle_file(outfile)  #"starlink.txt" "iridium.txt"
        return selectedSat
    
