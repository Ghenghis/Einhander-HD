"""Synthetic source/draw boundary tests; no GPU, disc, PNG decoding or real capture."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

from source_draw_admission import admit, crc

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
LEGACY = ROOT / 'remaster-audit/fullgame-prep/static-extraction/validate_predicted.py'


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='fixture-', dir=HERE)
        self.base = Path(self.temporary.name).resolve()
        self.assertTrue(self.base.is_relative_to(HERE))
        self.addCleanup(self.temporary.cleanup)
        self.words = bytes(range(256)) * 128
        self.clut = struct.pack('<16H', *range(0x8000, 0x8010))
        self.key = crc(self.words) + '-' + crc(self.clut)
        self.static = self.base / 'static.words.bin'
        self.static.write_bytes(self.words)
        self.source = self.base / 'live' / self.key
        self.source.parent.mkdir()
        self.meta = dict(key=self.key, depth=0, clut_xy=[0, 504], known_words=16384, total_words=16384)
        self.put('.words.bin', self.words)
        self.put('.clut.bin', self.clut)
        self.put('.valid.bin', b'\1' * 16384)
        self.put_meta()
        self.draw = dict(event='source_draw_query_matched', key=self.key, frame=150, source_kind='native_page',
                         depth=0, semi=-1, page_xy=[832, 0], clut_xy=[0, 504],
                         native_words=[64, 256], uv_bounds=[0, 0, 63, 63], xy=[[10, 10], [74, 10], [10, 74]])
        self.log = self.base / 'capture.jsonl'
        self.put_draw(self.draw)

    def put(self, suffix, data):
        Path(str(self.source) + suffix).write_bytes(data)

    def put_meta(self):
        self.put('.source.json', json.dumps(self.meta).encode())

    def put_draw(self, row):
        self.log.write_text(json.dumps(row) + '\n', encoding='utf-8')

    def check(self):
        return admit(self.static, self.source, self.key, [832, 0], [0, 504], 0, [100, 200], [self.log])

    def test_exact_source_and_matching_draw_pass(self):
        report = self.check()
        self.assertTrue(report['passed'], report)
        self.assertEqual(report['matched_draws'][0]['frame'], 150)
        self.assertEqual(len(report['inputs']), 6)

    def test_complete_source_without_a_draw_is_rejected(self):
        self.log.write_text('', encoding='utf-8')
        self.assertFalse(self.check()['passed'])

    def test_different_clut_slot_page_key_depth_frame_or_source_kind_cannot_satisfy(self):
        for field, value in [('clut_xy', [0, 503]), ('page_xy', [768, 0]), ('key', self.key[:9] + '00000000'),
                             ('depth', 1), ('frame', 250), ('frame', True), ('source_kind', 'static_prediction')]:
            with self.subTest(field=field, value=value):
                row = copy.deepcopy(self.draw)
                row[field] = value
                self.put_draw(row)
                self.assertFalse(self.check()['passed'])

    def test_non_draw_event_or_incomplete_primitive_cannot_satisfy(self):
        for field, value in [('event', 'source_dump'), ('uv_bounds', []), ('uv_bounds', [0, 0, 256, 10]),
                             ('native_words', [16, 32]), ('xy', None), ('semi', None)]:
            with self.subTest(field=field):
                row = copy.deepcopy(self.draw)
                row[field] = value
                self.put_draw(row)
                self.assertFalse(self.check()['passed'])

    def test_bad_or_missing_metadata_is_rejected(self):
        original = copy.deepcopy(self.meta)
        for field, value in [('key', 'DEADBEEF-00000000'), ('depth', 1), ('clut_xy', [0, 503]),
                             ('known_words', None), ('total_words', 1), ('predicted', True),
                             ('raw_origin', 'static_disc_prediction')]:
            with self.subTest(field=field):
                self.meta = copy.deepcopy(original)
                self.meta[field] = value
                self.put_meta()
                self.assertFalse(self.check()['passed'])

    def test_empty_truncated_or_unknown_validity_rejected(self):
        for valid in (b'', b'\1' * 16383, b'\1' * 16383 + b'\0'):
            self.put('.valid.bin', valid)
            self.assertFalse(self.check()['passed'])
        self.put('.valid.bin', b'\xff' * 16384)
        self.assertTrue(self.check()['passed'])

    def test_corrupted_words_or_clut_rejected(self):
        self.put('.words.bin', self.words[:-1] + b'\0')
        self.assertFalse(self.check()['passed'])
        self.put('.words.bin', self.words)
        self.put('.clut.bin', self.clut[:-2])
        self.assertFalse(self.check()['passed'])

    def test_malformed_log_is_not_ignored(self):
        with self.log.open('a', encoding='utf-8') as stream:
            stream.write('{broken\n')
        report = self.check()
        self.assertFalse(report['passed'])
        self.assertEqual(report['malformed_lines'][0]['line'], 2)

    def test_explicit_frame_window_required(self):
        with self.assertRaises(ValueError):
            admit(self.static, self.source, self.key, [832, 0], [0, 504], 0, [200, 100], [self.log])

    def test_complete_8bpp_page_and_clut_pass(self):
        self.words *= 2
        self.clut = struct.pack('<256H', *range(0x8000, 0x8100))
        self.key = crc(self.words) + '-' + crc(self.clut)
        self.source = self.source.parent / self.key
        self.static.write_bytes(self.words)
        self.meta.update(key=self.key, depth=1, known_words=32768, total_words=32768)
        self.put_meta()
        self.put('.words.bin', self.words)
        self.put('.clut.bin', self.clut)
        self.put('.valid.bin', b'\1' * 32768)
        self.draw.update(key=self.key, depth=1, native_words=[128, 256])
        self.put_draw(self.draw)
        report = admit(self.static, self.source, self.key, [832, 0], [0, 504], 1, [100, 200], [self.log])
        self.assertTrue(report['passed'], report)

    def test_cli_writes_a_report_and_returns_failure_without_draw(self):
        output = self.base / 'admission.json'
        self.log.write_text('', encoding='utf-8')
        result = subprocess.run([sys.executable, '-B', str(HERE / 'source_draw_admission.py'),
            '--static-words', str(self.static), '--source-base', str(self.source), '--key', self.key,
            '--page', '832', '0', '--clut', '0', '504', '--depth', '0', '--frames', '100', '200',
            '--draws', str(self.log), '--out', str(output)], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(json.loads(output.read_text())['passed'])

    def test_verbatim_real_recorder_row_rekeyed_to_the_synthetic_source(self):
        row = json.loads((HERE / 'real-draw-row.jsonl').read_text())
        self.assertNotIn('uv_vertices', row)
        row['key'] = self.key
        self.meta['clut_xy'] = row['clut_xy']
        self.put_meta()
        self.put_draw(row)
        report = admit(self.static, self.source, self.key, row['page_xy'], row['clut_xy'],
                       row['depth'], [row['frame'], row['frame']], [self.log])
        self.assertTrue(report['passed'], report)

    def test_unlisted_clut_legacy_gate_passes_without_draw_but_new_gate_requires_exact_draw(self):
        spec = importlib.util.spec_from_file_location('legacy_predicted', LEGACY)
        legacy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(legacy)
        stage = self.base / 'stage'
        (stage / 'textures').mkdir(parents=True)
        tex = self.key[:8]
        (stage / 'textures' / (tex + '.words.bin')).write_bytes(self.words)
        (stage / 'textures.json').write_text(json.dumps([dict(tex=tex, confidence='static', kinds=['strip'], sources=[dict(kind='strip')])]))
        (stage / 'keys.json').write_text('[]')
        keys = self.base / 'keys.json'
        keys.write_text(json.dumps([self.key]))
        self.log.write_text('', encoding='utf-8')
        prior = legacy.gate(str(stage), [str(self.source.parent)], keys_file=str(keys))
        self.assertTrue(prior['pass_'], prior)
        self.assertFalse(self.check()['passed'])
        row = copy.deepcopy(self.draw)
        row['clut_xy'] = [0, 503]
        self.put_draw(row)
        self.assertFalse(self.check()['passed'])
        self.put_draw(self.draw)
        self.assertTrue(self.check()['passed'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
