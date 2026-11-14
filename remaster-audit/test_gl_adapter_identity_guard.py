"""Focused pure-data controls; no process, GL, window, socket or file operations."""
import unittest

from gl_adapter_identity_guard import AdapterEvidenceError, validate_active_adapter

MODEL = 'NVIDIA GeForce RTX 3090 Ti'
STARTUP = (b'psxrecomp: GL identity vendor="NVIDIA Corporation" '
           b'renderer="NVIDIA GeForce RTX 3090 Ti/PCIe/SSE2" version="4.6 FIXTURE" truncated=0\n'
           b'psxrecomp: GL GPU pipeline ready (internal scale 2x, FIXTURE)\n')


def present(total):
    return dict(ok=True, total=total, events=[] if not total else
                [[total-1, 50, 'vram', 100, [0, 0, 640, 480], [0, 0, 640, 480], [0, 0, 0], 0, [0, 0, 0, 1]]],
                requested=1, returned=min(1, total), missing=0, truncated=0, capacity=16384)


def evidence():
    return dict(stdout=STARTUP, expected_model=MODEL, expected_process=(123, 1000.5),
                process_before=(123, 1000.5), process_after=(123, 1000.5),
                present_before_owner_bracket=((123, 1000.5), (123, 1000.5)),
                present_after_owner_bracket=((123, 1000.5), (123, 1000.5)),
                present_before=present(2), present_after=present(3))


class AdapterGuardTests(unittest.TestCase):
    def refused(self, modify):
        args=evidence();modify(args)
        with self.assertRaises(AdapterEvidenceError):validate_active_adapter(**args)

    def test_valid_model_and_advancing_owned_gl(self):
        self.assertEqual(validate_active_adapter(**evidence())['after_total'], 3)

    def test_empty_initial_ring_is_allowed(self):
        args=evidence();args['present_before']=present(0)
        self.assertEqual(validate_active_adapter(**args)['before_total'], 0)

    def test_wrong_model(self):
        self.refused(lambda a:a.update(stdout=STARTUP.replace(b'3090 Ti',b'3060')))

    def test_model_substring_does_not_accept_another_sku(self):
        self.refused(lambda a:a.update(expected_model='NVIDIA GeForce RTX 3090'))

    def test_missing_and_duplicate_identity(self):
        for text in (b'',STARTUP+STARTUP):
            with self.subTest(text=text):self.refused(lambda a:a.update(stdout=text))

    def test_truncated_identity(self):
        self.refused(lambda a:a.update(stdout=STARTUP.replace(b'truncated=0',b'truncated=1')))

    def test_ready_marker_is_required(self):
        self.refused(lambda a:a.update(stdout=STARTUP.splitlines()[0]+b'\n'))

    def test_software_fallback_rejects_even_matching_adapter(self):
        self.refused(lambda a:a.update(stdout=STARTUP+b'psxrecomp: GL pipeline init failed: software\n'))

    def test_actual_software_fallback_text(self):
        fallback='psxrecomp: GL pipeline init failed — software rendering\n'.encode('utf-8')
        self.refused(lambda a:a.update(stdout=STARTUP+fallback))

    def test_identity_must_precede_ready(self):
        first, second=STARTUP.splitlines(keepends=True)
        self.refused(lambda a:a.update(stdout=second+first))

    def test_complete_model_case_is_normalized(self):
        args=evidence();args['expected_model']=MODEL.lower()
        self.assertTrue(validate_active_adapter(**args)['model_only'])

    def test_actual_dual_raster_ready_variant(self):
        args=evidence()
        args['stdout']=(STARTUP.splitlines()[0]+b'\n'
                        b'psxrecomp: GL GPU pipeline ready (dual-raster, '
                        b'internal scale 2x, SW@1x authority, no FBO readback)\n')
        self.assertTrue(validate_active_adapter(**args)['listener_brackets_validated'])

    def test_laptop_suffix_does_not_match(self):
        self.refused(lambda a:a.update(stdout=STARTUP.replace(b'Ti/PCIe',b'Ti Laptop GPU/PCIe')))

    def test_both_rpc_queries_require_owned_listener_brackets(self):
        for name in ('present_before_owner_bracket','present_after_owner_bracket'):
            for bracket in ((), ((124,1000.5),(124,1000.5)),
                            ((123,1000.5),(123,1001.5)),
                            ((124,1000.5),(123,1000.5))):
                with self.subTest(name=name,bracket=bracket):
                    self.refused(lambda a:a.update({name:bracket}))

    def test_strict_utf8_and_original_bytes_are_required(self):
        for text in (STARTUP.decode('utf-8'), STARTUP+b'\xff', STARTUP+b'\0'):
            with self.subTest(text_type=type(text).__name__):
                self.refused(lambda a:a.update(stdout=text))

    def test_nonadvancing_or_decreasing_ring(self):
        for count in (1,2):
            with self.subTest(count=count):self.refused(lambda a:a.update(present_after=present(count)))

    def test_reused_pid_or_other_process(self):
        for identity in ((123,1001.5),(124,1000.5)):
            with self.subTest(identity=identity):self.refused(lambda a:a.update(process_after=identity))

    def test_incomplete_or_failed_ring(self):
        for change in ({'missing':1},{'truncated':1},{'ok':False},{'requested':600},{'total':True}):
            with self.subTest(change=change):
                self.refused(lambda a:a['present_after'].update(change))

    def test_stale_gl_event(self):
        self.refused(lambda a:a['present_after']['events'][0].__setitem__(0,1))

    def test_gl_error_and_blank_only_reject(self):
        self.refused(lambda a:a['present_after']['events'][0].__setitem__(7,1282))
        self.refused(lambda a:a['present_after']['events'][0].__setitem__(2,'blank'))

    def test_invalid_fields_or_log_bound(self):
        self.refused(lambda a:a.update(stdout=STARTUP.replace(b'NVIDIA Corporation',b'?')))
        self.refused(lambda a:a.update(stdout=b'x'*(1024*1024+1)))


if __name__ == '__main__':unittest.main()
