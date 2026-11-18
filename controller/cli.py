"""Wait for a VASP batch, then ask a fresh Codex invocation to continue."""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import time

from tools.vasp import cli as vasp

ROOT = Path(__file__).resolve().parents[1]
STATES = {'waiting', 'codex_running', 'complete', 'failed'}


def task_path(value):
    task = Path(value).resolve()
    if not task.is_relative_to(ROOT/'projects') or not (task/'request.md').is_file():
        raise ValueError('Task must be under projects/ and contain request.md')
    return task


def validate(task, state):
    task_path(task)
    if state.get('status') not in STATES or not isinstance(state.get('jobs'), list) or not state['jobs']:
        raise ValueError('State needs a valid status and a nonempty jobs list')
    seen = set()
    for job in state['jobs']:
        path = (task/job['directory']).resolve()
        if not path.is_relative_to(task) or path == task or path in seen:
            raise ValueError('Job directory must be unique and inside the task')
        seen.add(path)
        actual = str(json.loads((path/'submission.json').read_text())['job_id'])
        if not actual.isdigit() or actual != job['job_id']:
            raise ValueError('Saved job ID does not match submission.json')


def save(task, state):
    validate(task, state)
    workflow = task/'workflow'
    workflow.mkdir(exist_ok=True)
    state['updated_at_utc'] = vasp.stamp()
    vasp.write_json(workflow/'state.json', state)
    with (workflow/'events.jsonl').open('a') as log:
        log.write(json.dumps(state) + '\n')


def load(task):
    state = json.loads((task/'workflow/state.json').read_text())
    validate(task, state)
    return state


def set_state(task, status, jobs, next_action):
    task = task_path(task)
    state = load(task) if (task/'workflow/state.json').exists() else {'jobs': []}
    if status == 'waiting':
        if not jobs or not next_action:
            raise ValueError('Waiting needs --job and --next-action')
        state['jobs'] = []
        for name in jobs:
            path = (task/name).resolve()
            if not path.is_relative_to(task) or path == task:
                raise ValueError('Job must be inside task')
            job_id = str(json.loads((path/'submission.json').read_text())['job_id'])
            state['jobs'].append({'directory': str(path.relative_to(task)), 'job_id': job_id})
    elif jobs:
        raise ValueError('--job is only used with waiting')
    state['status'] = status
    if next_action is not None:
        state['next_action'] = next_action
    state.pop('error', None)
    save(task, state)
    return state


def fail(task, state, reason):
    state.update(status='failed', error=reason)
    save(task, state)
    return 'failed'


def tick(task, invoke):
    state = load(task)
    if state['status'] in ('complete', 'failed'):
        return state['status']
    if state['status'] == 'codex_running':
        return fail(task, state, 'Interrupted Codex invocation; inspect logs before manual recovery')
    for job in state['jobs']:
        job['scheduler'] = vasp.status(task/job['directory'])
    save(task, state)  # Also persists observations if the queue later forgets jobs.
    if any(job['scheduler']['job_state'] not in vasp.TERMINAL for job in state['jobs']):
        return 'waiting'
    previous = {(j['job_id'], j['directory']) for j in state['jobs']}
    handled = set(map(tuple, state.get('handled_jobs', []))) | previous
    state['status'] = 'codex_running'
    state['attempt'] = state.get('attempt', 0) + 1
    save(task, state)
    try:
        code = invoke(task)
        after = load(task)
    except Exception as exc:
        return fail(task, state, f'Codex invocation/state error: {exc}')
    if code != 0:
        return fail(task, after, f'Codex exited {code}; inspect logs before manual recovery')
    if after['status'] == 'codex_running':
        return fail(task, after, 'Codex did not persist a next state')
    after['handled_jobs'] = sorted(handled)
    if after['status'] == 'waiting' and handled.intersection(
            (j['job_id'], j['directory']) for j in after['jobs']):
        return fail(task, after, 'Codex tried waiting again on an already handled batch')
    save(task, after)
    return after['status']


def invoke_codex(task, lock_fd):
    state = load(task)
    relative = str(task.relative_to(ROOT))
    prompt = (
        f'Continue the authorized scientific task in {relative}. Read AGENTS.md, '
        f'{relative}/request.md, and {relative}/workflow/state.json. The watched batch '
        'has reached terminal scheduler states; this does not establish convergence. '
        'Collect each job with tools/vasp/cli.py, inspect result.json, and make the '
        'next scientific decision within the original request. Write your report '
        'inside this task. Use python -m controller.cli set-state TASK --status complete '
        'or failed when done, or --status waiting --job RELATIVE_JOB_DIR (repeatable) '
        '--next-action "PLAN" for a newly submitted batch. TASK is the task directory; '
        'job paths are relative to it. Preserve old calculation directories. Do not '
        'wait for jobs. This is a fresh invocation; all context must come from disk.'
    )
    prefix = task/'workflow'/f'codex_{state["attempt"]:03d}'
    command = ['codex', 'exec', '--skip-git-repo-check', '-C', str(ROOT),
               '--sandbox', 'workspace-write', '--ephemeral', '--json',
               '--output-last-message', str(prefix)+'.last.txt', '-']
    with Path(str(prefix)+'.jsonl').open('w') as out, Path(str(prefix)+'.stderr.log').open('w') as err:
        return subprocess.run(command, input=prompt, text=True, stdout=out, stderr=err,
                              cwd=ROOT, pass_fds=(lock_fd,)).returncode


def run(task, interval):
    if interval < 30:
        raise ValueError('Use a polling interval of at least 30 seconds')
    with (task/'workflow/.controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            outcome = tick(task, lambda t: invoke_codex(t, lock.fileno()))
            if outcome != 'waiting':
                return outcome
            time.sleep(interval)  # Scheduler waiting uses no LLM.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    setter = sub.add_parser('set-state')
    setter.add_argument('task', type=Path)
    setter.add_argument('--status', choices=('waiting', 'complete', 'failed'), required=True)
    setter.add_argument('--job', action='append', default=[])
    setter.add_argument('--next-action')
    runner = sub.add_parser('run')
    runner.add_argument('task', type=Path)
    runner.add_argument('--interval', type=int, default=60)
    args = parser.parse_args()
    try:
        task = task_path(args.task)
        if args.command == 'set-state':
            outcome = set_state(task, args.status, args.job, args.next_action)['status']
        else:
            outcome = run(task, args.interval)
        print(json.dumps({'task': str(task.relative_to(ROOT)), 'status': outcome}))
        return 1 if outcome == 'failed' else 0
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
