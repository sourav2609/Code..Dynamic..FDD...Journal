#!/usr/bin/env python3

import argparse
import csv
import json
from pathlib import Path

import numpy as np


def build_parser():
    parser = argparse.ArgumentParser(
        description="Merge chunked experiment JSON files and generate per-configuration summaries."
    )
    parser.add_argument(
        "--experiments-root",
        type=str,
        default="Data/experiments",
        help="Root directory containing J_*/K_* experiment outputs.",
    )
    parser.add_argument(
        "--plot-format",
        type=str,
        default="eps",
        help="Output format for merged CDF plots.",
    )
    parser.add_argument(
        "--skip-plots",
        action="store_true",
        help="Skip merged CDF plot generation.",
    )
    return parser


def plot_results(results_with_spin, results_without_spin, output_path):
    import matplotlib.pyplot as plt

    sorted_spin = np.sort(results_with_spin)
    sorted_no_spin = np.sort(results_without_spin)
    cdf_spin = np.arange(1, len(sorted_spin) + 1) / len(sorted_spin)
    cdf_no_spin = np.arange(1, len(sorted_no_spin) + 1) / len(sorted_no_spin)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(8, 6))
    plt.plot(sorted_spin, cdf_spin, label="With Spin", color="blue")
    plt.plot(sorted_no_spin, cdf_no_spin, label="Without Spin", color="red")
    plt.xlabel("Sum Rate")
    plt.ylabel("CDF")
    plt.grid(True)
    plt.legend()
    plt.savefig(output_path, format=output_path.suffix.lstrip(".") or None)
    plt.close()


def main():
    args = build_parser().parse_args()
    experiments_root = Path(args.experiments_root)
    summary_rows = []

    if not experiments_root.exists():
        raise FileNotFoundError(f"Experiments root not found: {experiments_root}")

    for config_dir in sorted(p for p in experiments_root.iterdir() if p.is_dir()):
        chunk_dir = config_dir / "chunks"
        if not chunk_dir.exists():
            continue

        chunk_files = sorted(chunk_dir.glob("chunk_*.json"))
        if not chunk_files:
            continue

        merged_with_spin = []
        merged_without_spin = []
        chunk_metadata = []

        for chunk_file in chunk_files:
            payload = json.loads(chunk_file.read_text())
            merged_with_spin.extend(payload.get("results_with_spin", []))
            merged_without_spin.extend(payload.get("results_without_spin", []))
            chunk_metadata.append(payload.get("metadata", {}))

        merged_dir = config_dir / "merged"
        merged_dir.mkdir(parents=True, exist_ok=True)

        merged_payload = {
            "config": chunk_metadata[0] if chunk_metadata else {},
            "numChunks": len(chunk_files),
            "numResults": len(merged_with_spin),
            "chunkFiles": [str(path) for path in chunk_files],
            "results_with_spin": merged_with_spin,
            "results_without_spin": merged_without_spin,
        }
        merged_file = merged_dir / "results.json"
        merged_file.write_text(json.dumps(merged_payload, indent=2) + "\n")

        if merged_with_spin and merged_without_spin:
            summary_rows.append(
                {
                    "config": config_dir.name,
                    "num_chunks": len(chunk_files),
                    "num_results": len(merged_with_spin),
                    "mean_with_spin": float(np.mean(merged_with_spin)),
                    "mean_without_spin": float(np.mean(merged_without_spin)),
                    "max_with_spin": float(np.max(merged_with_spin)),
                    "max_without_spin": float(np.max(merged_without_spin)),
                    "merged_file": str(merged_file),
                }
            )

            if not args.skip_plots:
                plot_results(
                    merged_with_spin,
                    merged_without_spin,
                    merged_dir / f"cdf_merged.{args.plot_format}",
                )

    if summary_rows:
        summary_file = experiments_root / "summary.csv"
        with open(summary_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            writer.writeheader()
            writer.writerows(summary_rows)
        print(f"Wrote merged summary to {summary_file}")
    else:
        print("No experiment chunks found to merge.")


if __name__ == "__main__":
    main()
