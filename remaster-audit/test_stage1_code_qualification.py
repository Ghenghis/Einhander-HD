import unittest
from stage1_code_qualification import qualification_errors


def results():
    proof = dict(errors=[], owned_process_exit=0, close=dict(port_closed=True),
        requested_entries=['0x0003A998'], samples=[dict(
            shadow=dict(shadow=dict(in_shadow=0, native_exec=1, divergences=0, skipped_device=0, records=[])),
            hot_candidates={'0x0003A998': dict(candidates=[dict(match=1, diff_passes=32, device_touch=0)])})])
    world = dict(errors=[], owned_process_exit=0, close=dict(port_closed=True), observations=[
        dict(elapsed_seconds=t, registers=dict(frame=f)) for t, f in [(0, 100), (1, 160), (2, 220), (12, 820)]])
    return proof, world


def nonleaf_results(address=0xB5C08):
    from stage1_code_qualification import NONLEAF_UNITS
    proof, world = results()
    entry = f'0x{address:08X}'
    proof['requested_entries'] = [entry]
    final = proof['samples'][-1]
    final['hot_candidates'] = {entry: dict(candidates=[
        dict(index=7, crc='0x1234ABCD', match=1, diff_passes=128, device_touch=0)])}
    units = [dict(candidate_index=7, code_crc='0x1234ABCD', cand=entry,
                  unit=f'0x{pc:08X}', exit=kind, clean=32, div=0, skip=0, last_div_kind=0)
             for pc, kind in NONLEAF_UNITS[address]]
    final['shadow']['shadow'].update(units=units, units_total=len(units),
                                    units_listed=len(units), unit_overflow=0)
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

    def test_every_known_nonleaf_requires_each_declared_path(self):
        from stage1_code_qualification import NONLEAF_UNITS
        for address, required in NONLEAF_UNITS.items():
            with self.subTest(address=address):
                self.assertEqual(qualification_errors(*nonleaf_results(address)), [])
                for index in range(len(required)):
                    proof, world = nonleaf_results(address)
                    shadow = proof['samples'][-1]['shadow']['shadow']
                    shadow['units'].pop(index)
                    shadow['units_total'] = shadow['units_listed'] = len(shadow['units'])
                    self.assertTrue(qualification_errors(proof, world))

    def test_complete_nonleaf_same_code_units_accepted(self):
        self.assertEqual(qualification_errors(*nonleaf_results()), [])

    def test_entry_counts_do_not_qualify_unobserved_continuations(self):
        proof, world = nonleaf_results()
        shadow = proof['samples'][-1]['shadow']['shadow']
        shadow['units'] = shadow['units'][:2]
        shadow['units_total'] = shadow['units_listed'] = 2
        errors = qualification_errors(proof, world)
        self.assertEqual(sum('0x800B5CD4' in e for e in errors), 2)

    def test_nonleaf_legacy_proof_without_units_rejected(self):
        proof, world = nonleaf_results()
        del proof['samples'][-1]['shadow']['shadow']['units']
        self.assertTrue(any('per-unit' in e for e in qualification_errors(proof, world)))

    def test_unit_counts_cannot_be_borrowed_from_another_native_variant(self):
        for key, value in [('candidate_index', 8), ('code_crc', '0x1234ABCE'),
                           ('cand', '0x000B5EB8'), ('unit', '0xA00B5CD4')]:
            proof, world = nonleaf_results()
            proof['samples'][-1]['shadow']['shadow']['units'][2][key] = value
            self.assertTrue(any('0x800B5CD4 call' in e for e in qualification_errors(proof, world)))

    def test_incomplete_truncated_or_failed_unit_records_rejected(self):
        for key, value in [('units_total', 5), ('units_listed', 3), ('unit_overflow', 1)]:
            proof, world = nonleaf_results()
            proof['samples'][-1]['shadow']['shadow'][key] = value
            self.assertTrue(qualification_errors(proof, world))
        for key, value in [('clean', 31), ('div', 1), ('skip', 1), ('last_div_kind', 16)]:
            proof, world = nonleaf_results()
            proof['samples'][-1]['shadow']['shadow']['units'][2][key] = value
            self.assertTrue(qualification_errors(proof, world))


if __name__ == '__main__':
    unittest.main()
