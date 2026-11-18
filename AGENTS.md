# Codex VASP tutorial harness

- Read README.md for setup and supported calculation types. Use the activated
  Python environment; do not install dependencies or change the cluster setup
  without authorization.
- Use a fresh directory under projects/ for every changed calculation. Preserve
  old runs. Never publish POTCAR, credentials, or licensed VASP executables.
- Codex/researchers choose the scientific model and inputs. Optional DFT Skills
  provides methodological guidance; these tools do not select scientific settings.
- Use tools/vasp/cli.py check, submit, status, collect for supported calculations.
  Check the configured submission template before submission. Submit/cancel jobs
  only when authorized. Never edit checked inputs to reuse a job directory.
- Use result.json to distinguish validated results from failures. Passing execution
  gates does not establish numerical convergence or physical accuracy.
- For authorized unattended tasks, read controller/README.md: write request.md
  including objective, allowed calculations and stop condition; save waiting state,
  launch a persistent controller, and end the interactive turn. No active polling.
- A background invocation reconstructs context from request.md and workflow/state.json,
  collects each job, interprets results, writes a report and marks complete/failed
  or watches an entirely new authorized batch. Do not resume a live IDE thread.
