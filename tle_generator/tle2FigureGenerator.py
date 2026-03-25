"""
symmetric_tle_generator_with_plot.py

Generates symmetric satellites around a central location, writes Skyfield-compatible TLEs,
and saves a figure of the constellation centered at (0,0) in EPS format.
"""

import numpy as np
import datetime
import math
from skyfield.api import wgs84
import matplotlib.pyplot as plt

# Constants
MU = 398600.4418  # km^3/s^2
RE = 6371.0  # km

def tle_checksum(line):
    s = line[:68]
    total = 0
    for c in s:
        if c.isdigit():
            total += int(c)
        elif c == '-':
            total += 1
    return str(total % 10)

def _safe_piece_letter(idx):
    letters = []
    n = idx - 1
    while True:
        letters.append(chr((n % 26) + 65))
        n = n // 26 - 1
        if n < 0:
            break
    return "".join(reversed(letters))

def _mean_motion_from_altitude_km(H_km):
    a = RE + H_km
    n_rad_s = math.sqrt(MU / (a**3))
    revs_per_day = n_rad_s * 86400.0 / (2.0 * math.pi)
    return revs_per_day

def great_circle_destination(lat0_deg, lon0_deg, angular_dist_rad, az_rad):
    phi0 = math.radians(lat0_deg)
    lam0 = math.radians(lon0_deg)
    phi = math.asin(math.sin(phi0) * math.cos(angular_dist_rad) +
                    math.cos(phi0) * math.sin(angular_dist_rad) * math.cos(az_rad))
    lam = lam0 + math.atan2(math.sin(az_rad) * math.sin(angular_dist_rad) * math.cos(phi0),
                            math.cos(angular_dist_rad) - math.sin(phi0) * math.sin(phi))
    lat = math.degrees(phi)
    lon = (math.degrees(lam) + 180.0) % 360.0 - 180.0
    return lat, lon

def generate_constellation_tles(numSat, centralLoc, zenithAngle, Hsat,
                                outfile="../satelliteTLEs.txt",
                                epoch_dt=None,
                                base_norad=90000):
    if numSat < 1:
        raise ValueError("numSat must be >= 1")
    lat0 = float(centralLoc.latitude.degrees)
    lon0 = float(centralLoc.longitude.degrees)

    # Compute angular distance from central location
    rs = RE + Hsat
    epsilon = math.radians(90.0 - zenithAngle)
    t = math.tan(epsilon)
    A = RE / rs
    inner = A / math.sqrt(1.0 + t**2)
    inner = max(-1.0, min(1.0, inner))
    psi = math.acos(inner) - math.atan(t)

    azimuths_deg = np.linspace(0.0, 360.0, numSat, endpoint=False)
    subs = [great_circle_destination(lat0, lon0, psi, math.radians(a)) for a in azimuths_deg]

    # Epoch formatting
    if epoch_dt is None:
        epoch_dt = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
    else:
        if epoch_dt.tzinfo is None:
            raise ValueError("epoch_dt must be timezone-aware UTC datetime")
    doy = epoch_dt.timetuple().tm_yday
    seconds_into_day = epoch_dt.hour * 3600 + epoch_dt.minute * 60 + epoch_dt.second + epoch_dt.microsecond / 1e6
    frac = seconds_into_day / 86400.0
    frac_int = int(round(frac * 1e8))
    if frac_int >= 100_000_000:
        epoch_dt = epoch_dt + datetime.timedelta(days=1)
        doy = epoch_dt.timetuple().tm_yday
        frac_int = 0
    yy = epoch_dt.year % 100
    epoch_str = f"{yy:02d}{doy:03d}.{frac_int:08d}"

    mean_motion = _mean_motion_from_altitude_km(Hsat)
    incl_for_all = float(max(5.0, min(179.9, abs(lat0))))

    tle_lines = []
    launch_year_short = yy
    launch_number = 1
    for idx, (lat, lon) in enumerate(subs, start=1):
        satname = f"SAT-{idx}"
        raan = float(((idx - 1) * (360.0 / numSat)) % 360.0)
        ecc = 0.0001000
        ecc_str = f"{int(round(ecc * 1e7)):07d}"
        argp = 0.0
        mean_anomaly = float(((idx - 1) * (360.0 / numSat)) % 360.0)
        norad_id = base_norad + idx
        piece = _safe_piece_letter(idx)
        int_desig = f"{launch_year_short:02d}{launch_number:03d}{piece}"

        line1_body = (f"1 {norad_id:05d}U {int_desig:<8s} {epoch_str:>17s} "
                      f".00000000  00000-0  00000-0 0 ")
        line1_body = line1_body.ljust(68)
        line1 = line1_body + tle_checksum(line1_body)

        line2_body = (f"2 {norad_id:05d} "
                      f"{incl_for_all:8.4f} {raan:8.4f} {ecc_str:>7s} "
                      f"{argp:8.4f} {mean_anomaly:8.4f} {mean_motion:11.8f}")
        revnum = idx
        line2_full = f"{line2_body}{revnum:5d}"
        line2_full = line2_full.ljust(68)
        line2 = line2_full + tle_checksum(line2_full)

        tle_lines.extend([satname, line1, line2])

    # Save TLEs
    with open(outfile, "w", newline="\n") as f:
        for L in tle_lines:
            f.write(L + "\n")
    print(f"Generated {numSat} TLEs -> {outfile}")
    return subs, Hsat

def plot_constellation(subs, Hsat, centralLoc, epoch, epsfile="symmetric_constellation.eps"):
    # Compute relative positions (centered at 0,0)
    lats = [lat - centralLoc.latitude.degrees for lat, lon in subs]
    lons = [lon - centralLoc.longitude.degrees for lat, lon in subs]

    plt.figure(figsize=(6,6))
    plt.plot(0, 0, 'ro', label='Central location')  # center at origin
    plt.scatter(lons, lats, c='b', marker='^', s=80, label='Satellites')

    for x, y in zip(lons, lats):
        plt.plot([0, x], [0, y], 'k--', linewidth=0.7)

    plt.xlabel('Longitude offset (deg)')
    plt.ylabel('Latitude offset (deg)')
    plt.title(f'Symmetric Satellite Constellation at Epoch {epoch.date()} (H={Hsat} km)')
    plt.grid(True)
    plt.axis('equal')
    plt.legend()
    plt.savefig(epsfile, format='eps')
    plt.close()
    print(f"EPS figure saved as {epsfile}")

# =======================
if __name__ == "__main__":
    centralLoc = wgs84.latlon(53.0793, 8.8017)  # Bremen
    epoch = datetime.datetime(2025, 9, 26, tzinfo=datetime.timezone.utc)

    # Generate satellites
    subs, Hsat = generate_constellation_tles(
        numSat=2,
        centralLoc=centralLoc,
        zenithAngle=10,
        Hsat=600,
        outfile="synthetic_tles.txt",
        epoch_dt=epoch
    )

    # Plot constellation
    plot_constellation(subs, Hsat, centralLoc, epoch, epsfile="symmetric_constellation.eps")
