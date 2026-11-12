"""Offline acceptance-gate regression tests; no game connection or input."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

import ui_native_journey as native


class Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class NativeJourneyTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.journey = native.Journey(dict(evidence=str(self.root)))
        self.clock = Clock()
        self.clock_patch = patch.object(native, "time", self.clock)
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)
        self.black = np.zeros((240, 320, 3), dtype=np.uint8)
        self.title = self.black.copy()
        self.title[80:150, 20:300] = [0, 100, 180]
        self.title[165:195, 105:215] = [200, 200, 200]
        self.reference = self.root / "reference.png"
        Image.fromarray(self.title).save(self.reference)

    def command_sequence(self, sequence):
        values = iter(sequence)

        def reply(report, payload):
            request = json.loads(payload)
            self.assertEqual(request["cmd"], "screenshot")
            value = next(values)
            if isinstance(value, BaseException):
                raise value
            if isinstance(value, str):
                return dict(ok=False, error=value)
            Image.fromarray(value).save(request["path"])
            return dict(ok=True)

        return patch.object(native, "command", side_effect=reply)

    def notes(self):
        return [json.loads(line) for line in self.journey.log.read_text().splitlines()]

    def test_title_does_not_accept_stale_thumbnail_while_display_disabled(self):
        Image.fromarray(self.title).save(self.journey.gate)
        with patch.object(native, "command", return_value=dict(ok=False, error="display disabled")) as request:
            with self.assertRaisesRegex(RuntimeError, "Title not observed"):
                self.journey.title(seconds=.5)
        self.assertGreater(request.call_count, 1)
        self.assertNotIn("title_observed", [r["kind"] for r in self.notes()])
        self.assertLessEqual(self.clock.now, .7)

    def test_title_waits_for_fresh_valid_image_after_transition(self):
        Image.fromarray(self.title).save(self.journey.gate)
        with self.command_sequence(["display disabled", self.black, self.title]) as request:
            self.journey.title(seconds=2)
        self.assertEqual(request.call_count, 3)
        self.assertEqual(self.notes()[-1]["kind"], "title_observed")

    def test_like_does_not_accept_stale_thumbnail_and_still_times_out(self):
        Image.fromarray(self.title).save(self.journey.gate)
        with patch.object(native, "command", return_value=dict(ok=False, error="display disabled")):
            with self.assertRaisesRegex(RuntimeError, "Expected native scene not observed"):
                self.journey.like(self.reference, [(0, 0, 320, 240)], seconds=.5)
        self.assertEqual(self.notes()[-1]["kind"], "gate_failed")
        self.assertIsNone(self.notes()[-1]["distances"])
        self.assertLessEqual(self.clock.now, .7)

    def test_like_requires_three_consecutive_real_observations(self):
        with self.command_sequence([self.title, self.title, self.title]) as request:
            self.journey.like(self.reference, [(0, 0, 320, 240)], seconds=2)
        self.assertEqual(request.call_count, 3)
        self.assertEqual(self.notes()[-1]["kind"], "reference_observed")

    def test_transition_resets_reference_observation_streak(self):
        sequence = [self.title, self.title, "display disabled", self.title, self.title, self.title]
        with self.command_sequence(sequence) as request:
            self.journey.like(self.reference, [(0, 0, 320, 240)], seconds=2)
        self.assertEqual(request.call_count, 6)
        self.assertEqual(self.notes()[-1]["kind"], "reference_observed")

    def test_different_scene_resets_reference_observation_streak(self):
        sequence = [self.title, self.title, self.black, self.title, self.title, self.title]
        with self.command_sequence(sequence) as request:
            self.journey.like(self.reference, [(0, 0, 320, 240)], seconds=2)
        self.assertEqual(request.call_count, 6)

    def test_real_screenshot_error_propagates_from_both_gates(self):
        for gate in (lambda: self.journey.title(seconds=2),
                     lambda: self.journey.like(self.reference, [(0, 0, 320, 240)], seconds=2)):
            with self.subTest(gate=gate):
                with patch.object(native, "command", return_value=dict(ok=False, error="PNG write failed")) as request:
                    with self.assertRaisesRegex(RuntimeError, "PNG write failed"):
                        gate()
                self.assertEqual(request.call_count, 1)
                self.assertEqual(self.clock.now, 0)

    def test_transport_error_is_not_treated_as_display_transition(self):
        with self.command_sequence([TimeoutError("debug socket timeout")]):
            with self.assertRaisesRegex(TimeoutError, "debug socket timeout"):
                self.journey.title(seconds=2)
        self.assertEqual(self.clock.now, 0)

    def test_successful_reply_without_thumbnail_fails(self):
        with patch.object(native, "command", return_value=dict(ok=True)):
            with self.assertRaisesRegex(RuntimeError, "Native state thumbnail missing"):
                self.journey.title(seconds=2)


if __name__ == "__main__":
    unittest.main()
