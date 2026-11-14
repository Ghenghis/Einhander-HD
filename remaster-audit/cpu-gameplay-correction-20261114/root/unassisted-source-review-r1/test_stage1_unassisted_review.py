"""CPU-only refusal tests. No graphics context, runtime, broker mutation or RAM writes."""
import copy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
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
        with patch.object(shared_gpu_guard, 'current_permission', return_value={'allowed': False}), \
             patch.object(shared_gpu_guard, 'broker_action', side_effect=AssertionError('No registration')), \
             patch.object(review.pacing, 'launch', side_effect=AssertionError('No launch')):
            # The actual local user hold is read; no GPU checks are called.
            with self.assertRaises((ValueError, KeyError)):
                review.fenced_launch(dict(self.report, evidence=str(ROOT)))


if __name__ == '__main__':
    unittest.main(verbosity=2)
