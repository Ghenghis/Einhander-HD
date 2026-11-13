import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
from gpu_capture_guard import require_quiet_gpu,queue_state

class GpuGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'GPU-RESERVED').write_text('owned test reservation')
    def check(self,q=None):
        return require_quiet_gpu(root=self.root,fetch_queue=lambda:q if q is not None else dict(queue_running=[],queue_pending=[]))
    def test_reservation_required(self):
        (self.root/'GPU-RESERVED').unlink()
        with self.assertRaisesRegex(RuntimeError,'Reserve'):self.check()
    def test_live_holder_refused_even_if_queue_is_empty(self):
        (self.root/'GPU-LOCK.json').write_text(json.dumps(dict(owner='artist',expires_epoch=101)))
        with self.assertRaisesRegex(RuntimeError,'artist'):self.check()
    def test_running_and_pending_jobs_are_both_refused(self):
        for key in ('queue_running','queue_pending'):
            q=dict(queue_running=[],queue_pending=[]);q[key]=[dict(job='art')]
            with self.assertRaisesRegex(RuntimeError,'running or pending'):self.check(q)
    def test_expired_holder_still_needs_owner_release_and_is_not_deleted(self):
        lock=self.root/'GPU-LOCK.json';lock.write_text(json.dumps(dict(owner='expired',expires_epoch=99)))
        with self.assertRaisesRegex(RuntimeError,'owner to release'):self.check()
        self.assertTrue(lock.exists())
    def test_malformed_queue_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,'malformed'):self.check(dict(queue_running='unknown',queue_pending=[]))
    def test_reservation_change_during_queue_read_refused(self):
        def changed():
            (self.root/'GPU-RESERVED').write_text('different reservation')
            return dict(queue_running=[],queue_pending=[])
        with self.assertRaisesRegex(RuntimeError,'changed'):
            require_quiet_gpu(root=self.root,fetch_queue=changed)
    def test_down_server_without_holder_is_quiet(self):
        r=require_quiet_gpu(root=self.root,fetch_queue=lambda:None)
        self.assertFalse(r['comfy_server_reachable'])
    def test_http_error_is_unknown_queue_state(self):
        with patch('gpu_capture_guard.urllib.request.urlopen',side_effect=urllib.error.HTTPError('http://localhost',503,'busy',{},None)):
            with self.assertRaisesRegex(RuntimeError,'HTTP error'):queue_state()
    def test_timeout_is_unknown_queue_state(self):
        with patch('gpu_capture_guard.urllib.request.urlopen',side_effect=urllib.error.URLError(TimeoutError('timed out'))):
            with self.assertRaisesRegex(RuntimeError,'unknown state'):queue_state()
    def test_explicit_connection_refusal_means_server_absent(self):
        with patch('gpu_capture_guard.urllib.request.urlopen',side_effect=urllib.error.URLError(ConnectionRefusedError(10061,'refused'))):
            self.assertIsNone(queue_state())

if __name__=='__main__':unittest.main()
