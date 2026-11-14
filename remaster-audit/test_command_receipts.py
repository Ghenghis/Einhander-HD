import concurrent.futures
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import launch_ui_candidate as ui


class FixedTime:
    @staticmethod
    def now(unused):
        return datetime(2026, 11, 13, 0, 0, 0, tzinfo=timezone.utc)


class CommandReceiptTests(unittest.TestCase):
    def test_concurrent_same_timestamp_receipts_are_complete_and_unique(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / 'commands'
            directory.mkdir()
            stopped = threading.Event()
            failures = []

            def audit():
                while not stopped.is_set():
                    for path in directory.glob('*.json'):
                        try:
                            value = json.loads(path.read_bytes())
                            self.assertEqual(value['padding'], 'x' * 2000)
                        except Exception as error:
                            failures.append(str(error))
                    time.sleep(.001)

            reader = threading.Thread(target=audit)
            reader.start()
            try:
                with patch.object(ui, 'datetime', FixedTime):
                    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                        paths = list(pool.map(lambda index: ui.write_command_receipt(
                            directory, dict(index=index, padding='x' * 2000)), range(256)))
            finally:
                stopped.set()
                reader.join()
            self.assertEqual(failures, [])
            self.assertEqual(len(set(paths)), 256)
            self.assertEqual(len(list(directory.glob('*.json'))), 256)
            self.assertEqual({json.loads(path.read_bytes())['index'] for path in paths}, set(range(256)))
            self.assertEqual(list(directory.glob('*.tmp')), [])

    def test_a_forced_name_collision_keeps_the_existing_receipt(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / 'commands'
            with patch.object(ui, 'datetime', FixedTime), patch.object(
                    ui.uuid, 'uuid4', return_value=SimpleNamespace(hex='forced-collision')):
                first = ui.write_command_receipt(directory, dict(index=1))
                before = first.read_bytes()
                with self.assertRaises(FileExistsError):
                    ui.write_command_receipt(directory, dict(index=2))
            self.assertEqual(first.read_bytes(), before)
            temporary = list(directory.glob('*.tmp'))
            self.assertEqual(len(temporary), 1)
            self.assertEqual(json.loads(temporary[0].read_bytes()), dict(index=2))

    def test_failed_publication_retains_unpublished_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / 'commands'
            with patch.object(ui.os, 'link', side_effect=OSError('injected publication failure')):
                with self.assertRaisesRegex(OSError, 'injected publication failure'):
                    ui.write_command_receipt(directory, dict(index=3))
            self.assertEqual(list(directory.glob('*.json')), [])
            temporary = list(directory.glob('*.tmp'))
            self.assertEqual(len(temporary), 1)
            self.assertEqual(json.loads(temporary[0].read_bytes()), dict(index=3))


if __name__ == '__main__':
    unittest.main()
