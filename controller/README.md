# Batch controller

The controller is a standard component of the harness. Run after completing
the root README's VASP setup. Requires an installed,
authenticated Codex CLI (`codex --version`), Slurm access, and Python dependencies.
The controller uses the account/environment of the process launching it.

1. Put the allowed objective, expected report and stop condition in
   projects/Si_example/request.md (examples/si/request.md is a starting point).
2. Check and submit static/run01 using tools/vasp.
3. Save the handoff (job directories are relative to the task):

```bash
python -m controller.cli set-state projects/Si_example \
  --status waiting --job static/run01 \
  --next-action 'Collect and validate; write report.md; no further jobs.'
```

Repeat --job for a batch. Job IDs come from each submission.json.
4. For unattended execution start a persistent user service on Linux/systemd:

```bash
systemd-run --user --unit=si-controller-demo --collect --no-block \
  --working-directory="$PWD" --setenv=PATH="$PATH" \
  --setenv=VASP_BIN="$VASP_BIN" \
  "$(command -v python)" -B -m controller.cli run projects/Si_example
```

Use a unique service name per task. The activated environment's PATH must include
python, codex, Slurm and needed cluster executables. If your cluster requires
other environment/module variables, arrange them in its supported service/job
launch mechanism. Test `systemctl --user is-system-running` first. On systems
without user services, use a persistent terminal session and run
`python -m controller.cli run projects/Si_example`; closing an ordinary foreground
terminal can stop that process. No platform-independent daemon is bundled.

The controller waits until ALL watched jobs are terminal (including failures),
then invokes fresh `codex exec` with the request and saved state. It never submits
or interprets calculations itself. Codex runs collect and decides what follows.
State is waiting -> codex_running -> complete/failed, or another new waiting batch.
No model calls occur during scheduler polling (default 60 seconds, minimum 30).

Observe `projects/Si_example/workflow/state.json`, events.jsonl, per-attempt logs,
and the requested report. `systemctl --user status si-controller-demo` shows service
status; completed units may be removed because --collect was used. This is a
background workflow: the original IDE chat is not resumed, and no notifications
are implemented. Allowed work is bounded by request.md, not a hard compute cap.

Fresh Codex ends with `python -m controller.cli set-state TASK --status complete`
or failed. Another batch requires --status waiting, all NEW --job paths, and
--next-action. Locking prevents concurrent controllers; handled identities block
old batches being recycled. All metadata is local; no credentials are saved here.

No automatic retry/crash recovery: nonzero Codex exits, missing handoffs and
interrupted codex_running stop with a failed state. Inspect actual job/output
records and logs before an explicit manual state reset; never blindly resubmit.
UNKNOWN scheduler state keeps waiting. A scheduler terminal state is not
scientific validation. Python errors outside the controlled handoff may only
appear in the service log, so inspect both service and workflow logs on failure.
