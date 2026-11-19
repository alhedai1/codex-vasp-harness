# Codex VASP Harness

VASP tools for checking inputs, submitting jobs and validating results, with a
controller that waits for Slurm jobs and automatically starts Codex to continue.

## 1. Clone

From your existing workspace root:

```bash
git clone --branch v0.1.3 https://github.com/alhedai1/codex-vasp-harness.git harness-source
```

## 2. Copy

Back up any existing tools/vasp/ and controller/ folders first. Keep your
calculations, skills and environment.

```bash
mkdir -p tools
cp -R harness-source/tools/vasp tools/
cp -R harness-source/controller .
```

Continue from the workspace root, not inside harness-source/.

## 3. Configure

Edit tools/vasp/submit.slurm for your cluster: partition, resources and MPI launcher.
Set your VASP executable path in the active environment:

```bash
export VASP_BIN=/absolute/path/to/vasp_std
```

Requires Python 3.11+, numpy, pymatgen, Slurm, and an installed/authenticated Codex
CLI. Use your existing environment. If needed: `python -m pip install numpy pymatgen`.
The detached controller launch uses Linux user systemd services; verify
`systemctl --user is-system-running`. Supply your own licensed VASP and POTCARs.

## 4. Update AGENTS.md

Merge **harness-source/AGENTS.example.md** into your workspace's AGENTS.md.
Replace older harness instructions; keep your other lab-specific instructions.

## 5. Run through Codex

> Prepare and run a small static bulk-Si calculation using the VASP harness.
> Launch the controller to collect and validate it automatically and write a
> short report. No additional calculations after this test.

The workflow is check -> submit -> controller waits -> fresh Codex collects
and reports. Inputs/settings and fingerprints go into prepared.json; job IDs
into submission.json; validated results into result.json. The controller state
and logs are in projects/<task>/workflow/, with the report in the task directory.

The controller is part of the harness. It waits for the whole batch, including
failed jobs. It does not resume the original sidebar chat or send notifications.
Failures stop automation for inspection; there is no automatic retry.

Supported: fresh-start periodic PBE/PBEsol PAW static calculations and relaxations
(IBRION=1/2/3), uniform k meshes, whole-atom fixed/free constraints. Successful
execution checks do not establish numerical convergence or physical accuracy.
