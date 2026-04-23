import argparse
import random
import sys
from pathlib import Path

sys.path.append("/opt/anaconda3/lib/python3.12/site-packages")

import numpy as np
from skyfield.api import load, wgs84

from satTLEgenerator import generateSyntheticSatelliteInstances
from utils import Network, Optimizer, Simulator


DEFAULT_FREQS = [2.4e9, 1.6e9]
DEFAULT_BWS = [10e6, 10e6]
DEFAULT_NS = [8, 8]
DEFAULT_RADIUS_KM = 10


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run dynamic FDD simulations for a single (J, K) configuration."
    )
    parser.add_argument("--num-sat", type=int, default=2, help="Number of satellites (J).")
    parser.add_argument("--num-ue", type=int, default=10, help="Number of UEs (K).")
    parser.add_argument("--n-iter", type=int, default=3, help="Number of Monte Carlo iterations.")
    parser.add_argument(
        "--chunk-id",
        type=int,
        default=1,
        help="Chunk index used for batch runs and output naming.",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default="Data",
        help="Root directory where experiment outputs will be stored.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Base seed for reproducible chunk runs. Each iteration uses seed + iteration index.",
    )
    parser.add_argument(
        "--freqs",
        nargs=2,
        type=float,
        default=DEFAULT_FREQS,
        metavar=("DL_FREQ", "UL_FREQ"),
        help="Two carrier frequencies in Hz.",
    )
    parser.add_argument(
        "--bandwidths",
        nargs=2,
        type=float,
        default=DEFAULT_BWS,
        metavar=("BW1", "BW2"),
        help="Two bandwidths in Hz.",
    )
    parser.add_argument(
        "--sat-antennas",
        nargs=2,
        type=int,
        default=DEFAULT_NS,
        metavar=("N1", "N2"),
        help="Satellite UPA dimensions.",
    )
    parser.add_argument("--ue-antennas", type=int, default=1, help="Number of UE antennas.")
    parser.add_argument("--sat-max-pow", type=float, default=20.0, help="Satellite power in Watts.")
    parser.add_argument("--ue-max-pow", type=float, default=2.0, help="UE power in Watts.")
    parser.add_argument(
        "--radius-km",
        type=float,
        default=DEFAULT_RADIUS_KM,
        help="UE drop radius in km.",
    )
    parser.add_argument("--hsat-km", type=float, default=500.0, help="Satellite altitude in km.")
    parser.add_argument("--central-lat", type=float, default=53.0793, help="Central latitude in degrees.")
    parser.add_argument("--central-lon", type=float, default=8.8017, help="Central longitude in degrees.")
    parser.add_argument("--start-year", type=int, default=2025, help="Simulation start year.")
    parser.add_argument("--start-month", type=int, default=1, help="Simulation start month.")
    parser.add_argument("--start-day", type=int, default=1, help="Simulation start day.")
    parser.add_argument(
        "--azimuth-range",
        nargs=2,
        type=float,
        default=(0.0, 360.0),
        metavar=("AZ_MIN", "AZ_MAX"),
        help="Satellite azimuth sampling range in degrees.",
    )
    parser.add_argument(
        "--elevation-range",
        nargs=2,
        type=float,
        default=(30.0, 80.0),
        metavar=("EL_MIN", "EL_MAX"),
        help="Satellite elevation sampling range in degrees.",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Write a chunk-level CDF plot in addition to the raw chunk JSON.",
    )
    parser.add_argument(
        "--plot-format",
        type=str,
        default="eps",
        help="Plot format for chunk-level plots, for example eps or png.",
    )
    return parser


def config_directory(output_root, num_sat, num_ue):
    return Path(output_root) / "experiments" / f"J_{num_sat:02d}_K_{num_ue:03d}"


def chunk_label(chunk_id):
    return f"chunk_{chunk_id:03d}"


def run_simulation(args):
    if args.num_ue < args.num_sat:
        raise ValueError("numUE must be greater than or equal to numSat.")

    ts = load.timescale()
    start_time = ts.utc(args.start_year, args.start_month, args.start_day)
    central_loc = wgs84.latlon(args.central_lat, args.central_lon)
    ant_spacing = tuple(3e8 / (2 * freq) for freq in args.freqs)

    config_dir = config_directory(args.output_root, args.num_sat, args.num_ue)
    chunk_dir = config_dir / "chunks"
    plot_dir = config_dir / "plots"
    runtime_dir = config_dir / "runtime"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    plot_dir.mkdir(parents=True, exist_ok=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    sat_instance_file = runtime_dir / f"{chunk_label(args.chunk_id)}_satellites.json"
    result_file = chunk_dir / f"{chunk_label(args.chunk_id)}.json"
    plot_file = plot_dir / f"{chunk_label(args.chunk_id)}.{args.plot_format}"

    def layout_callback(iteration_idx):
        if args.seed is not None:
            iter_seed = args.seed + iteration_idx
            np.random.seed(iter_seed)
            random.seed(iter_seed)
            sat_seed = args.seed + 100000 + iteration_idx
        else:
            sat_seed = None

        generateSyntheticSatelliteInstances(
            numSat=args.num_sat,
            centralLoc=central_loc,
            azimuthRangeDeg=tuple(args.azimuth_range),
            elevationRangeDeg=tuple(args.elevation_range),
            Hsat=args.hsat_km,
            start_time=start_time,
            outfile=str(sat_instance_file),
            random_seed=sat_seed,
        )

    if args.seed is not None:
        np.random.seed(args.seed)
        random.seed(args.seed)

    network = Network(args.num_sat, args.num_ue, central_loc, args.radius_km, start_time)
    optimizer = Optimizer("fractionalProgramming")
    simulator = Simulator(
        network,
        optimizer,
        args.freqs,
        args.bandwidths,
        args.sat_antennas,
        args.ue_antennas,
        args.sat_max_pow,
        args.ue_max_pow,
        ant_spacing,
        args.n_iter,
        str(sat_instance_file),
        layout_callback=layout_callback,
    )

    metadata = {
        "numSat": args.num_sat,
        "numUE": args.num_ue,
        "nIter": args.n_iter,
        "chunkId": args.chunk_id,
        "seed": args.seed,
        "freqs": list(args.freqs),
        "bandwidths": list(args.bandwidths),
        "satAntennas": list(args.sat_antennas),
        "ueAntennas": args.ue_antennas,
        "satMaxPow": args.sat_max_pow,
        "ueMaxPow": args.ue_max_pow,
        "radiusKm": args.radius_km,
        "hsatKm": args.hsat_km,
        "centralLat": args.central_lat,
        "centralLon": args.central_lon,
        "startDate": f"{args.start_year:04d}-{args.start_month:02d}-{args.start_day:02d}",
        "azimuthRangeDeg": list(args.azimuth_range),
        "elevationRangeDeg": list(args.elevation_range),
    }

    simulator.run(
        checkpoint_file=result_file,
        metadata=metadata,
        plot_file=plot_file if args.plot else None,
    )

    print(f"Saved chunk results to {result_file}")
    return result_file


def main():
    args = build_parser().parse_args()
    run_simulation(args)


if __name__ == "__main__":
    main()
