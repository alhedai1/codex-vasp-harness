## VASP harness

- Use the existing scientific Python environment. Use DFT Skills, when installed,
  for scientific method/input choices. Preserve existing calculations.
- Use tools/vasp/cli.py check, submit, status, collect for supported VASP jobs.
  Submit only when the task authorizes it. Use a new projects/<task>/<stage>/runNN
  directory for changed inputs. Never edit inputs after check or bypass a failed gate.
- Copy tools/vasp/submit.slurm into each fresh job directory before check;
  review partition/resources/launcher and set VASP_BIN for this server.
- For each task write projects/<task>/request.md: objective, authorized work,
  expected report and stop condition. Keep licensed POTCAR files local.
- After submission, save the handoff using:
  python -m controller.cli set-state projects/<task> --status waiting
  --job <relative-job-directory> --next-action "What to validate/do next"
  Repeat --job for every job in the batch. Paths are relative to projects/<task>.
- Start the controller as a detached user service, from the workspace root:
  systemd-run --user --unit=<unique-task-service> --collect --no-block
  --working-directory="$PWD" --setenv=PATH="$PATH" --setenv=VASP_BIN="$VASP_BIN"
  "$(command -v python)" -B -m controller.cli run projects/<task>
  (The wrapped lines above form one command.) Then end active Codex work.
  Tell the researcher the task's state and report locations. Do not poll jobs.
- The controller waits for the whole batch and starts fresh background Codex.
  Reconstruct context from request.md and workflow/state.json. Collect every job
  through the VASP tool, inspect result.json, interpret failures, and write report.md.
- Set controller state complete/failed when done, or waiting with entirely NEW
  submitted jobs and a next action within the authorized task. Never repeat an old
  batch. Do not resume the original IDE thread. Do not invent extra calculations.
- Validated execution is not numerical convergence or physical validation.
  No automatic retry or notification is implemented. Inspect logs before recovery.
