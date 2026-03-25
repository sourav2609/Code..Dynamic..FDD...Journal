#!/usr/bin/env python3

import argparse
import json
import math
import os
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate chunked batch jobs for (J, K) simulation sweeps and run them in parallel."
    )
    parser.add_argument("--j-values", nargs="+", type=int, required=True, help="Satellite counts.")
    parser.add_argument("--k-values", nargs="+", type=int, required=True, help="UE counts.")
    parser.add_argument(
        "--total-iterations",
        type=int,
        default=200,
        help="Total iterations per (J, K) configuration.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=10,
        help="Iterations per chunk job.",
    )
    parser.add_argument(
        "--jobs-root",
        type=str,
        default="Data/jobs",
        help="Directory where shell job files will be generated.",
    )
    parser.add_argument(
        "--output-root",
        type=str,
        default="Data",
        help="Root directory passed through to main.py for results.",
    )
    parser.add_argument(
        "--python-bin",
        type=str,
        default="python3",
        help="Python executable used inside generated job scripts.",
    )
    parser.add_argument(
        "--seed-base",
        type=int,
        default=100000,
        help="Base seed used to derive reproducible chunk seeds.",
    )
    parser.add_argument(
        "--radius-km",
        type=float,
        default=None,
        help="Optional UE drop radius forwarded to main.py. If omitted, main.py uses its own constant.",
    )
    parser.add_argument(
        "--plot-chunks",
        action="store_true",
        help="Generate chunk-level plots for every job.",
    )
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="Only generate the job scripts without executing them.",
    )
    parser.add_argument(
        "--skip-merge",
        action="store_true",
        help="Skip the final merge step after all generated jobs finish.",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=None,
        help="Maximum number of local jobs to run concurrently. Defaults to CPU count.",
    )
    return parser


def write_script(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o755)


def build_chunk_command(args, num_sat, num_ue, iter_count, chunk_idx, seed):
    command = [
        args.python_bin,
        "main.py",
        "--num-sat",
        str(num_sat),
        "--num-ue",
        str(num_ue),
        "--n-iter",
        str(iter_count),
        "--chunk-id",
        str(chunk_idx),
        "--seed",
        str(seed),
        "--output-root",
        args.output_root,
    ]
    if args.radius_km is not None:
        command.extend(["--radius-km", str(args.radius_km)])
    if args.plot_chunks:
        command.append("--plot")
    return command


def create_manifest(args, jobs_root, repo_root):
    num_chunks = math.ceil(args.total_iterations / args.chunk_size)
    manifest = {
        "repo_root": str(repo_root),
        "output_root": args.output_root,
        "experiments_root": f"{args.output_root}/experiments",
        "j_values": args.j_values,
        "k_values": args.k_values,
        "total_iterations": args.total_iterations,
        "chunk_size": args.chunk_size,
        "num_chunks": num_chunks,
        "jobs": [],
    }

    root_run_lines = ["#!/bin/sh", "set -e"]
    root_parallel_lines = [
        "#!/bin/sh",
        "set -e",
        f'find {shlex.quote(str(jobs_root))} -path "*/chunk_*.sh" -print | sort | '
        f'xargs -n 1 -P {max(1, args.max_parallel or (os.cpu_count() or 1))} sh',
    ]

    config_counter = 0
    for num_sat in args.j_values:
        for num_ue in args.k_values:
            config_counter += 1
            config_job_dir = jobs_root / f"J_{num_sat:02d}_K_{num_ue:03d}"
            log_dir = config_job_dir / "logs"
            config_run_lines = ["#!/bin/sh", "set -e"]
            remaining = args.total_iterations

            for chunk_idx in range(1, num_chunks + 1):
                iter_count = min(args.chunk_size, remaining)
                remaining -= iter_count

                seed = args.seed_base + config_counter * 100000 + chunk_idx * 100
                command_parts = build_chunk_command(
                    args, num_sat, num_ue, iter_count, chunk_idx, seed
                )
                quoted_cmd = " ".join(shlex.quote(part) for part in command_parts)
                script_path = config_job_dir / f"chunk_{chunk_idx:03d}.sh"
                write_script(
                    script_path,
                    [
                        "#!/bin/sh",
                        "set -e",
                        f"cd {shlex.quote(str(repo_root))}",
                        quoted_cmd,
                    ],
                )

                config_run_lines.append(shlex.quote(str(script_path)))
                root_run_lines.append(shlex.quote(str(script_path)))

                manifest["jobs"].append(
                    {
                        "numSat": num_sat,
                        "numUE": num_ue,
                        "chunkId": chunk_idx,
                        "iterations": iter_count,
                        "seed": seed,
                        "script": str(script_path),
                        "log_file": str(log_dir / f"chunk_{chunk_idx:03d}.log"),
                        "command": quoted_cmd,
                        "command_parts": command_parts,
                    }
                )

            write_script(config_job_dir / "run_all_chunks.sh", config_run_lines)

    write_script(jobs_root / "run_all.sh", root_run_lines)
    write_script(jobs_root / "run_all_parallel.sh", root_parallel_lines)
    return manifest
def run_single_job(job, repo_root):
    log_path = Path(job["log_file"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", newline="\n") as log_file:
        result = subprocess.run(
            ["sh", job["script"]],
            cwd=repo_root,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    if result.returncode != 0:
        raise RuntimeError(
            f"Job failed for J={job['numSat']}, K={job['numUE']}, chunk={job['chunkId']}. "
            f"See log: {log_path}"
        )
    return job


def run_generated_jobs_parallel(manifest, repo_root, max_parallel):
    total_jobs = len(manifest["jobs"])
    max_workers = max_parallel or os.cpu_count() or 1
    max_workers = max(1, min(max_workers, total_jobs))

    print(f"Running {total_jobs} jobs locally with max_parallel={max_workers}")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(run_single_job, job, repo_root): job
            for job in manifest["jobs"]
        }
        completed = 0
        for future in as_completed(future_map):
            job = future_map[future]
            future.result()
            completed += 1
            print(
                f"Completed {completed}/{total_jobs}: "
                f"J={job['numSat']}, K={job['numUE']}, chunk={job['chunkId']}"
            )


def merge_results(args, repo_root):
    subprocess.run(
        [
            args.python_bin,
            "scripts/merge_experiment_results.py",
            "--experiments-root",
            f"{args.output_root}/experiments",
        ],
        check=True,
        cwd=repo_root,
    )


def main():
    args = build_parser().parse_args()
    if args.total_iterations < 1:
        raise ValueError("total-iterations must be positive.")
    if args.chunk_size < 1:
        raise ValueError("chunk-size must be positive.")

    repo_root = Path(__file__).resolve().parent.parent
    jobs_root = Path(args.jobs_root)
    jobs_root.mkdir(parents=True, exist_ok=True)

    manifest = create_manifest(args, jobs_root, repo_root)
    manifest_path = jobs_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"Generated {len(manifest['jobs'])} job scripts under {jobs_root}")

    if args.generate_only:
        print(f"Local parallel launcher: {jobs_root / 'run_all_parallel.sh'}")
        return

    run_generated_jobs_parallel(manifest, repo_root, args.max_parallel)

    if not args.skip_merge:
        merge_results(args, repo_root)
        print(f"Merged results are available under {Path(args.output_root) / 'experiments'}")


if __name__ == "__main__":
    main()
