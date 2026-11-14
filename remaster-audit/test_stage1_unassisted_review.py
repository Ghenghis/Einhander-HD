"""CPU-only refusal tests. No graphics context, runtime, broker mutation or RAM writes."""
import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import tempfile
import ast
import contextlib
import io

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / 'tools/coordination'))
spec = importlib.util.spec_from_file_location('review', ROOT / 'run_stage1_unassisted_review.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


class LaunchPolicy(unittest.TestCase):
    def setUp(self):
        self.now = dt.datetime(2026, 11, 14, 18, 40, tzinfo=dt.timezone.utc)
        self.hold = dict(schema='einhander-user-gpu-hold-v1', reserved_until_utc='2026-11-14T18:37:05Z')
        self.report = dict(production_installed=False,
            visual_profile=dict(timer_only_assistance=False, capture_seconds=60),
            pacing_profile=dict(ram_writes=False, timer_assistance=False))

    def check(self, **kwargs):
        args = dict(report=self.report, hold=self.hold, permission=dict(allowed=True), now=self.now)
        args.update(kwargs)
        return review.validate_review_policy(**args)

    def test_unassisted_after_hold_still_requires_grant(self):
        self.assertEqual(self.check()['assistance'], False)
        for grant in ({}, {'allowed': False}, {'allowed': 1}):
            with self.subTest(grant=grant), self.assertRaises(ValueError):
                self.check(permission=grant)

    def test_hold_cannot_be_overridden_by_valid_grant(self):
        with self.assertRaisesRegex(ValueError, 'reservation'):
            self.check(now=self.now.replace(hour=18, minute=0))

    def test_missing_or_malformed_hold_fails_closed(self):
        for hold in (None, {}, {'schema': 'old'}, dict(self.hold, reserved_until_utc='bad'),
                     dict(self.hold, reserved_until_utc='2026-11-14T18:00:00')):
            with self.subTest(hold=hold), self.assertRaises((ValueError, KeyError)):
                self.check(hold=hold)

    def test_ram_write_metadata_cannot_be_hidden(self):
        for key in ('ram_writes', 'timer_assistance'):
            r = copy.deepcopy(self.report)
            r['pacing_profile'][key] = True
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'disagrees'):
                self.check(report=r)

    def test_assistance_is_explicit_and_consistent(self):
        r = copy.deepcopy(self.report)
        for val in (None, 0, 1, 'false'):
            r['visual_profile']['timer_only_assistance'] = val
            with self.subTest(val=val), self.assertRaises(ValueError):
                self.check(report=r)
        r['visual_profile']['timer_only_assistance'] = True
        r['pacing_profile'].update(ram_writes=True, timer_assistance=True)
        self.assertTrue(self.check(report=r)['assistance'])

    def test_duration_and_private_scope_refusals(self):
        for val in (0, -1, True, 60.0, 61, 3600):
            r = copy.deepcopy(self.report)
            r['visual_profile']['capture_seconds'] = val
            with self.subTest(val=val), self.assertRaises(ValueError):
                self.check(report=r)
        for val in (True, None, 0):
            r = dict(self.report, production_installed=val)
            with self.subTest(val=val), self.assertRaises(ValueError):
                self.check(report=r)

    def test_fenced_launch_refuses_before_any_popen_or_registration(self):
        sys.path.insert(0, str(ROOT.parent / 'tools/coordination'))
        import shared_gpu_guard
        with patch.object(Path, 'read_bytes', return_value=json.dumps(self.hold).encode()), \
             patch.object(shared_gpu_guard, 'current_permission', return_value={'allowed': False}), \
             patch.object(shared_gpu_guard, 'broker_action', side_effect=AssertionError('No registration')), \
             patch.object(review.pacing, 'launch', side_effect=AssertionError('No launch')):
            # Use a deterministic hold fixture; no actual user state is required.
            with self.assertRaises((ValueError, KeyError)):
                review.fenced_launch(dict(self.report, evidence=str(ROOT)))


class CommandPolicy(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='einhander-policy-test-')
        self.addCleanup(self.temp.cleanup)
        self.report = dict(evidence=self.temp.name,
            visual_profile=dict(timer_only_assistance=False,ordinary_fire=False))

    def test_all_known_state_mutators_refused_before_transport(self):
        from unassisted_command_guard import send_guarded
        mutators = ['savestate','load_state','save_state','write_ram','set_snapshot','fn_disable',
                    'overlay_irq_suppress_on','input_route_append','input_route_start',
                    'pause','step','run_to_frame','lockstep','unknown']
        for cmd in mutators:
            with self.subTest(cmd=cmd), self.assertRaises(ValueError):
                send_guarded(lambda *_: self.fail('Transport called'), self.report, json.dumps(dict(cmd=cmd)))
        self.assertFalse((Path(self.temp.name)/'command-intents').exists())

    def test_intent_exists_when_transport_times_out(self):
        from unassisted_command_guard import send_guarded, audit_commands
        def timeout(*args):
            intents=list((Path(self.temp.name)/'command-intents').glob('*.json'))
            self.assertEqual(len(intents),1)
            self.assertEqual(json.loads(intents[0].read_text())['request']['cmd'],'audio_stats')
            raise TimeoutError('Executed but reply unknown')
        with self.assertRaises(TimeoutError):
            send_guarded(timeout,self.report,json.dumps(dict(cmd='audio_stats')))
        self.assertEqual(audit_commands(self.report)['checked_records'],1)

    def test_arguments_and_paths_fail_closed(self):
        from unassisted_command_guard import validate_command
        requests=[dict(cmd='turbo',enabled=1),dict(cmd='turbo',enabled=False),
            dict(cmd='press',buttons=65535,frames=121),dict(cmd='press',buttons=65535,frames=True),
            dict(cmd='set_input',buttons='0x7FFF'),dict(cmd='read_ram',addr='0x80081380',len=100),
            dict(cmd='screenshot',path=str(Path(self.temp.name).parent/'outside.png')),
            dict(cmd='audio_stats',hidden_mutator=True)]
        for request in requests:
            with self.subTest(request=request),self.assertRaises(ValueError):validate_command(self.report,request)
        validate_command(self.report,dict(cmd='turbo',enabled=0))
        validate_command(self.report,dict(cmd='frame_phase_ring',n=2048,from_frame=0,to_frame=300))

    def test_malformed_audit_preserved_without_cleanup_exception(self):
        from unassisted_command_guard import audit_commands
        p=Path(self.temp.name)/'commands';p.mkdir()
        (p/'bad.json').write_text('{broken')
        (p/'mutator.json').write_text(json.dumps(dict(request=dict(cmd='savestate',op='load'))))
        self.assertEqual(len(audit_commands(self.report)['forbidden_or_malformed']),2)

    def test_transient_broker_arguments_removed_on_success_and_timeout(self):
        import shared_gpu_guard
        from types import SimpleNamespace
        paths=[]
        def transport(args,**kwargs):
            path=Path(args[args.index('--file')+1]);paths.append(path)
            self.assertTrue(path.exists())
            self.assertFalse(path.is_relative_to(Path(self.temp.name)))
            self.assertEqual(json.loads(path.read_text())['token'],'synthetic-test-fence')
            if len(paths)==2:raise TimeoutError('Synthetic transport timeout')
            return SimpleNamespace(returncode=0,stdout='{"allowed":true}')
        with patch.object(shared_gpu_guard.subprocess,'run',side_effect=transport):
            self.assertTrue(shared_gpu_guard.broker_action('check','synthetic-test-fence',self.temp.name)['allowed'])
            with self.assertRaises(TimeoutError):shared_gpu_guard.broker_action('check','synthetic-test-fence',self.temp.name)
        self.assertTrue(all(not p.exists() and not p.parent.exists() for p in paths))


class ActualCliPolicy(unittest.TestCase):
    def execute_main(self, extra):
        text=(ROOT/'run_stage1_unassisted_review.py').read_text(encoding='utf-8')
        block=ast.parse(text).body[-1]
        self.assertIsInstance(block,ast.If)
        namespace=dict(review.__dict__)
        calls=[]
        namespace['prepare']=lambda args:calls.append(vars(args))
        namespace['run']=lambda *_:self.fail('GPU/game path must not run')
        argv=['review','--batch','cpu-fixture','--candidate','unused-private-candidate.json',
              '--runtime','unused-private-build.json','--prepare-only',*extra]
        with patch.object(sys,'argv',argv),contextlib.redirect_stderr(io.StringIO()):
            exec(compile(ast.Module(body=block.body,type_ignores=[]),'actual-cli-block','exec'),namespace)
        return calls

    def test_actual_cli_defaults_are_light_and_unassisted(self):
        calls=self.execute_main([])
        self.assertEqual(len(calls),1)
        args=calls[0]
        self.assertEqual((args['capture_seconds'],args['supersampling']),(60,2))
        self.assertTrue(args['telemetry_only'])
        self.assertFalse(args['timer_assist'])

    def test_unsupported_modes_refuse_before_preparation(self):
        for extra in (['--timer-assist'],['--record-evidence'],['--capture-seconds','3600']):
            with self.subTest(extra=extra),self.assertRaises(SystemExit) as caught:
                self.execute_main(extra)
            self.assertEqual(caught.exception.code,2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
