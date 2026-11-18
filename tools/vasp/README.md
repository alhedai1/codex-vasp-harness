# VASP command reference

Run from the workspace root using Python 3.11+ with numpy and pymatgen:

```text
python tools/vasp/cli.py check   JOB_DIR
python tools/vasp/cli.py submit  JOB_DIR
python tools/vasp/cli.py status  JOB_DIR
python tools/vasp/cli.py collect JOB_DIR
```

Inputs: nonempty POSCAR, INCAR, KPOINTS, real licensed POTCAR and submit.slurm.
Check requires explicit ENCUT, EDIFF, NSW and GGA=PE/PS; relaxations require
IBRION=1/2/3 and nonzero EDIFFG. Cutoff must meet each potential ENMAX. Uniform
Gamma/Monkhorst meshes only. Whole-atom TTT/FFF constraints and fresh electronic
starts (ISTART=0, ICHARG=2) only. Hybrid, meta-GGA and SOC are outside scope.

Check saves settings, constraints, potential identities, warnings and SHA256
fingerprints in prepared.json. It rejects duplicate INCAR tags, inconsistent
species/potential order and existing outputs. Check does not select or converge
the scientific settings. Read potential warnings before submitting.

Submit verifies frozen hashes, locks the submission and refuses prior outputs,
submissions or attempted submissions. submission_attempt.json is saved before
sbatch; do not automatically delete it after an ambiguous interruption. Inspect
the scheduler first. The batch template includes a second overwrite guard.

Status uses squeue, scontrol, then sacct, recording observations in scheduler.json.
A saved terminal observation is reused if Slurm expires the job record; UNKNOWN
alone never implies completion. Slurm access must be available outside a sandbox.

Collect requires COMPLETED/0:0, valid XML, matching starting geometry, explicit
scientific INCAR controls, mesh and potential identities. Some VASP builds omit
KPAR/NCORE/NPAR in XML; these remain input-hash protected. SCF convergence is
required at every ionic step. Steps reaching NELM are conservatively rejected.
Relaxations require ionic convergence and, for negative EDIFFG, the force target
on free atoms. Final CONTCAR must match XML; static jobs may fall back to POSCAR.
Finite energy/forces, validation errors/warnings and output fingerprints are
saved to result.json. This does not check every possible physical failure.

Exit codes: 0 command success; 1 error/failed validation; 2 unfinished/unknown
when collecting. Status itself returns a scheduler observation, not validation.
For other supported needs, extend and test deliberately rather than bypassing
validation silently. This release does not implement Bader readiness checks,
protocol files or cross-calculation comparison.
