# Codex VASP Harness

A small teaching example for materials researchers using Codex with VASP and
Slurm. Codex chooses the calculation; reusable commands check inputs, submit
jobs, and validate/record results. The controller handles waiting and
starts a fresh Codex process after a batch finishes.

## What is included

- `tools/vasp/cli.py`: `check`, `submit`, `status`, `collect`.
- `tools/vasp/submit.slurm`: editable cluster submission template.
- `examples/si/`: public two-atom diamond-Si input geometry and tutorial settings.
- `AGENTS.md`: instructions routing Codex through the tools.
- `controller/`: automatic waiting and background continuation.
- `tests/`: acceptance-gate tests with mocked parser/scheduler boundaries; no
  licensed potentials or live scheduler required.

No VASP executable, POTCAR, credentials, or calculation outputs are distributed.
The MIT license applies to this code; obtain VASP and potentials separately.

## 1. Get the code

Get the version used in this tutorial:

```bash
git clone --branch v0.1.1 https://github.com/alhedai1/codex-vasp-harness.git
cd codex-vasp-harness
HARNESS_SOURCE="$PWD"
```

Or download the [v0.1.1 release](https://github.com/alhedai1/codex-vasp-harness/releases/tag/v0.1.1).
Run the commands below from the repository root. For a versioned workshop use
the tutorial tag rather than an evolving branch. Link the slides to that release.

### Add both components to an existing workspace

From your existing workspace root (for example, `mmm12_tutorial`):

```bash
git clone --branch v0.1.1 https://github.com/alhedai1/codex-vasp-harness.git harness-source
mkdir -p tools
cp -R harness-source/tools/vasp tools/
cp -R harness-source/controller .
HARNESS_SOURCE="$PWD/harness-source"
```

Start with no existing `tools/vasp` or `controller` directories: move old versions
to a backup first. Copying into an existing directory can leave stale files.
Keep your `projects/`, `.agents/skills/`, environments and calculation outputs.
Keep your existing AGENTS.md and merge the supplied harness/controller instructions;
do not overwrite your lab's instructions. Both components are part of this setup.
Paths resolve relative to the installed tools' root. Continue from your workspace
root, with tools and controller alongside projects (not inside harness-source).
Example files and requirements are under harness-source/ in this installation mode.

## 2. Prepare the environment

Linux, Python **3.11+**, numpy, pymatgen, and Slurm command-line tools, an installed/authenticated Codex CLI, and a persistent
execution mechanism are required. The documented detached launch uses Linux user
systemd services. Check `codex --version` and `systemctl --user is-system-running`.
Use your lab's existing compatible environment, or create an isolated one:

```bash
conda create -n codex-vasp-harness python=3.11 pip
conda activate codex-vasp-harness
python -m pip install -r "$HARNESS_SOURCE/requirements.txt"
(cd "$HARNESS_SOURCE" && python -m unittest discover -s tests -v)
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
cp "$HARNESS_SOURCE/examples/si/POSCAR" "$HARNESS_SOURCE/examples/si/INCAR" \
  "$HARNESS_SOURCE/examples/si/KPOINTS" projects/Si_example/static/run01/
cp tools/vasp/submit.slurm projects/Si_example/static/run01/
cp "$HARNESS_SOURCE/examples/si/request.md" projects/Si_example/request.md
```

Place the **real authorized Si PAW_PBE POTCAR** in that job directory yourself.
It must match POSCAR species order. Do not download an arbitrary potential,
create a placeholder, or commit the licensed file. Read examples/si/README.md.

## 4. Check, submit, and hand off to the controller

Codex can perform this sequence when you ask it to run the complete task using
AGENTS.md. The commands below also make the handoff reproducible in a terminal:

```bash
python tools/vasp/cli.py check projects/Si_example/static/run01
python tools/vasp/cli.py submit projects/Si_example/static/run01
python -m controller.cli set-state projects/Si_example \
  --status waiting --job static/run01 \
  --next-action 'Collect and validate; write report.md; no further jobs.'
systemd-run --user --unit=si-controller-demo --collect --no-block \
  --working-directory="$PWD" --setenv=PATH="$PATH" \
  --setenv=VASP_BIN="$VASP_BIN" \
  "$(command -v python)" -B -m controller.cli run projects/Si_example
```

Use a unique unit name for each task. The controller waits without LLM calls,
then launches fresh Codex to run `collect`, interpret result.json, write report.md,
and mark the task complete/failed. You do not need to ask Codex to collect later.
For a new batch it repeats the handoff within the scope of request.md.
Read controller/README.md for service prerequisites, logs and failure handling.

`status` and `collect` remain independently callable for inspection/debugging;
normal unattended execution uses the controller for continuation.

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

## 6. Follow the completed workflow

Read `projects/Si_example/workflow/state.json` and `projects/Si_example/report.md`.
The controller and background Codex logs are in the task's workflow/ directory.
The original sidebar conversation is not resumed. **Notifications are not
implemented**: execution and continuation are automatic, but completion is
visible in the saved state/report rather than through an alert.

## Scope of this tutorial release

Fresh-start periodic PBE/PBEsol PAW calculations, explicit uniform k meshes,
static jobs and IBRION=1/2/3 relaxations; whole-atom fixed/free constraints.
Electronic restarts, partial-direction constraints and unsupported methods are
rejected explicitly. No automatic scientific recovery is performed.

Configurable scientific protocols and cross-calculation `compare` are proposed
next steps, **not commands in this release**. It is not a universal DFT validator.
