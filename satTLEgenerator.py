import numpy as np
import math
import datetime
import json
from skyfield.api import wgs84

from utils.synthetic_orbit import SyntheticOrbitLocation

def tle_checksum(line):
    """Compute TLE checksum (mod 10 of digits and '-' signs)."""
    s = line[:68]
    total = 0
    for c in s:
        if c.isdigit():
            total += int(c)
        elif c == '-':
            total += 1
    return str(total % 10)


def _safe_piece_letter(idx):
    """Return A, B, ..., Z, AA, AB, ... for launch piece letter."""
    letters = []
    n = idx - 1
    while True:
        letters.append(chr((n % 26) + 65))
        n = n // 26 - 1
        if n < 0:
            break
    return "".join(reversed(letters))


def _normalize(vec):
    arr = np.asarray(vec, dtype=float)
    norm = np.linalg.norm(arr)
    if norm == 0:
        raise ValueError("Cannot normalize a zero vector.")
    return arr / norm


def _sample_angle_deg(rng, angle_range_deg, wrap=False):
    start_deg, stop_deg = angle_range_deg
    if wrap and stop_deg < start_deg:
        span = (stop_deg + 360.0) - start_deg
        return (start_deg + rng.uniform(0.0, span)) % 360.0
    return float(rng.uniform(start_deg, stop_deg))


def _local_frame(centralLoc, start_time):
    ground = centralLoc.at(start_time)
    up = _normalize(ground.position.km)

    east_seed = np.asarray(ground.velocity.km_per_s, dtype=float)
    if np.linalg.norm(east_seed) < 1e-12:
        spin_axis = np.array([0.0, 0.0, 1.0])
        east_seed = np.cross(spin_axis, up)
        if np.linalg.norm(east_seed) < 1e-12:
            east_seed = np.array([0.0, 1.0, 0.0])
    east = _normalize(east_seed - np.dot(east_seed, up) * up)
    north = _normalize(np.cross(up, east))
    east = _normalize(np.cross(north, up))
    return ground, north, east, up


def _line_of_sight(north, east, up, azimuth_deg, elevation_deg):
    az = math.radians(azimuth_deg)
    el = math.radians(elevation_deg)
    los = (
        math.cos(el) * math.cos(az) * north
        + math.cos(el) * math.sin(az) * east
        + math.sin(el) * up
    )
    return _normalize(los)


def _range_to_altitude(ground_pos_km, los_hat, sat_radius_km):
    b = 2.0 * float(np.dot(ground_pos_km, los_hat))
    c = float(np.dot(ground_pos_km, ground_pos_km) - sat_radius_km**2)
    discriminant = b * b - 4.0 * c
    if discriminant < 0:
        raise ValueError("Requested geometry does not intersect the target orbit radius.")
    return (-b + math.sqrt(discriminant)) / 2.0


def _tangent_basis(position_km, east_ref, north_ref):
    r_hat = _normalize(position_km)
    tangent_east = east_ref - np.dot(east_ref, r_hat) * r_hat
    if np.linalg.norm(tangent_east) < 1e-12:
        tangent_east = north_ref - np.dot(north_ref, r_hat) * r_hat
    tangent_east = _normalize(tangent_east)
    tangent_north = _normalize(np.cross(r_hat, tangent_east))
    return tangent_east, tangent_north


def generateSyntheticSatelliteInstances(
    numSat,
    centralLoc,
    azimuthRangeDeg,
    elevationRangeDeg,
    Hsat,
    start_time,
    outfile="satellite_instances.json",
    random_seed=None,
):
    """
    Generate synthetic circular-orbit satellite instances with random azimuth and
    elevation angles at the reference time.

    The generated file is JSON and is consumed by ``Network.satSelection()``.
    """
    if numSat < 1:
        raise ValueError("numSat must be >= 1")

    rng = np.random.default_rng(random_seed)
    ground, north, east, up = _local_frame(centralLoc, start_time)
    ground_pos_km = np.asarray(ground.position.km, dtype=float)
    sat_radius_km = float(np.linalg.norm(ground_pos_km) + Hsat)
    omega_rad_s = math.sqrt(398600.4418 / (sat_radius_km**3))

    satellites = []
    for idx in range(1, numSat + 1):
        azimuth_deg = _sample_angle_deg(rng, azimuthRangeDeg, wrap=True)
        elevation_deg = _sample_angle_deg(rng, elevationRangeDeg)
        los_hat = _line_of_sight(north, east, up, azimuth_deg, elevation_deg)
        slant_range_km = _range_to_altitude(ground_pos_km, los_hat, sat_radius_km)
        position_km = ground_pos_km + slant_range_km * los_hat

        tangent_east, tangent_north = _tangent_basis(position_km, east, north)
        heading_deg = float(rng.uniform(0.0, 360.0))
        heading_rad = math.radians(heading_deg)
        t_hat0 = _normalize(
            math.sin(heading_rad) * tangent_east + math.cos(heading_rad) * tangent_north
        )

        location = SyntheticOrbitLocation(
            epoch_tt=float(np.asarray(start_time.tt).reshape(-1)[0]),
            radius_km=sat_radius_km,
            omega_rad_s=omega_rad_s,
            r_hat0=_normalize(position_km),
            t_hat0=t_hat0,
        )
        record = location.to_record()
        record.update(
            {
                "name": f"SAT-{idx}",
                "azimuth_deg": azimuth_deg,
                "elevation_deg": elevation_deg,
                "heading_deg": heading_deg,
            }
        )
        satellites.append(record)

    payload = {
        "format": "synthetic_satellite_instances_v1",
        "numSat": numSat,
        "Hsat_km": Hsat,
        "azimuth_range_deg": list(azimuthRangeDeg),
        "elevation_range_deg": list(elevationRangeDeg),
        "satellites": satellites,
    }

    with open(outfile, "w", newline="\n") as f:
        json.dump(payload, f, indent=2)

    print(
        f"Generated {numSat} synthetic satellite instances with azimuth range "
        f"{azimuthRangeDeg} deg and elevation range {elevationRangeDeg} deg"
    )
    for sat in satellites:
        print(
            f"{sat['name']}: az={sat['azimuth_deg']:.2f} deg, "
            f"el={sat['elevation_deg']:.2f} deg, heading={sat['heading_deg']:.2f} deg"
        )
    print(f"Satellite instances saved to {outfile}")
    return outfile


def generateConstellationTLEs(numSat, centralLoc, zenithAngle, Hsat, start_time, outfile="satelliteTLEs.txt"):
    """
    Generate symmetric circular constellation TLEs where the zenithAngle influences orbital inclination.

    Args:
        numSat (int): number of satellites
        centralLoc: wgs84.latlon object representing central ground location
        zenithAngle (float): zenith angle in degrees (0 = overhead, 90 = horizon)
        Hsat (float): satellite altitude in km
        start_time: Skyfield Time object (ts.utc(...))
        outfile (str): output text file for generated TLEs
    """
    if numSat < 1:
        raise ValueError("numSat must be >= 1")

    Re = 6371.0  # km
    MU = 398600.4418  # km^3/s^2

    lat0 = centralLoc.latitude.degrees
    lon0 = centralLoc.longitude.degrees

    # --- Inclination depends on zenith angle ---
    # e.g., larger zenith angle → higher inclination (broader coverage)
    incl = max(0.1, min(179.9, abs(lat0) + zenithAngle))
    incl = min(incl, 179.9)

    # --- Mean motion from altitude (Kepler’s 3rd law) ---
    mean_motion = math.sqrt(MU / ((Re + Hsat)**3)) * 86400 / (2 * math.pi)

    # --- Epoch string ---
    dt = start_time.utc_datetime()
    doy = dt.timetuple().tm_yday
    seconds_into_day = dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6
    frac_int = int(round(seconds_into_day / 86400 * 1e8))
    if frac_int >= 100_000_000:
        dt += datetime.timedelta(days=1)
        doy = dt.timetuple().tm_yday
        frac_int = 0
    yy = dt.year % 100
    epoch_str = f"{yy:02d}{doy:03d}.{frac_int:08d}"

    tle_list = []
    launch_year = yy
    launch_number = 1

    # --- Generate each satellite’s TLE ---
    for idx in range(1, numSat + 1):
        satname = f"SAT-{idx}"
        norad_id = 90000 + idx
        piece = _safe_piece_letter(idx)
        int_desig = f"{launch_year:02d}{launch_number:03d}{piece}"

        # Evenly spaced right ascension of ascending node (RAAN)
        raan = ((idx - 1) * (360.0 / numSat)) % 360
        argp = 0.0
        mean_anomaly = ((idx - 1) * (360.0 / numSat)) % 360
        ecc = 0.0001000
        ecc_str = f"{int(round(ecc * 1e7)):07d}"

        # --- Line 1 ---
        line1_body = (
            f"1 {norad_id:05d}U {int_desig:<8s} {epoch_str:>17s} "
            f".00000000  00000-0  00000-0 0 "
        ).ljust(68)
        line1 = line1_body + tle_checksum(line1_body)

        # --- Line 2 ---
        line2_body = (
            f"2 {norad_id:05d} "
            f"{incl:8.4f} {raan:8.4f} {ecc_str:>7s} "
            f"{argp:8.4f} {mean_anomaly:8.4f} {mean_motion:11.8f}"
        )
        line2_full = f"{line2_body}{idx:5d}".ljust(68)
        line2 = line2_full + tle_checksum(line2_full)

        tle_list.extend([satname, line1, line2])

    with open(outfile, "w", newline="\n") as f:
        f.write("\n".join(tle_list))

    print(f"Generated {numSat} satellites with zenithAngle = {zenithAngle}°, inclination = {incl:.2f}°")
    print(f"TLEs saved to {outfile}")

    return outfile
