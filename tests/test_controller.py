import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('tutorial_controller', ROOT/'controller/cli.py')
cli = importlib.util.module_from_spec(SPEC)
if Path(SPEC.origin).exists(): SPEC.loader.exec_module(cli)

class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(cli, 'set_state'), 'controller is not implemented')
        self.tmp=tempfile.TemporaryDirectory(dir=ROOT/'projects',prefix='test_controller_')
        self.addCleanup(self.tmp.cleanup)
        self.task=Path(self.tmp.name)
        (self.task/'request.md').write_text('Validate tutorial batch.\n')
        for name, job_id in [('a','1'),('b','2'),('c','3')]:
            job=self.task/name;job.mkdir()
            (job/'submission.json').write_text(json.dumps({'job_id':job_id}))

    def start(self,jobs=('a',)):
        return cli.set_state(self.task,'waiting',jobs,'Collect and report')

    def observe(self, states, invoke):
        def status(job):
            job_id=json.loads((job/'submission.json').read_text())['job_id']
            return {'job_id':job_id,'job_state':states[job.name],'exit_code':'0:0'}
        with patch.object(cli.vasp,'status',side_effect=status):
            return cli.tick(self.task,invoke)

    def test_waits_for_entire_batch_without_invoking_codex(self):
        self.start(('a','b'))
        self.assertEqual(self.observe({'a':'COMPLETED','b':'RUNNING'},lambda *_:self.fail()),'waiting')
        self.assertEqual(cli.load(self.task)['status'],'waiting')

    def test_terminal_batch_invokes_once_and_can_complete(self):
        self.start(); calls=[]
        def invoke(task):
            calls.append(task);cli.set_state(task,'complete',(),None);return 0
        self.assertEqual(self.observe({'a':'COMPLETED'},invoke),'complete')
        self.assertEqual(self.observe({},lambda *_:self.fail()),'complete')
        self.assertEqual(len(calls),1)

    def test_failed_job_also_reaches_codex_for_interpretation(self):
        self.start()
        def invoke(task): cli.set_state(task,'failed',(),'SCF failure');return 0
        self.assertEqual(self.observe({'a':'FAILED'},invoke),'failed')

    def test_new_batch_continues_but_same_batch_is_rejected(self):
        self.start()
        def next_batch(task): cli.set_state(task,'waiting',('b',),'Next batch');return 0
        self.assertEqual(self.observe({'a':'COMPLETED'},next_batch),'waiting')
        def same_batch(task): cli.set_state(task,'waiting',('b',),'Again');return 0
        self.assertEqual(self.observe({'b':'COMPLETED'},same_batch),'failed')

    def test_rejects_recycling_a_batch_after_an_intervening_batch(self):
        self.start()
        def batch_b(task): cli.set_state(task,'waiting',('b',),'B');return 0
        self.assertEqual(self.observe({'a':'COMPLETED'},batch_b),'waiting')
        def batch_a(task): cli.set_state(task,'waiting',('a',),'A again');return 0
        self.assertEqual(self.observe({'b':'COMPLETED'},batch_a),'failed')

    def test_unknown_state_waits_and_unchanged_codex_state_fails(self):
        self.start()
        self.assertEqual(self.observe({'a':'UNKNOWN'},lambda *_:self.fail()),'waiting')
        self.assertEqual(self.observe({'a':'COMPLETED'},lambda *_:0),'failed')

    def test_nonzero_codex_and_interrupted_invocation_fail_closed(self):
        self.start()
        self.assertEqual(self.observe({'a':'COMPLETED'},lambda *_:1),'failed')
        self.start()
        state=cli.load(self.task);state['status']='codex_running';cli.save(self.task,state)
        self.assertEqual(self.observe({},lambda *_:self.fail()),'failed')

    def test_lock_prevents_a_second_controller(self):
        import fcntl
        self.start()
        with (self.task/'workflow/.controller.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): cli.run(self.task,30)

    def test_rejects_bad_paths_missing_request_and_changed_job_identity(self):
        with self.assertRaises(ValueError): self.start(('../outside',))
        self.start()
        (self.task/'a/submission.json').write_text('{"job_id":"99"}')
        with self.assertRaises(ValueError): cli.load(self.task)
        (self.task/'request.md').unlink()
        with self.assertRaises(ValueError): cli.set_state(self.task,'waiting',('b',),'Next')

if __name__=='__main__': unittest.main()
