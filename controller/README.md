# Batch controller

The workspace's AGENTS.md tells Codex to save request.md and the waiting state,
start a persistent controller, then end its turn. The controller waits until all
watched jobs are terminal and starts fresh Codex to collect, interpret and report.

Records under projects/<task>/workflow/:
- state.json: waiting, codex_running, complete or failed, with the next action.
- events.jsonl: state history.
- codex_NNN.jsonl, .stderr.log and .last.txt: background Codex output.

No IDE-thread resumption, notifications, automatic retries or crash recovery.
A missing handoff, nonzero Codex exit or interrupted invocation stops automation.
UNKNOWN scheduler state keeps waiting. Inspect service logs and saved results
before any manual reset. Old handled batches cannot be reused.

For a running user service: systemctl --user status <service-name>.
Completed services may be removed because --collect was used at launch.
The request defines allowed work; no hard compute budget is enforced by the code.
