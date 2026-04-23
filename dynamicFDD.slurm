#!/bin/bash
#SBATCH -J myjob                              # Job name
#SBATCH -o myjob-%j.out                       # Output file (%j expands to job ID)
#SBATCH -e myjob-%j.err                       # Error file (%j expands to job ID)
#SBATCH -N 1                                  # Number of nodes
#SBATCH -n 1                                  # Number of tasks
#SBATCH -c 1                                  # CPUs per task
#SBATCH -t 10-23:01:00                         # Time limit (days-hrs:min:sec)
#SBATCH -p wiss                               # Queue or partition name
#SBATCH --mem=128G                             # Memory requirement
#SBATCH --mail-user=user@ant.uni-bremen.de    # Email address to which success or failure messages are sent
#SBATCH --mail-type=ALL                       # Select type of email messages to be sent (all)

# Load modules / set environment variables
HOSTNAME=$(hostname)

# Execute the job
srun echo $HOSTNAME
srun python3 scripts/generate_experiment_jobs.py \
  --j-values 3 \
  --k-values 10 15 20 25 30 40 \
  --total-iterations 200 \
  --chunk-size 2 \
  --jobs-root Data/jobs \
  --output-root Data \
  --max-parallel 600
wait  
echo "$(date): Finished jobs!"
