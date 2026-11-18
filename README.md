# Codex VASP Harness

A small teaching example for materials researchers using Codex with VASP and
Slurm. Codex chooses the calculation; reusable commands check inputs, submit
jobs, and validate/record results. An optional controller handles waiting and
starts a fresh Codex process after a batch finishes.

## What is included

- `tools/vasp/cli.py`: `check`, `submit`, `status`, `collect`.
- `tools/vasp/submit.slurm`: editable cluster submission template.
- `examples/si/`: public two-atom diamond-Si input geometry and tutorial settings.
- `AGENTS.md`: instructions routing Codex through the tools.
- `controller/`: optional advanced background continuation.
- `tests/`: acceptance-gate tests with mocked parser/scheduler boundaries; no
  licensed potentials or live scheduler required.

No VASP executable, POTCAR, credentials, or calculation outputs are distributed.
The MIT license applies to this code; obtain VASP and potentials separately.

## 1. Get the code

Get the version used in this tutorial:

```bash
git clone --branch v0.1.0 https://github.com/alhedai1/codex-vasp-harness.git
cd codex-vasp-harness
```

Or download the [v0.1.0 release](https://github.com/alhedai1/codex-vasp-harness/releases/tag/v0.1.0).
Run the commands below from the repository root. For a versioned workshop use
the tutorial tag rather than an evolving branch. Link the slides to that release.

For an existing workspace, copy `tools/vasp/` into its `tools/` directory and
merge the relevant instructions from AGENTS.md. Copy `controller/` only for
background continuation. Paths resolve relative to the installed tools' root.

## 2. Prepare the environment

Linux, Python **3.11+**, numpy, pymatgen, and Slurm command-line tools are required.
Use your lab's existing compatible environment, or create an isolated one:

```bash
conda create -n codex-vasp-harness python=3.11 pip
conda activate codex-vasp-harness
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

These dependencies are for the harness, not a VASP installation. The environment
used to verify this snapshot is recorded in docs/tested-environment.txt.

## 3. Configure your cluster and the Si example

Edit `tools/vasp/submit.slurm`: set partition, task count, memory, walltime and
the MPI launcher your cluster supports. The one-task/ten-minute template is only
a small demonstration. Load your VASP/MPI modules if required by your cluster.
Set the executable path in the environment before submission:

```bash
export VASP_BIN=/absolute/path/to/your/licensed/vasp_std
mkdir -p projects/Si_example/static/run01
cp examples/si/POSCAR examples/si/INCAR examples/si/KPOINTS projects/Si_example/static/run01/
cp tools/vasp/submit.slurm projects/Si_example/static/run01/
```

Place the **real authorized Si PAW_PBE POTCAR** in that job directory yourself.
It must match POSCAR species order. Do not download an arbitrary potential,
create a placeholder, or commit the licensed file. Read examples/si/README.md.

## 4. Check, submit, collect

```bash
python tools/vasp/cli.py check projects/Si_example/static/run01
python tools/vasp/cli.py submit projects/Si_example/static/run01
python tools/vasp/cli.py status projects/Si_example/static/run01
# After a terminal scheduler state:
python tools/vasp/cli.py collect projects/Si_example/static/run01
```

| Command | What it verifies/records | Record |
|---|---|---|
| check | Input consistency, method/settings, potential identities, file fingerprints | prepared.json |
| submit | Checked inputs unchanged; no previous submission or outputs | submission.json |
| status | Scheduler observation and exit code | scheduler.json |
| collect | Scheduler outcome, output consistency, SCF/ionic convergence, energies/forces | result.json |

`submit` requires the prior input snapshot and rechecks its hashes internally.
Inputs cannot be changed after check; create a new directory for changed settings.
Submission attempts are persisted before sbatch so interrupted submission cannot
silently launch duplicate jobs. Inspect Slurm before manually recovering an attempt.

Successful collection reports `status: validated`, `electronic_converged: true`,
and an energy in eV per cell. This static example has `ionic_converged: null`.
Do not present a successful run as cutoff/k-point convergence or physical validation.
See tools/vasp/README.md for the complete supported scope and exit codes.

## 5. Demonstrate a rejected change (no new calculation needed)

Use another disposable fresh input directory, copy the example and real local
POTCAR into it, and run check. Change ENCUT in its INCAR, then run submit.
The tool refuses the changed inputs **before sbatch**. Do not edit a completed run.
A file hash is a fingerprint connecting each result to the checked input files.

This enforces consistency within the tool workflow, not a security boundary:
Codex with write/shell access can modify or bypass scripts. AGENTS.md routes it
through the interface; validation code supplies deterministic acceptance gates.

## Optional: unattended continuation

Follow controller/README.md. Codex saves the objective/state and starts a detached
controller. It waits for the entire submitted batch, then starts fresh Codex to
collect, interpret, report, and continue or stop. It does not update the original
sidebar conversation. **Notifications are not implemented.** Status, reports,
and logs are written to the task directory.

## Scope of this tutorial release

Fresh-start periodic PBE/PBEsol PAW calculations, explicit uniform k meshes,
static jobs and IBRION=1/2/3 relaxations; whole-atom fixed/free constraints.
Electronic restarts, partial-direction constraints and unsupported methods are
rejected explicitly. No automatic scientific recovery is performed.

Configurable scientific protocols and cross-calculation `compare` are proposed
next steps, **not commands in this release**. It is not a universal DFT validator.
