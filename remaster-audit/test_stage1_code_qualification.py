import unittest
from stage1_code_qualification import qualification_errors


def results():
    proof = dict(errors=[], owned_process_exit=0, close=dict(port_closed=True),
        requested_entries=['0x000B5C08'], samples=[dict(
            shadow=dict(shadow=dict(in_shadow=0, native_exec=1, divergences=0, skipped_device=0, records=[])),
            hot_candidates={'0x000B5C08': dict(candidates=[dict(match=1, diff_passes=32, device_touch=0)])})])
    world = dict(errors=[], owned_process_exit=0, close=dict(port_closed=True), observations=[
        dict(elapsed_seconds=t, registers=dict(frame=f)) for t, f in [(0, 100), (1, 160), (2, 220), (12, 820)]])
    return proof, world


class QualificationTests(unittest.TestCase):
    def test_completed_comparisons_and_progress(self):
        self.assertEqual(qualification_errors(*results()), [])

    def test_early_passes_do_not_accept_unfinished_shadow(self):
        proof, world = results()
        proof['samples'][-1]['shadow']['shadow']['in_shadow'] = 1
        self.assertIn('Final shadow comparison is unfinished', qualification_errors(proof, world))

    def test_frozen_guest_rejected_even_with_completed_shadow(self):
        proof, world = results()
        world['observations'][-1]['registers']['frame'] = 220
        self.assertTrue(any('No guest frame progress' in e for e in qualification_errors(proof, world)))

    def test_native_execution_must_be_restored(self):
        proof, world = results()
        proof['samples'][-1]['shadow']['shadow']['native_exec'] = 0
        self.assertIn('Native execution was not restored after comparison', qualification_errors(proof, world))

    def test_short_pause_then_progress_is_not_a_freeze(self):
        proof, world = results()
        world['observations'][2]['registers']['frame'] = 160
        self.assertEqual(qualification_errors(proof, world), [])

    def test_rewound_or_nonmonotonic_observations_rejected(self):
        for field, value in [('elapsed_seconds', 0), ('frame', 99)]:
            proof, world = results()
            row = world['observations'][1]
            (row if field == 'elapsed_seconds' else row['registers'])[field] = value
            self.assertTrue(qualification_errors(proof, world))

    def test_missing_or_failed_comparisons_rejected(self):
        for field, value in [('divergences', 1), ('skipped_device', 1), ('in_shadow', None)]:
            proof, world = results()
            proof['samples'][-1]['shadow']['shadow'][field] = value
            self.assertTrue(qualification_errors(proof, world))
        proof, world = results()
        proof['samples'][-1]['hot_candidates'] = {}
        self.assertTrue(qualification_errors(proof, world))


if __name__ == '__main__':
    unittest.main()
