"""License-free tests of acceptance gates; parser/scheduler are mocked.
Real POTCAR/XML parsing belongs to the user's separately licensed smoke test.
"""
from pathlib import Path
from types import SimpleNamespace
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from pymatgen.io.vasp import Incar, Kpoints, Poscar
from tools.vasp import cli
ROOT = Path(__file__).resolve().parents[1]

class VaspTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(dir=ROOT/'projects',prefix='test_vasp_')
        self.addCleanup(tmp.cleanup)
        self.job=Path(tmp.name)
        for name in ('POSCAR','INCAR','KPOINTS'):
            shutil.copy2(ROOT/'examples/si'/name,self.job/name)
        # No licensed or dummy POTCAR files: these tests exercise only gates.
        inputs=('POSCAR','INCAR','KPOINTS')
        p=patch.object(cli,'INPUTS',inputs);p.start();self.addCleanup(p.stop)
        incar=dict(Incar.from_file(self.job/'INCAR'))
        structure=Poscar.from_file(self.job/'POSCAR',check_for_potcar=False).structure
        kpoints=Kpoints.from_file(self.job/'KPOINTS')
        data=dict(job_family='static',natoms=2,species=['Si'],incar=incar,
            kpoints=kpoints.as_dict(),potcar_titles=['Si test identity'],selective_dynamics=None,
            input_sha256={n:cli.sha256(self.job/n) for n in inputs})
        cli.write_json(self.job/'prepared.json',data)
        cli.write_json(self.job/'submission.json',{'job_id':'123'})
        self.parsed=SimpleNamespace(incar=incar.copy(),parameters=dict(incar,NELM=100),
            initial_structure=structure,final_structure=structure,kpoints=kpoints,
            potcar_symbols=['Si test identity'],converged_electronic=True,
            converged_ionic=True,final_energy=-10.0,
            ionic_steps=[{'electronic_steps':[{}],'forces':np.zeros((2,3))}])

    def collect(self,state='COMPLETED',code='0:0'):
        (self.job/'vasprun.xml').write_text('<mock-parser-boundary/>')
        with patch.object(cli,'scheduler_state',return_value=(state,code)), patch.object(cli,'Vasprun',return_value=self.parsed):
            return cli.collect(self.job)

    def test_changed_input_blocks_submission(self):
        with (self.job/'INCAR').open('a') as f:f.write('\nENCUT=450\n')
        with self.assertRaises(ValueError):cli.submit(self.job)

    def test_duplicate_submission_is_blocked(self):
        with self.assertRaises(FileExistsError):cli.submit(self.job)

    def test_valid_static_gate_records_energy_and_hashes(self):
        result=self.collect()
        self.assertEqual(result['status'],'validated')
        self.assertEqual(result['energy_sigma0_eV_per_cell'],-10.0)
        self.assertIn('vasprun.xml',result['output_sha256'])
        self.assertIsNone(result['ionic_converged'])

    def test_completed_scheduler_does_not_override_scf_failure(self):
        self.parsed.converged_electronic=False
        self.assertEqual(self.collect()['status'],'failed')

    def test_completed_scheduler_does_not_override_method_mismatch(self):
        self.parsed.incar['GGA']='Ps'
        self.assertEqual(self.collect()['status'],'failed')

    def test_wrong_potential_identity_is_rejected(self):
        self.parsed.potcar_symbols=['different identity']
        self.assertEqual(self.collect()['status'],'failed')

    def test_timeout_is_not_accepted_with_converged_outputs(self):
        self.assertEqual(self.collect('TIMEOUT','0:1')['status'],'failed')

    def test_nonfinite_energy_is_rejected(self):
        self.parsed.final_energy=float('nan')
        self.assertEqual(self.collect()['status'],'failed')

    def test_running_job_is_not_collected(self):
        self.assertEqual(self.collect('RUNNING',None)['status'],'waiting')

    def test_parser_error_is_recorded(self):
        with patch.object(cli,'scheduler_state',return_value=('COMPLETED','0:0')),patch.object(cli,'Vasprun',side_effect=ValueError('broken XML')):
            result=cli.collect(self.job)
        self.assertEqual(result['status'],'failed')
        self.assertIn('broken XML',result['errors'][0])

    def test_ionic_gate_rejects_unrelaxed_geometry(self):
        data=json.loads((self.job/'prepared.json').read_text())
        data['job_family']='relax';data['incar'].update(NSW=10,IBRION=2,EDIFFG=-.01)
        cli.write_json(self.job/'prepared.json',data)
        self.parsed.incar.update(data['incar']);self.parsed.converged_ionic=False
        self.assertEqual(self.collect()['status'],'failed')

    def test_missing_inputs_cannot_be_checked(self):
        (self.job/'prepared.json').unlink();(self.job/'submission.json').unlink()
        (self.job/'KPOINTS').unlink()
        with self.assertRaises(ValueError):cli.check(self.job)

if __name__=='__main__':unittest.main()
