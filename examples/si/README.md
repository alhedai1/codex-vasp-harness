# Small silicon execution example

Two-atom diamond-Si primitive cell with fixed conventional a=5.43 angstrom.
Static nonmagnetic PBE, ENCUT=400 eV, Gamma 6x6x6, EDIFF=1e-6 eV,
Gaussian smearing 0.05 eV, NSW=0. These are starting settings for testing the
harness, not a numerical-convergence study. Supply a compatible locally licensed
Si PAW_PBE POTCAR. Potential versions can change the energy; no exact energy
match is promised. Never distribute that POTCAR with this repository.

The environment-specific original smoke test used one MPI task on Slurm and
successfully exercised check, submit and collect. This repository includes only
input geometry/settings, not the outputs or pseudopotential from that run.
