"""Real-scene classification and simulated transport; never controls a game."""
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

import native_ui_facade_route as route


class FixtureTransport:
    def __init__(self, frames):
        self.frames = iter(frames)
        self.last = frames[-1]
        self.now = 0.0
        self.calls = []
        self.frame = 0

    def sleep(self, seconds):
        self.now += seconds

    def __call__(self, command, **fields):
        self.calls.append((command, fields))
        if command == "screenshot":
            self.last = next(self.frames, self.last)
            Image.fromarray(self.last).save(fields["path"])
            self.frame += 1
        return dict(ok=True, frame=self.frame)


class NativeRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.refs, cls.receipts = route.load_references()

    def test_actual_native_title_fighter_arm_and_city_are_distinct(self):
        for expected, pixels in self.refs.items():
            with self.subTest(expected=expected):
                self.assertEqual(expected, route.classify_native(pixels, self.refs)["state"])

    def test_original_hd_off_scenes_have_a_separate_pinned_profile(self):
        refs, _ = route.load_references("native-stock")
        for expected, pixels in refs.items():
            with self.subTest(expected=expected):
                self.assertEqual(expected, route.classify_native(pixels, refs, "native-stock")["state"])

    def test_original_gray_hud_rejects_blank_and_menu_scenes(self):
        refs, _ = route.load_references("native-stock")
        for pixels in [np.zeros((240, 320, 3), np.uint8), refs["title"], refs["fighter"], refs["arm"]]:
            self.assertNotEqual("city", route.classify_native(pixels, refs, "native-stock")["state"])

    def test_unknown_reference_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown"):
            route.load_references("unregistered")

    def test_assembled_title_uses_its_own_pinned_actual_native_reference(self):
        refs,_=route.load_references("assembled-v1")
        for expected,pixels in refs.items():
            self.assertEqual(expected,route.classify_native(pixels,refs,"assembled-v1")["state"])
        self.assertEqual("unknown",route.classify_native(refs["title"],self.refs)["state"])

    def test_original_profile_requires_three_observations_per_prompt(self):
        refs, _ = route.load_references("native-stock")
        with tempfile.TemporaryDirectory() as directory:
            transport = FixtureTransport([refs[name] for name in
                ["title"]*3+["fighter"]*3+["arm"]*3+["city"]*3])
            proof = route.enter_city(dict(evidence=directory, debug_port=4377,
                route_reference_profile="native-stock"), timeout_per_state=2,
                _debug=transport, _clock=lambda: transport.now, _sleep=transport.sleep)
            self.assertTrue(proof["ok"])
            self.assertEqual(["title", "fighter", "arm"], [x["after_state"] for x in proof["inputs"]])
            self.assertTrue(all(g["consecutive"] == 3 for g in proof["gates"]))

    def test_city_rejects_actual_selection_and_title_scenes(self):
        for name in ("fighter", "arm", "title"):
            self.assertNotEqual("city", route.classify_native(self.refs[name], self.refs)["state"])

    def test_fighter_reference_acquisition_stops_before_selection_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = FixtureTransport([self.refs[name] for name in ["title"]*3+["fighter"]*3])
            proof = route.enter_city(dict(evidence=directory, debug_port=4377), stop_at="fighter",
                timeout_per_state=2, _debug=transport, _clock=lambda: transport.now, _sleep=transport.sleep)
            self.assertEqual("fighter", proof["final_state"])
            self.assertEqual(["title"], [x["after_state"] for x in proof["inputs"]])
            self.assertEqual(2, len(proof["gates"]))
            self.assertEqual("clear_input", transport.calls[-1][0])

    def test_blank_and_actual_fmv_are_unknown(self):
        blank = np.zeros((240, 320, 3), dtype=np.uint8)
        self.assertEqual("unknown", route.classify_native(blank, self.refs)["state"])
        path = route.ROOT / "dev-center-evidence/title-e-20261112-v13/native-v12-title.png"
        with Image.open(path) as image:
            actual_fmv = route.native_pixels(image)
        self.assertEqual("unknown", route.classify_native(actual_fmv, self.refs)["state"])

    def test_fighter_header_with_unverified_ship_label_is_not_confirmable(self):
        pixels = self.refs["fighter"].copy()
        pixels[50:68, 5:135] = 0
        self.assertEqual("fighter_other_or_label_unverified", route.classify_native(pixels, self.refs)["state"])

    def test_alternate_native_craft_labels_are_distinguished(self):
        refs, _ = route.load_craft_references()
        for name, pixels in refs.items():
            self.assertEqual(name, route.classify_craft(pixels, refs)["craft"])
        self.assertEqual("unverified", route.classify_craft(np.zeros((240, 320, 3), np.uint8), refs)["craft"])

    def test_alternate_craft_is_verified_after_each_down_input(self):
        refs, _ = route.load_references("native-stock");crafts, _ = route.load_craft_references()
        for craft, steps in [("mk3", ["mk3"]), ("astraea", ["mk3", "astraea"])]:
            with self.subTest(craft=craft), tempfile.TemporaryDirectory() as directory:
                frames=[refs["title"]]*3+[refs["fighter"]]*3
                for selected in steps:frames += [crafts[selected]]*3
                if craft=="astraea":
                    arms,_=route.load_craft_references(route.ASTRAEA_ARM_REFERENCES)
                    frames += [arms["arm2"]]*3+[arms["arm1"]]*3
                else:frames += [refs["arm"]]*3
                frames += [refs["city"]]*3
                transport=FixtureTransport(frames)
                proof=route.enter_city(dict(evidence=directory,debug_port=4377,route_reference_profile="native-stock"),
                    craft=craft,timeout_per_state=2,_debug=transport,_clock=lambda:transport.now,_sleep=transport.sleep)
                self.assertTrue(proof["ok"])
                self.assertEqual(len(steps),sum(x["button"]=="down" for x in proof["inputs"]))
                self.assertEqual(craft,proof["requested_craft"])
                if craft=="astraea":
                    self.assertEqual(["arm2","arm1"],[x["after_state"] for x in proof["inputs"] if x["after_state"].startswith("arm")])

    def test_astraea_arm_slots_are_distinct_and_blank_is_rejected(self):
        refs,_=route.load_craft_references(route.ASTRAEA_ARM_REFERENCES)
        for name,pixels in refs.items():self.assertEqual(name,route.classify_arm_slot(pixels,refs)["arm_slot"])
        self.assertEqual("unverified",route.classify_arm_slot(np.zeros((240,320,3),np.uint8),refs)["arm_slot"])

    def test_astraea_does_not_confirm_arm1_until_selection_changes(self):
        refs,_=route.load_references("native-stock");crafts,_=route.load_craft_references()
        arms,_=route.load_craft_references(route.ASTRAEA_ARM_REFERENCES)
        frames=[refs["title"]]*3+[refs["fighter"]]*3+[crafts["mk3"]]*3+[crafts["astraea"]]*3+[arms["arm2"]]*20
        with tempfile.TemporaryDirectory() as directory:
            transport=FixtureTransport(frames)
            with self.assertRaisesRegex(RuntimeError,"astraea-arm1"):
                route.enter_city(dict(evidence=directory,debug_port=4377,route_reference_profile="native-stock"),
                    craft="astraea",timeout_per_state=2,_debug=transport,_clock=lambda:transport.now,_sleep=transport.sleep)
            proof=json.loads(next(Path(directory).glob("native-facade-route-*/route-proof.json")).read_bytes())
            self.assertEqual(["arm2"],[x["after_state"] for x in proof["inputs"] if x["after_state"].startswith("arm")])

    def test_wrong_craft_after_down_is_never_confirmed(self):
        refs, _ = route.load_references("native-stock")
        with tempfile.TemporaryDirectory() as directory:
            transport=FixtureTransport([refs["title"]]*3+[refs["fighter"]]*20)
            with self.assertRaisesRegex(RuntimeError,"fighter-mk3"):
                route.enter_city(dict(evidence=directory,debug_port=4377,route_reference_profile="native-stock"),
                    craft="mk3",timeout_per_state=2,_debug=transport,_clock=lambda:transport.now,_sleep=transport.sleep)
            proof=json.loads(next(Path(directory).glob("native-facade-route-*/route-proof.json")).read_bytes())
            self.assertEqual(["title"],[x["after_state"] for x in proof["inputs"] if x["button"]=="confirm"])

    def test_composed_image_cannot_be_used_as_native_gate(self):
        with self.assertRaises(ValueError):
            route.native_pixels(Image.new("RGB", (1280, 960)))

    def execute(self, names, expect_success=True):
        with tempfile.TemporaryDirectory() as directory:
            frames = [self.refs[name] if name != "unknown" else np.zeros((240, 320, 3), np.uint8) for name in names]
            transport = FixtureTransport(frames)
            report = dict(evidence=directory, debug_port=4377)
            if expect_success:
                proof = route.enter_city(report, timeout_per_state=2, _debug=transport,
                    _clock=lambda: transport.now, _sleep=transport.sleep)
            else:
                with self.assertRaisesRegex(RuntimeError, "timed out"):
                    route.enter_city(report, timeout_per_state=2, _debug=transport,
                        _clock=lambda: transport.now, _sleep=transport.sleep)
                proof_path = next(Path(directory).glob("native-facade-route-*/route-proof.json"))
                proof = json.loads(proof_path.read_text())
                self.assertTrue(list(proof_path.parent.glob("failed-last-*.png")))
            self.assertTrue(all(command in {"screenshot", "get_registers", "set_input", "clear_input"}
                                for command, fields in transport.calls))
            self.assertEqual("clear_input", transport.calls[-1][0])
            return proof

    def test_direct_city_after_fighter_uses_two_confirmations(self):
        proof = self.execute(["title"]*3+["fighter"]*3+["city"]*3)
        self.assertTrue(proof["ok"])
        self.assertEqual(["title", "fighter"], [x["after_state"] for x in proof["inputs"]])
        self.assertTrue(all(g["consecutive"] == 3 and len(g["captures"]) == 3 for g in proof["gates"]))

    def test_optional_arm_is_observed_before_its_single_confirmation(self):
        proof = self.execute(["title"]*3+["fighter"]*3+["arm"]*3+["city"]*3)
        self.assertEqual(["title", "fighter", "arm"], [x["after_state"] for x in proof["inputs"]])
        self.assertEqual("city", proof["final_state"])

    def test_interrupted_observations_do_not_trigger_an_early_confirmation(self):
        proof = self.execute(["title"]*3+["fighter", "unknown"]+["fighter"]*3+["city"]*3)
        fighter = next(g for g in proof["gates"] if g["stage"] == "fighter-mk2")
        self.assertEqual([6, 7, 8], [x["frame"] for x in fighter["captures"]])
        self.assertEqual(2, len(proof["inputs"]))

    def test_unknown_state_retains_failure_evidence_and_sends_no_blind_confirm(self):
        proof = self.execute(["title"]*3+["unknown"]*6, expect_success=False)
        self.assertFalse(proof["ok"])
        self.assertEqual(["title"], [x["after_state"] for x in proof["inputs"]])
        self.assertFalse(proof["ram_writes"])
        self.assertFalse(proof["state_loads"])


if __name__ == "__main__":
    unittest.main()
