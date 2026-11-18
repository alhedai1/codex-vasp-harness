#!/usr/bin/env python3
"""Check, submit, observe and validate existing tutorial VASP inputs."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import warnings

import numpy as np
from pymatgen.io.vasp import Incar, Kpoints, Poscar, Potcar, Vasprun

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ('POSCAR', 'INCAR', 'KPOINTS', 'POTCAR', 'submit.slurm')
OUTPUTS = ('OUTCAR', 'OSZICAR', 'vasprun.xml', 'CONTCAR', 'WAVECAR', 'CHGCAR')
TERMINAL = {'COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY',
            'NODE_FAIL', 'PREEMPTED', 'BOOT_FAIL', 'DEADLINE', 'REVOKED'}


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, data):
    # Atomic replacement: readers never see half-written metadata.
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    temp.replace(path)


def stamp():
    return datetime.now(timezone.utc).isoformat()


def checked(job):
    data = json.loads((job/'prepared.json').read_text())
    if data['input_sha256'] != {name: sha256(job/name) for name in INPUTS}:
        raise ValueError('Inputs changed after check; use a new calculation directory')
    return data


def check(job):
    if (job/'prepared.json').exists():
        return checked(job)
    if any((job/name).exists() for name in (*OUTPUTS, 'submission.json')):
        raise FileExistsError('Check fresh inputs in a new directory, not existing outputs')
    for name in INPUTS:
        if not (job/name).is_file() or not (job/name).stat().st_size:
            raise ValueError(f'Missing nonempty input: {name}')
    tags = []
    for line in (job/'INCAR').read_text().splitlines():
        for assignment in re.split('[;]', re.split('[!#]', line)[0]):
            if '=' in assignment:
                tags.append(assignment.split('=', 1)[0].strip().upper())
    if len(tags) != len(set(tags)):
        raise ValueError('Duplicate INCAR tags; resolve them before checking')
    incar = Incar.from_file(job/'INCAR')
    for tag in ('ENCUT', 'EDIFF', 'NSW'):
        if tag not in incar or not np.isfinite(incar[tag]):
            raise ValueError(f'Explicit finite {tag} required')
    if incar['ENCUT'] <= 0 or incar['EDIFF'] <= 0 or incar['NSW'] < 0:
        raise ValueError('ENCUT/EDIFF must be positive; NSW must be nonnegative')
    if str(incar.get('GGA')).upper() not in ('PE', 'PS') or incar.get('METAGGA') or incar.get('LHFCALC'):
        raise ValueError('Tutorial supports explicit GGA=PE (PBE) or PS (PBEsol) only')
    if incar.get('LNONCOLLINEAR') or incar.get('LSORBIT'):
        raise ValueError('Noncollinear/SOC calculations are outside this tutorial')
    if incar['NSW'] > 0 and (incar.get('IBRION') not in (1, 2, 3) or not incar.get('EDIFFG')):
        raise ValueError('Relaxation requires IBRION=1/2/3 and nonzero EDIFFG')
    if incar.get('ISTART', 0) != 0 or incar.get('ICHARG', 2) != 2:
        raise ValueError('Tutorial supports fresh electronic starts only: ISTART=0, ICHARG=2')
    pos = Poscar.from_file(job/'POSCAR', check_for_potcar=False)
    if pos.selective_dynamics is not None and any(len(set(row)) != 1 for row in pos.selective_dynamics):
        raise ValueError('Tutorial supports whole-atom TTT/FFF constraints only')
    if pos.structure.volume <= 0 or not np.isfinite(pos.structure.cart_coords).all():
        raise ValueError('Invalid structure cell or coordinates')
    kpoints = Kpoints.from_file(job/'KPOINTS')
    if (kpoints.style.name not in ('Gamma', 'Monkhorst') or len(kpoints.kpts) != 1
            or any(k <= 0 or int(k) != k for k in kpoints.kpts[0])):
        raise ValueError('Tutorial requires an explicit positive uniform k-point mesh')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        potentials = Potcar.from_file(job/'POTCAR')
    if [p.element for p in potentials] != pos.site_symbols:
        raise ValueError('POSCAR species and POTCAR order do not match')
    if any('PAW_PBE' not in p.TITEL for p in potentials):
        raise ValueError('Tutorial requires PAW_PBE potentials')
    if incar['ENCUT'] < max(p.ENMAX for p in potentials):
        raise ValueError('ENCUT is below a potential ENMAX')
    data = dict(schema_version=1, checked_at_utc=stamp(), job_family='relax' if incar['NSW'] else 'static',
                species=pos.site_symbols, natoms=len(pos.structure), incar=dict(incar),
                kpoints=kpoints.as_dict(), selective_dynamics=pos.selective_dynamics,
                potcar_titles=[p.TITEL for p in potentials],
                warnings=[str(w.message) for w in caught],
                input_sha256={name: sha256(job/name) for name in INPUTS})
    if data['selective_dynamics'] is not None:
        data['selective_dynamics'] = np.asarray(data['selective_dynamics']).tolist()
    write_json(job/'prepared.json', data)
    return data


def submit(job):
    # Serializes concurrent submissions through this interface.
    with (job/'.submit.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        checked(job)
        if any((job/name).exists() for name in (*OUTPUTS, 'submission.json', 'submission_attempt.json')):
            raise FileExistsError('Already submitted/attempted or outputs exist; use a new directory')
        # Persist BEFORE sbatch: ambiguous interruptions must not cause a second job.
        write_json(job/'submission_attempt.json', {'attempted_at_utc': stamp()})
        run = subprocess.run(['sbatch', '--parsable', 'submit.slurm'], cwd=job,
                             capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError(f'SLURM submission failed: {run.stderr.strip()} (attempt retained)')
        job_id = run.stdout.strip().split(';')[0]
        if not job_id.isdigit():
            raise ValueError('Unrecognized sbatch response; inspect SLURM before retrying')
        data = dict(job_id=job_id, submitted_at_utc=stamp(), command=['sbatch', '--parsable', 'submit.slurm'])
        write_json(job/'submission.json', data)
        return data


def scheduler_state(job_id):
    queries = (['squeue', '-h', '-j', job_id, '-o', '%T'],
               ['scontrol', 'show', 'job', '-o', job_id],
               ['sacct', '-n', '-P', '-j', job_id, '-o', 'JobIDRaw,State,ExitCode'])
    for index, command in enumerate(queries):
        run = subprocess.run(command, capture_output=True, text=True)
        if run.returncode:
            continue
        if index == 0 and run.stdout.strip():
            state = run.stdout.strip().splitlines()[0].upper()
            if state not in TERMINAL:
                return state, None
        if index == 1:
            state = re.search(r'\bJobState=(\S+)', run.stdout)
            code = re.search(r'\bExitCode=(\S+)', run.stdout)
            if state:
                return state[1], code[1] if code else None
        if index == 2:
            for line in run.stdout.splitlines():
                parts = line.split('|')
                if len(parts) >= 3 and parts[0].strip() == job_id:
                    return parts[1].strip().split()[0].rstrip('+'), parts[2].strip()
    return 'UNKNOWN', None  # Never infer success from disappearing queue entries.


def status(job):
    job_id = str(json.loads((job/'submission.json').read_text())['job_id'])
    if not job_id.isdigit():
        raise ValueError('Invalid saved job ID')
    state, code = scheduler_state(job_id)
    path = job/'scheduler.json'
    if state == 'UNKNOWN' and path.exists():
        saved = json.loads(path.read_text())
        if saved['job_id'] == job_id and saved['job_state'] in TERMINAL:
            return dict(saved, evidence_source='saved_terminal_observation')
    data = dict(job_id=job_id, job_state=state, exit_code=code,
                observed_at_utc=stamp(), evidence_source='slurm')
    write_json(path, data)
    return data


def collect(job):
    prepared = checked(job)
    observed = status(job)
    if observed['job_state'] not in TERMINAL:
        return dict(observed, status='waiting')
    result = dict(schema_version=1, collected_at_utc=stamp(), status='failed', scheduler=observed,
                  electronic_converged=False, ionic_converged=None, errors=[],
                  input_sha256=prepared['input_sha256'], output_sha256={},
                  collector_sha256=sha256(Path(__file__)))
    if observed['job_state'] != 'COMPLETED' or observed['exit_code'] != '0:0':
        result['errors'].append('SLURM did not report COMPLETED with exit code 0:0')
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            run = Vasprun(job/'vasprun.xml', parse_dos=False, parse_eigen=False, parse_potcar_file=False)
        result['warnings'] = [str(w.message) for w in caught]
        initial = Poscar.from_file(job/'POSCAR', check_for_potcar=False).structure
        for tag, expected in prepared['incar'].items():
            if tag in ('KPAR', 'NCORE', 'NPAR') and tag not in run.incar and tag not in run.parameters:
                continue  # Some VASP builds omit parallelization controls from XML.
            actual = run.incar.get(tag, run.parameters.get(tag))
            if isinstance(expected, str):
                matches = str(actual).strip().upper() == expected.strip().upper()
            else:
                matches = actual is not None and np.allclose(expected, actual, rtol=1e-8, atol=1e-12)
            if not matches:
                raise ValueError(f'XML {tag} does not match checked INCAR')
        saved_k = prepared['kpoints']
        if (run.kpoints.style.name != saved_k['generation_style']
                or not np.allclose(run.kpoints.kpts, saved_k['kpoints'])
                or not np.allclose(run.kpoints.kpts_shift, saved_k['usershift'])):
            raise ValueError('XML k-point mesh does not match checked KPOINTS')
        if run.potcar_symbols != prepared['potcar_titles']:
            raise ValueError('XML potential identities do not match checked POTCAR')
        if (initial.species != run.initial_structure.species
                or not np.allclose(initial.lattice.matrix, run.initial_structure.lattice.matrix)
                or not np.allclose((initial.frac_coords-run.initial_structure.frac_coords+.5)%1-.5, 0, atol=1e-6)):
            raise ValueError('XML initial structure does not match checked POSCAR')
        result['electronic_converged'] = bool(run.converged_electronic and all(
            len(step['electronic_steps']) < run.parameters['NELM'] for step in run.ionic_steps))
        if not result['electronic_converged']:
            result['errors'].append('Electronic convergence not established at every ionic step')
        energy = float(run.final_energy)
        forces = np.asarray(run.ionic_steps[-1]['forces'])
        if not np.isfinite(energy) or forces.shape != (prepared['natoms'], 3) or not np.isfinite(forces).all():
            raise ValueError('Invalid energy or forces')
        mask = prepared['selective_dynamics']
        effective = forces if mask is None else forces*np.asarray(mask)
        result.update(energy_sigma0_eV_per_cell=energy, ionic_steps=len(run.ionic_steps),
                      max_mobile_force_eV_A=float(np.linalg.norm(effective, axis=1).max()),
                      max_raw_force_eV_A=float(np.linalg.norm(forces, axis=1).max()))
        if prepared['job_family'] == 'relax':
            threshold = prepared['incar']['EDIFFG']
            result['ionic_converged'] = bool(run.converged_ionic and
                (threshold > 0 or result['max_mobile_force_eV_A'] <= abs(threshold)))
            if not result['ionic_converged']:
                result['errors'].append('Ionic convergence/force criterion not satisfied')
        final = job/'CONTCAR'
        if final.is_file() and final.stat().st_size:
            structure = Poscar.from_file(final, check_for_potcar=False).structure
            if (structure.species != run.final_structure.species
                    or not np.allclose(structure.lattice.matrix, run.final_structure.lattice.matrix, atol=1e-5)
                    or not np.allclose((structure.frac_coords-run.final_structure.frac_coords+.5)%1-.5, 0, atol=1e-5)):
                raise ValueError('CONTCAR does not match XML final structure')
        elif prepared['job_family'] == 'relax':
            raise ValueError('Missing nonempty CONTCAR for relaxation')
        else:
            final = job/'POSCAR'
        result['final_structure'] = final.name
        result['output_sha256'] = {name:sha256(job/name) for name in {'vasprun.xml', final.name}}
        if not result['errors']:
            result['status'] = 'validated'
    except Exception as exc:
        result['errors'].append(f'{type(exc).__name__}: {exc}')
    write_json(job/'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('check', 'submit', 'status', 'collect'))
    parser.add_argument('job_dir', type=Path)
    args = parser.parse_args()
    try:
        job = args.job_dir.resolve(strict=True)
        if not job.is_dir() or not job.is_relative_to(ROOT):
            raise ValueError('Job must be a directory inside this workspace')
        result = globals()[args.command](job)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 2 if result.get('status') == 'waiting' else 1 if result.get('status') == 'failed' else 0
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
