import contextlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import launch_hd
import test_material_profiles as fixtures


class HdLaunchTests(unittest.TestCase):
    def setUp(self):
        fixtures.MaterialProfileTests.setUp(self)
        fixtures.MaterialProfileTests.game_paths(self)
        self.executable = self.root / "build-release/Einhander_Recompiled.exe"
        self.executable.write_bytes(b"fixture only, never executed")

    def save(self, **extra):
        fixtures.MaterialProfileTests.receipt(self)
        return self.materials.dispatch(dict(action="save", profile="aurora-teal", enemy_profile="gold-obsidian", **extra))

    def test_no_saved_selection_launches_stock_and_clears_inherited_skin(self):
        p = launch_hd.prepare_hd_launch(self.root)
        self.assertEqual(p["selection_source"], "no_saved_preset")
        self.assertEqual(p["environment_overrides"]["PSXRECOMP_SKIN_PROFILE"], "stock")
        self.assertEqual(p["environment_overrides"]["PSXRECOMP_SKIN_DETAIL_PATH"], "")
        self.assertEqual(p["arguments"][0], str(self.executable))

    def test_saved_material_and_details_reach_direct_game_arguments(self):
        fixtures.MaterialProfileTests.detail_asset(self)
        self.save(detail_map="gold-obsidian-engraved")
        p = launch_hd.prepare_hd_launch(self.root)
        self.assertEqual((p["profile"], p["enemy_profile"]), ("aurora-teal", "gold-obsidian"))
        self.assertEqual(p["selection_source"], "explicit_saved_preset")
        self.assertIn("--no-launcher", p["arguments"])
        self.assertNotIn("--launcher", p["arguments"])
        self.assertTrue(p["environment_overrides"]["PSXRECOMP_SKIN_DETAIL_PATH"].endswith("gold-obsidian-engraved.png"))

    def test_changed_saved_descriptor_fails_instead_of_silent_stock(self):
        saved = self.save()
        descriptor = Path(saved["config_path"])
        descriptor.write_bytes(descriptor.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Saved skin preset"):
            launch_hd.prepare_hd_launch(self.root)

    def test_changed_runtime_receipt_is_rejected(self):
        self.save()
        (self.root / "built/Material-runtime.exe").write_bytes(b"different executable")
        with self.assertRaises(ValueError):
            launch_hd.prepare_hd_launch(self.root)

    def test_explicit_stock_recovers_from_invalid_pointer_without_changing_it(self):
        self.save()
        pointer = self.root / "tools/material-selection.json"
        pointer.write_text("invalid JSON")
        p = launch_hd.prepare_hd_launch(self.root, stock=True)
        self.assertEqual(p["selection_source"], "explicit_stock")
        self.assertEqual(pointer.read_text(), "invalid JSON")

    def test_check_never_launches_and_forwards_game_arguments(self):
        prepared = launch_hd.prepare_hd_launch(self.root, game_arguments=["--window-title", "HD test"])
        self.assertEqual(prepared["arguments"][-2:], ["--window-title", "HD test"])
        with patch("launch_hd.prepare_hd_launch", return_value=prepared), patch("launch_hd.subprocess.run") as run, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(launch_hd.main(["--check"]), 0)
            run.assert_not_called()
            self.assertFalse(json.loads(output.getvalue())["game_launched"])


if __name__ == "__main__":
    unittest.main()
