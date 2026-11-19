# Codex VASP Harness

Reusable VASP commands with validation/provenance, plus a controller that waits
for Slurm jobs and starts Codex again to collect results and continue the task.
Both the VASP tool and controller are standard parts of the harness.

## 1. Clone into your existing workspace

Run from your workspace root, where your AGENTS.md and projects/ live:

```bash
git clone --branch v0.1.2 https://github.com/alhedai1/codex-vasp-harness.git harness-source
```

## 2. Copy the two components

Start without existing tools/vasp/ and controller/ directories. Back up old
versions first if present; keep your projects, skills and existing environment.

```bash
mkdir -p tools
cp -R harness-source/tools/vasp tools/
cp -R harness-source/controller .
```

Your workspace now has:

```text
AGENTS.md
tools/vasp/cli.py
tools/vasp/submit.slurm
controller/cli.py
projects/
```

Continue working in the workspace root, not inside harness-source/.

## 3. Configure your cluster

Edit tools/vasp/submit.slurm: partition, resources and the MPI launch line.
In your active environment, set the path to your licensed VASP executable:

```bash
export VASP_BIN=/absolute/path/to/vasp_std
```

Use Python 3.11+ with numpy and pymatgen. If your environment lacks them:

```bash
python -m pip install -r harness-source/requirements.txt
```

The controller also needs an installed, authenticated Codex CLI, Slurm commands,
and a persistent process. The supplied launch instructions use Linux user systemd:
check `codex --version` and `systemctl --user is-system-running` on your server.
Module-based clusters may require additional environment setup in the batch script
and service. Supply your own licensed POTCARs; none are included here.

## 4. Update AGENTS.md

Merge the instructions from **harness-source/AGENTS.example.md** into your
workspace's AGENTS.md. Replace older harness instructions if present; keep your
lab-specific instructions. Do not overwrite the entire existing file.

## 5. Ask Codex to run a small task

For example:

> Prepare and run a small static bulk-Si calculation using the VASP harness.
> Launch the controller to collect and validate it automatically and write a
> short report. No additional calculations after this test.

Codex prepares the inputs and runs check -> submit -> controller handoff.
The controller waits without LLM calls, then starts fresh Codex to run collect,
interpret the result and write the report. You do not need to request collection
again. It does not wake the original sidebar chat or send completion notifications.

| Command | Purpose | Saved record |
|---|---|---|
| check | Check inputs; record settings and file fingerprints | prepared.json |
| submit | Verify unchanged inputs; block repeat submission; submit to Slurm | submission.json |
| status | Observe the recorded Slurm job | scheduler.json |
| collect | Check completion/convergence and record energy/forces | result.json |

Inspect projects/<task>/workflow/state.json and report.md for progress/results.
Logs are under workflow/. The controller waits for the whole batch, including
failures. It stops on errors instead of blindly retrying. See controller/README.md.

## Scope

Fresh-start periodic PBE/PBEsol PAW static calculations and IBRION=1/2/3 relaxations;
uniform k meshes and whole-atom fixed/free constraints. Input generation and
scientific decisions belong to Codex/researchers. Passing the checks does not
establish cutoff/k-point convergence or physical accuracy. This is a teaching
harness, not a security boundary. Protocol/compare commands are not implemented.

Tests are for maintainers and are not part of installation:
`python -B -m unittest discover -s tests -v` from the repository root.
