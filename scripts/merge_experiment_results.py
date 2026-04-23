#!/usr/bin/env python3

import argparse
import csv
import json
from pathlib import Path

import numpy as np


CASE_ORDER = (
    "bestSolution_wspin",
    "bestSolution_spin0",
    "bestSolution_spin1",
    "bestSolution_randSpin",
)
CASE_PLOT_STYLES = {
    "bestSolution_wspin": ("Best Over All Spins", "blue"),
    "bestSolution_spin0": ("All-Zero Spin", "red"),
    "bestSolution_spin1": ("All-One Spin", "green"),
    "bestSolution_randSpin": ("Random Spin-0/1", "orange"),
}


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


def extract_case_results(payload):
    if "results_by_case" in payload:
        results_by_case = payload["results_by_case"]
        return {
            case_name: list(results_by_case.get(case_name, [])) for case_name in CASE_ORDER
        }

    # Backward compatibility for older two-series chunk files.
    return {
        "bestSolution_wspin": list(payload.get("results_with_spin", [])),
        "bestSolution_spin0": [],
        "bestSolution_spin1": [],
        "bestSolution_randSpin": list(payload.get("results_without_spin", [])),
    }


def plot_results(results_by_case, output_path):
    import matplotlib.pyplot as plt

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(8, 6))
    for case_name in CASE_ORDER:
        case_values = results_by_case.get(case_name, [])
        if not case_values:
            continue
        sorted_values = np.sort(case_values)
        cdf_values = np.arange(1, len(sorted_values) + 1) / len(sorted_values)
        label, color = CASE_PLOT_STYLES[case_name]
        plt.plot(sorted_values, cdf_values, label=label, color=color)
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

        merged_results_by_case = {case_name: [] for case_name in CASE_ORDER}
        chunk_metadata = []

        for chunk_file in chunk_files:
            payload = json.loads(chunk_file.read_text())
            chunk_results_by_case = extract_case_results(payload)
            for case_name in CASE_ORDER:
                merged_results_by_case[case_name].extend(chunk_results_by_case[case_name])
            chunk_metadata.append(payload.get("metadata", {}))

        merged_dir = config_dir / "merged"
        merged_dir.mkdir(parents=True, exist_ok=True)

        num_results = max(
            (len(merged_results_by_case[case_name]) for case_name in CASE_ORDER),
            default=0,
        )

        merged_payload = {
            "config": chunk_metadata[0] if chunk_metadata else {},
            "numChunks": len(chunk_files),
            "numResults": num_results,
            "chunkFiles": [str(path) for path in chunk_files],
            "result_case_order": list(CASE_ORDER),
            "results_by_case": merged_results_by_case,
            "results_with_spin": merged_results_by_case["bestSolution_wspin"],
            "results_without_spin": merged_results_by_case["bestSolution_randSpin"],
        }
        merged_file = merged_dir / "results.json"
        merged_file.write_text(json.dumps(merged_payload, indent=2) + "\n")

        if any(merged_results_by_case[case_name] for case_name in CASE_ORDER):
            summary_row = {
                "config": config_dir.name,
                "num_chunks": len(chunk_files),
                "num_results": num_results,
                "merged_file": str(merged_file),
            }
            for case_name in CASE_ORDER:
                case_values = merged_results_by_case[case_name]
                summary_row[f"mean_{case_name}"] = (
                    float(np.mean(case_values)) if case_values else None
                )
                summary_row[f"max_{case_name}"] = (
                    float(np.max(case_values)) if case_values else None
                )
            summary_rows.append(summary_row)

            if not args.skip_plots:
                plot_results(
                    merged_results_by_case,
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
