# Spinning Frequency Bands

## Author

**Sourav Mukherjee**  
PhD Student  
Room N2410  
University of Bremen  
Department of Communications Engineering (Arbeitsbereich Nachrichtentechnik)  
Otto-Hahn-Allee NW1  
D-28359 Bremen, Germany  
📧 [mukherjee@ant.uni-bremen.de](mailto:mukherjee@ant.uni-bremen.de)

---
### License
If you use the code in any way, please cite the original paper. 

---

## Paper

**Title**: *Spinning Bands for LEO Satellites: Interference Mitigation Through Dynamic Downlink-Uplink Band Allocation*  

---

## Requirements

### Python Packages

- `numpy`
- `skyfield`
- `matplotlib`
- `cvxpy`
- `mosek`

`cvxpy` is configured to solve with `MOSEK`, so a working MOSEK installation and license are required.

Example installation:

```bash
pip install numpy skyfield matplotlib cvxpy mosek
```

## How To Run

### 1. Run A Single Configuration

Use [`main.py`](/Users/souravmukherjee/Documents/GitHub/CoDexCodes/dynamic%20FDD/dynamic%20FDD%20-%20Chatgpt%20Accelerated/main.py) to run one `(J, K)` case directly.

Example:

```bash
python3 main.py \
  --num-sat 2 \
  --num-ue 10 \
  --n-iter 5 \
  --chunk-id 1 \
  --output-root Data
```

Main arguments:

- `--num-sat`: number of satellites `J`
- `--num-ue`: number of UEs `K`
- `--n-iter`: number of simulation iterations for this run
- `--chunk-id`: chunk number used in output filenames
- `--output-root`: where results are written
- `--seed`: reproducible base seed
- `--plot`: also save a chunk-level CDF plot

### 2. Run Multiple Configurations In Parallel

Use [`scripts/generate_experiment_jobs.py`](/Users/souravmukherjee/Documents/GitHub/CoDexCodes/dynamic%20FDD/dynamic%20FDD%20-%20Chatgpt%20Accelerated/scripts/generate_experiment_jobs.py).

This script now does three things automatically:

1. Generates chunk job scripts
2. Runs the chunk jobs in parallel locally
3. Merges the chunk outputs at the end

Example:

```bash
python3 scripts/generate_experiment_jobs.py \
  --j-values 1 2 3 4 \
  --k-values 10 15 20 25 30 40 \
  --total-iterations 200 \
  --chunk-size 10 \
  --jobs-root Data/jobs \
  --output-root Data \
  --max-parallel 4
```

Meaning of the main batch arguments:

- `--j-values`: list of `J` values
- `--k-values`: list of `K` values
- `--total-iterations`: total iterations per configuration
- `--chunk-size`: iterations per chunk job
- `--jobs-root`: where generated shell scripts and logs are stored
- `--output-root`: where simulation results are stored
- `--max-parallel`: maximum number of chunk jobs running at the same time

Example:

- `--total-iterations 200`
- `--chunk-size 10`

means each `(J, K)` configuration is split into `20` chunk jobs, each running `10` iterations.

### 3. Generate Scripts Only

If you only want the shell scripts without executing them:

```bash
python3 scripts/generate_experiment_jobs.py \
  --j-values 1 2 \
  --k-values 10 15 \
  --total-iterations 40 \
  --chunk-size 10 \
  --jobs-root Data/jobs \
  --output-root Data \
  --generate-only
```

## Where Results Are Stored

If `--output-root Data` is used, results are written under:

```text
Data/experiments/
```

For a configuration `(J=2, K=15)`, the structure is:

```text
Data/experiments/J_02_K_015/
├── chunks/
│   ├── chunk_001.json
│   ├── chunk_002.json
│   └── ...
├── merged/
│   ├── results.json
│   └── cdf_merged.eps
├── plots/
│   └── chunk_001.eps
└── runtime/
    ├── chunk_001_satellites.json
    └── ...
```

### Chunk Results

Each chunk file is saved here:

```text
Data/experiments/J_XX_K_YYY/chunks/chunk_ZZZ.json
```

Each chunk file is checkpointed after every completed iteration and overwritten in the same file.  
If you open the file during execution, you can see:

- `status`
- `completed_iterations`
- `target_iterations`
- `iteration_results`
- `results_with_spin`
- `results_without_spin`

So if a run fails midway, the file still shows how many iterations were already completed and their values.

### Runtime Satellite Instances

For each chunk, the generated satellite geometry is stored in:

```text
Data/experiments/J_XX_K_YYY/runtime/chunk_ZZZ_satellites.json
```

### Merged Results

After all chunks finish, merged outputs are stored in:

```text
Data/experiments/J_XX_K_YYY/merged/results.json
Data/experiments/J_XX_K_YYY/merged/cdf_merged.eps
```

The overall summary across configurations is stored in:

```text
Data/experiments/summary.csv
```

## Where Job Files And Logs Are Stored

Generated shell scripts and local execution logs are stored under:

```text
Data/jobs/
```

Example:

```text
Data/jobs/J_02_K_015/
├── chunk_001.sh
├── chunk_002.sh
├── run_all_chunks.sh
└── logs/
    ├── chunk_001.log
    └── chunk_002.log
```

Useful generated files:

- `Data/jobs/run_all.sh`: run all chunk scripts sequentially
- `Data/jobs/run_all_parallel.sh`: run all chunk scripts in parallel
- `Data/jobs/manifest.json`: manifest of all generated chunk jobs

## Notes

- The default UE drop radius is controlled in [`main.py`](/Users/souravmukherjee/Documents/GitHub/CoDexCodes/dynamic%20FDD/dynamic%20FDD%20-%20Chatgpt%20Accelerated/main.py) by `DEFAULT_RADIUS_KM`.
- The default local parallelism is based on CPU count if `--max-parallel` is not specified.
- If you want a specific radius, pass `--radius-km ...` explicitly.

## Project Structure

```text
root/
├── main.py
├── satTLEgenerator.py
├── scripts/
│   ├── generate_experiment_jobs.py
│   └── merge_experiment_results.py
├── Data/
├── Results/
└── utils/
    ├── __init__.py
    ├── components.py
    ├── helper.py
    ├── network.py
    ├── optimizer.py
    ├── simulator.py
    └── synthetic_orbit.py
```
