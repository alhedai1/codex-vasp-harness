#!/bin/bash
#SBATCH --job-name=vasp-tutorial
#SBATCH --partition=local
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:10:00
#SBATCH --output=slurm-%j.out
#SBATCH --error=slurm-%j.err

# EDIT the partition/resources above for your cluster before checking inputs.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
: "${VASP_BIN:?Export VASP_BIN as the absolute path to your licensed VASP executable}"
test -x "$VASP_BIN"
for input in POSCAR INCAR KPOINTS POTCAR; do
    test -s "$input"
done
for output in OUTCAR OSZICAR vasprun.xml CONTCAR WAVECAR CHGCAR; do
    if [[ -e "$output" ]]; then
        echo "Refusing to overwrite $output; use a fresh directory." >&2
        exit 1
    fi
done
# Adapt this MPI launch line to the cluster's documented VASP launcher.
mpirun -np "${SLURM_NTASKS}" "$VASP_BIN" > "vasp-${SLURM_JOB_ID}.out" 2>&1
