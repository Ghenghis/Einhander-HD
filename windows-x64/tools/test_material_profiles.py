import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from material_profiles import CONTRACT, DEFAULT_PLAYER_KEYS, DEFAULT_STRENGTH, DETAIL_IDS, ENEMY_KEYS, FIGHTER_KEY, PLAYER_KEYS, PROFILE_MAP, MaterialProfiles, enemy_selection, saved_selection, selection
from launch_material import main, prepare_launch


class MaterialProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.pack = self.root / "hd-textures" / "stage1-v1"
        self.pngs = self.pack / "einhander-texture-replacements"
        self.pngs.mkdir(parents=True)
        self.source = self.pngs / (FIGHTER_KEY + ".png")
        self.source.write_bytes(b"immutable fighter fixture")
        for key in PLAYER_KEYS + ENEMY_KEYS:
            if key != FIGHTER_KEY:
                (self.pngs / (key + ".png")).write_bytes(("immutable atlas fixture " + key).encode())
        self.other = self.pngs / "UNRELATED-PAGE.png"
        self.other.write_bytes(b"unrelated HD page remains available")
        self.sha = hashlib.sha256(self.source.read_bytes()).hexdigest()
        (self.pack / "manifest.json").write_text(json.dumps(dict(files=[dict(key=path.stem, sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in self.pngs.iterdir()])))
        self.materials = MaterialProfiles(self.root, lambda: [dict(key=FIGHTER_KEY, width=1024, height=1024, sha256=self.sha, url="/dev/skins/source/" + FIGHTER_KEY + ".png")])

    def receipt(self):
        executable = self.root / "built" / "Material-runtime.exe"
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b"fixture; not executable")
        (self.root / "tools").mkdir(parents=True, exist_ok=True)
        receipt = self.root / "tools" / "material-runtime.json"
        receipt.write_text(json.dumps(dict(schema_version=1, contract=CONTRACT, material_shader=True, dual_profiles=True, detail_maps=True, profiles=list(PROFILE_MAP), player_keys=list(PLAYER_KEYS), enemy_keys=list(ENEMY_KEYS), executable=str(executable), sha256=hashlib.sha256(executable.read_bytes()).hexdigest())))
        return executable

    def detail_asset(self, identity=DETAIL_IDS[0]):
        from PIL import Image
        folder = self.root / "tools" / "skin_collection" / "materials"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (identity + ".png")
        Image.new("RGB", (4, 4), (180, 140, 30)).save(path)
        manifest = folder / "materials.json"
        previous = json.loads(manifest.read_text())["maps"] if manifest.is_file() else []
        previous = [row for row in previous if row["id"] != identity]
        previous.append(dict(id=identity, label="Fixture Material", width=4, height=4, sha256=hashlib.sha256(path.read_bytes()).hexdigest(), unchanged_generated_png=True))
        manifest.write_text(json.dumps(dict(maps=previous)))
        return path, manifest

    def game_paths(self):
        (self.root / "game.toml").write_text("[game]\n")
        bios = self.root / "build-release" / "bios"
        bios.mkdir(parents=True)
        (bios / "SCPH1001.BIN").write_bytes(b"fixture")
        rom = self.root.parent / "ROM"
        rom.mkdir()
        (rom / "Einhander (USA).cue").write_text("fixture")

    def test_defaults_and_eight_exact_collection_profiles(self):
        self.assertEqual(selection({}), ("stock", 0., list(DEFAULT_PLAYER_KEYS)))
        self.assertEqual(enemy_selection({}), ("stock", 0., list(ENEMY_KEYS)))
        catalog = self.materials.catalog()
        self.assertEqual(len(catalog["profiles"]), 15)
        self.assertEqual(catalog["strength_default"], DEFAULT_STRENGTH)
        aurora = next(profile for profile in catalog["profiles"] if profile["id"] == "aurora-teal")
        self.assertEqual(aurora["primary"], "#16E6CD")
        self.assertEqual(aurora["accent_rgb"], [83/255, 246/255, 1.])
        self.assertFalse(catalog["runtime"]["ready"])

    def test_palette_categories_preserve_gold_and_add_three_neon_directions(self):
        catalog = self.materials.catalog()
        neon = {profile["id"] for profile in catalog["profiles"] if profile["category"] == "Neon-Cyberpunk"}
        self.assertEqual(neon, {"neon-circuit", "ultraviolet-grid", "reactor-lime"})
        gold = {profile["id"] for profile in catalog["profiles"] if profile["category"] == "Gold"}
        self.assertEqual(gold, {"gold-obsidian", "aurora-gilt", "crimson-regalia", "glacier-gilt"})
        self.assertEqual(PROFILE_MAP["neon-circuit"]["primary"], "#00F0FF")
        self.assertEqual(PROFILE_MAP["ultraviolet-grid"]["accent"], "#38F6FF")
        self.assertEqual(PROFILE_MAP["reactor-lime"]["accent"], "#F8FF59")

    def test_all_six_detail_identities_include_separate_neon_maps(self):
        for identity in DETAIL_IDS:
            self.detail_asset(identity)
        catalog = self.materials.catalog()
        self.assertEqual(len(catalog["detail_maps"]), 6)
        neon = [row for row in catalog["detail_maps"] if row["category"] == "Neon-Cyberpunk"]
        self.assertEqual({row["id"] for row in neon}, {"neon-circuit-tracery", "ultraviolet-plasma-grid", "reactor-lime-hazard"})
        for row in neon:
            result = self.materials.stage(dict(profile="neon-circuit", detail_map=row["id"]))
            self.assertEqual(result["descriptor"]["detail_map"], row["id"])
            self.assertEqual(result["descriptor"]["authored_detail"]["player"]["sha256"], row["sha256"])
            self.assertEqual(result["descriptor"]["authored_detail"]["player"]["wrap"], "mirrored_repeat")

    def test_no_detail_is_default_and_inherited_detail_paths_are_cleared(self):
        result = self.materials.stage(dict(profile="aurora-teal"))
        env = result["descriptor"]["environment"]
        self.assertEqual(result["descriptor"]["detail_map"], "none")
        self.assertEqual(result["descriptor"]["enemy_detail_map"], "none")
        self.assertEqual(env["PSXRECOMP_SKIN_DETAIL_PATH"], "")
        self.assertEqual(env["PSXRECOMP_SKIN_ENEMY_DETAIL_PATH"], "")

    def test_authored_detail_can_enrich_stock_colors_with_separate_receipt(self):
        path, _ = self.detail_asset()
        result = self.materials.stage(dict(profile="stock", detail_map=DETAIL_IDS[0]))
        descriptor = result["descriptor"]
        self.assertEqual(descriptor["profile"], "stock")
        self.assertEqual(descriptor["authored_detail"]["player"]["path"], str(path))
        self.assertEqual(descriptor["environment"]["PSXRECOMP_SKIN_DETAIL_PATH"], str(path))
        self.assertEqual(descriptor["environment"]["PSXRECOMP_SKIN_DETAIL_STRENGTH"], "0.120000")
        self.assertEqual(descriptor["environment"]["PSXRECOMP_SKIN_DETAIL_SCALE"], "8.000000")
        self.assertEqual(descriptor["authored_detail"]["player"]["wrap"], "mirrored_repeat")
        self.receipt()
        self.game_paths()
        prepared = prepare_launch(self.root, result["config_path"])
        self.assertEqual(prepared["authored_detail"]["player"]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_invalid_detail_identity_strength_scale_and_modified_png_rejected(self):
        path, _ = self.detail_asset()
        for request in (dict(detail_map="../../escape"), dict(detail_map=DETAIL_IDS[0], detail_strength=0.36),
                        dict(detail_map=DETAIL_IDS[0], detail_strength=True), dict(detail_map=DETAIL_IDS[0], detail_scale=65),
                        dict(enemy_detail_map=DETAIL_IDS[0], enemy_detail_scale=float("nan"))):
            with self.assertRaises(ValueError):
                self.materials.stage(request)
        path.write_bytes(path.read_bytes() + b"tampered")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            self.materials.stage(dict(detail_map=DETAIL_IDS[0]))

    def test_detail_dimensions_enforce_native_decode_cap(self):
        path, manifest_path = self.detail_asset()
        import struct
        content = bytearray(path.read_bytes())
        content[16:20] = struct.pack(">I", 4097)
        path.write_bytes(content)
        manifest = json.loads(manifest_path.read_text())
        manifest["maps"][0].update(width=4097, sha256=hashlib.sha256(content).hexdigest())
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "dimensions"):
            self.materials.stage(dict(detail_map=DETAIL_IDS[0]))

    def test_manual_check_rejects_detail_receipt_drift(self):
        path, manifest_path = self.detail_asset()
        result = self.materials.stage(dict(detail_map=DETAIL_IDS[0]))
        path.write_bytes(path.read_bytes() + b"new authored revision")
        manifest = json.loads(manifest_path.read_text())
        manifest["maps"][0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, "detail receipt changed"):
            prepare_launch(self.root, result["config_path"])

    def test_runtime_receipt_must_support_detail_and_new_profile(self):
        self.detail_asset()
        result = self.materials.stage(dict(profile="aurora-gilt", detail_map=DETAIL_IDS[0]))
        self.receipt()
        self.game_paths()
        path = self.root / "tools" / "material-runtime.json"
        receipt = json.loads(path.read_text())
        receipt["detail_maps"] = False
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "detail-map support"):
            prepare_launch(self.root, result["config_path"])
        receipt["detail_maps"] = True
        receipt["profiles"].remove("aurora-gilt")
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "profile identities"):
            prepare_launch(self.root, result["config_path"])

    def test_staging_references_entire_pack_without_copy_or_activation(self):
        originals = {path.name: path.read_bytes() for path in self.pngs.iterdir()}
        with patch("subprocess.run") as run:
            result = self.materials.stage(dict(action="stage", profile="aurora-teal", strength=0.55))
            run.assert_not_called()
        descriptor = result["descriptor"]
        self.assertEqual(descriptor["status"], "staged_not_launched")
        self.assertFalse(descriptor["in_game_verified"])
        self.assertEqual(descriptor["source_pack"]["entries"], 12)
        self.assertTrue(descriptor["source_pack"]["all_entries_preserved"])
        self.assertEqual(descriptor["source_pack"]["copied_pngs"], 0)
        self.assertEqual(descriptor["environment"]["PSXRECOMP_SKIN_KEYS"], ",".join(DEFAULT_PLAYER_KEYS))
        self.assertEqual(descriptor["environment"]["PSXRECOMP_SKIN_ENEMY_PROFILE"], "stock")
        self.assertEqual(descriptor["environment"]["PSXRECOMP_SKIN_STRENGTH"], "0.550000")
        self.assertEqual({path.name: path.read_bytes() for path in self.pngs.iterdir()}, originals)
        self.assertFalse(list(Path(result["config_path"]).parent.glob("*.png")))
        self.assertTrue(Path(result["launcher_path"]).is_file())
        self.assertFalse(descriptor["runtime"]["ready"])

    def test_unknown_key_profile_invalid_strength_or_launch_action_rejected(self):
        for request in (dict(profile="../bad"), dict(profile="aurora-teal", targets=["UNRELATED-PAGE"]),
                        dict(profile="aurora-teal", strength=float("nan")), dict(profile="aurora-teal", strength=True),
                        dict(profile="aurora-teal", strength=1.01), dict(profile="aurora-teal", targets=[]),
                        dict(profile="aurora-teal", enemy_profile="unknown"),
                        dict(profile="aurora-teal", enemy_profile="crimson-red", enemy_targets=[FIGHTER_KEY]),
                        dict(profile="aurora-teal", enemy_profile="crimson-red", enemy_strength=float("inf")),
                        dict(profile="aurora-teal", action="launch")):
            with self.assertRaises(ValueError):
                self.materials.stage(request)
        self.assertFalse((self.root / "tools" / "material-profiles").exists())

    def test_distinct_enemy_profile_keeps_channels_independent(self):
        result = self.materials.stage(dict(profile="aurora-teal", strength=0.65, enemy_profile="crimson-red", enemy_strength=0.9))
        descriptor = result["descriptor"]
        self.assertEqual(descriptor["profile"], "aurora-teal")
        self.assertEqual(descriptor["enemy_profile"], "crimson-red")
        self.assertEqual(descriptor["environment"]["PSXRECOMP_SKIN_PROFILE"], "aurora-teal")
        self.assertEqual(descriptor["environment"]["PSXRECOMP_SKIN_ENEMY_PROFILE"], "crimson-red")
        self.assertEqual(descriptor["environment"]["PSXRECOMP_SKIN_ENEMY_STRENGTH"], "0.900000")
        self.assertEqual(len(descriptor["source_textures"]), 10)
        self.assertEqual(set(descriptor["targets"]) & set(descriptor["enemy_targets"]), set())

    def test_default_hull_selection_keeps_shared_mechanics_and_weapon_slots_stock(self):
        catalog = self.materials.catalog()
        self.assertEqual(catalog["default_player_keys"], list(DEFAULT_PLAYER_KEYS))
        self.assertNotIn(FIGHTER_KEY, catalog["default_player_keys"])
        mechanical = next(target for target in catalog["targets"] if target["key"] == FIGHTER_KEY)
        self.assertEqual(mechanical["category"], "shared_mechanical")
        self.assertEqual(mechanical["slot"], "unpartitioned")
        self.assertFalse(mechanical["default_selected"])
        self.assertFalse(mechanical["independent_weapon_slot"])
        self.assertFalse(catalog["component_support"]["built_in_gun"]["selectable"])
        self.assertFalse(catalog["component_support"]["pickup_gunpod"]["selectable"])
        result = self.materials.stage(dict(profile="aurora-teal"))
        self.assertNotIn(FIGHTER_KEY, result["descriptor"]["targets"])
        self.assertNotIn(FIGHTER_KEY, result["descriptor"]["environment"]["PSXRECOMP_SKIN_KEYS"])
        explicit = self.materials.stage(dict(profile="aurora-teal", targets=[FIGHTER_KEY]))
        self.assertEqual(explicit["descriptor"]["targets"], [FIGHTER_KEY])

    def test_enemy_profile_requires_dual_runtime_receipt(self):
        result = self.materials.stage(dict(profile="aurora-teal", enemy_profile="crimson-red"))
        self.receipt()
        self.game_paths()
        receipt_path = self.root / "tools" / "material-runtime.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["dual_profiles"] = False
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "independent enemy"):
            prepare_launch(self.root, result["config_path"])

    def test_source_modification_rejected_before_staging(self):
        (self.pngs / (DEFAULT_PLAYER_KEYS[0] + ".png")).write_bytes(b"changed selected hull without receipt")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            self.materials.stage(dict(profile="aurora-teal"))

    def test_prepared_launch_requires_material_receipt_and_exact_hash(self):
        result = self.materials.stage(dict(profile="aurora-teal"))
        with self.assertRaisesRegex(ValueError, "pending"):
            prepare_launch(self.root, result["config_path"])
        executable = self.receipt()
        self.game_paths()
        prepared = prepare_launch(self.root, result["config_path"])
        self.assertTrue(prepared["runtime"]["executable_hash_verified"])
        self.assertEqual(prepared["arguments"][0], str(executable))
        self.assertIn("--launcher", prepared["arguments"])
        self.assertEqual(prepared["environment_overrides"]["PSXRECOMP_HD_TEXTURE_ROOT"], str(self.pack))
        executable.write_bytes(b"changed runtime")
        with self.assertRaisesRegex(ValueError, "Executable changed"):
            prepare_launch(self.root, result["config_path"])

    def test_prepared_launch_rejects_outside_descriptor_and_modified_pack(self):
        result = self.materials.stage(dict(profile="aurora-teal"))
        with self.assertRaisesRegex(ValueError, "inside"):
            prepare_launch(self.root, self.root / "material.json")
        (self.pack / "manifest.json").write_text((self.pack / "manifest.json").read_text() + "\n")
        with self.assertRaisesRegex(ValueError, "manifest changed"):
            prepare_launch(self.root, result["config_path"])

    def test_check_option_never_starts_a_process(self):
        with patch("launch_material.prepare_launch", return_value=dict(status="validated_not_launched")), patch("launch_material.subprocess.run") as run, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--config", "fixture", "--check"]), 0)
            run.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())["status"], "validated_not_launched")

    def live_engine(self, reply_override=None):
        calls = []
        def command(request, timeout=3.):
            calls.append(dict(request))
            if reply_override is not None:
                return reply_override
            return dict(ok=True, ready=True, contract=CONTRACT, applied=True, apply_scope="color_only_next_draw",
                        player=dict(profile=request["player_profile"], strength_percent=request["player_strength_percent"], key_count=4, detail_active=True),
                        enemy=dict(profile=request["enemy_profile"], strength_percent=request["enemy_strength_percent"], key_count=6, detail_active=True))
        self.materials.command = command
        return calls

    def test_live_apply_changes_only_colors_and_never_saves_or_stages(self):
        calls = self.live_engine()
        original_paths = set(self.root.rglob("*"))
        result = self.materials.dispatch(dict(action="apply", profile="aurora-teal", strength=0.75, enemy_profile="crimson-red", enemy_strength=0.65))
        self.assertTrue(result["ok"])
        self.assertFalse(result["saved"])
        self.assertFalse(result["detail_layers_changed"])
        self.assertEqual(calls, [dict(cmd="skin_material", player_profile="aurora-teal", player_strength_percent=75, enemy_profile="crimson-red", enemy_strength_percent=65)])
        self.assertEqual(set(self.root.rglob("*")), original_paths)
        self.assertFalse(saved_selection(self.root)["exists"])

    def test_live_invalid_pair_detail_fields_or_fractional_percent_never_sent(self):
        calls = self.live_engine()
        for change in (dict(enemy_profile="unknown"), dict(strength=0.755), dict(detail_map=DETAIL_IDS[0])):
            request = dict(action="apply", profile="aurora-teal", strength=0.75, enemy_profile="stock", enemy_strength=0.)
            request.update(change)
            with self.assertRaises(ValueError):
                self.materials.dispatch(request)
        with self.assertRaisesRegex(ValueError, "both player and enemy"):
            self.materials.dispatch(dict(action="apply", profile="aurora-teal"))
        self.assertEqual(calls, [])

    def test_live_offline_and_mismatched_ack_do_not_claim_success(self):
        self.live_engine(dict(ok=False, error="Connection refused"))
        result = self.materials.dispatch(dict(action="apply", profile="aurora-teal", strength=0.75, enemy_profile="stock", enemy_strength=0.))
        self.assertFalse(result["ok"])
        self.assertIn("Connection refused", result["error"])
        self.live_engine(dict(ok=True, ready=True, contract=CONTRACT, player=dict(profile="wrong"), enemy=dict(profile="stock")))
        result = self.materials.dispatch(dict(action="apply", profile="aurora-teal", strength=0.75, enemy_profile="stock", enemy_strength=0.))
        self.assertFalse(result["ok"])
        self.assertIn("acknowledgement", result["error"])
        self.assertFalse((self.root / "tools" / "material-selection.json").exists())

    def test_live_matching_get_response_is_not_misreported_as_applied(self):
        pair = dict(action="apply", profile="aurora-teal", strength=0.75, enemy_profile="stock", enemy_strength=0.)
        for extra in (dict(applied=False, apply_scope="color_only_next_draw"), dict(applied=True, apply_scope="status_only")):
            self.live_engine(dict(ok=True, ready=True, contract=CONTRACT, player=dict(profile="aurora-teal", strength_percent=75),
                                  enemy=dict(profile="stock", strength_percent=0), **extra))
            self.assertFalse(self.materials.dispatch(pair)["ok"])

    def test_explicit_save_writes_verified_pointer_without_engine_command(self):
        calls = self.live_engine()
        result = self.materials.dispatch(dict(action="save", profile="aurora-teal", enemy_profile="crimson-red"))
        self.assertEqual(result["status"], "saved_not_launched")
        self.assertTrue(result["saved"])
        self.assertFalse(result["live_applied"])
        saved = saved_selection(self.root)
        self.assertTrue(saved["valid"])
        self.assertEqual(saved["profile"], "aurora-teal")
        self.assertEqual(saved["enemy_profile"], "crimson-red")
        self.assertNotIn(FIGHTER_KEY, saved["targets"])
        self.assertEqual(calls, [])
        pointer = self.root / "tools" / "material-selection.json"
        previous = pointer.read_bytes()
        with self.assertRaises(ValueError):
            self.materials.dispatch(dict(action="save", profile="unknown"))
        self.assertEqual(pointer.read_bytes(), previous)

    def test_saved_pointer_rejects_path_escape_and_descriptor_tamper(self):
        result = self.materials.dispatch(dict(action="save", profile="aurora-teal"))
        pointer = self.root / "tools" / "material-selection.json"
        data = json.loads(pointer.read_text())
        data["descriptor_relative"] = "../../outside/material.json"
        pointer.write_text(json.dumps(data))
        self.assertFalse(saved_selection(self.root)["valid"])
        self.assertEqual(saved_selection(self.root)["status"], "invalid_saved_pointer")
        result = self.materials.dispatch(dict(action="save", profile="aurora-teal"))
        descriptor = Path(result["config_path"])
        descriptor.write_bytes(descriptor.read_bytes() + b"\n")
        saved = saved_selection(self.root)
        self.assertFalse(saved["valid"])
        self.assertIn("changed", saved["error"])

    def test_saved_check_never_starts_a_process(self):
        with patch("launch_material.saved_selection", return_value=dict(valid=True, config_path="saved-fixture")), patch("launch_material.prepare_launch", return_value=dict(status="validated_not_launched")) as prepare, patch("launch_material.subprocess.run") as run, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--saved", "--check"]), 0)
            run.assert_not_called()
            self.assertEqual(prepare.call_args.args[1], "saved-fixture")
            self.assertEqual(json.loads(output.getvalue())["status"], "validated_not_launched")

    def test_saved_check_invalid_pointer_stops_before_prepare_or_process(self):
        with patch("launch_material.saved_selection", return_value=dict(valid=False, error="Tampered saved pointer")), patch("launch_material.prepare_launch") as prepare, patch("launch_material.subprocess.run") as run, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["--saved", "--check"]), 1)
            prepare.assert_not_called()
            run.assert_not_called()
            self.assertFalse(json.loads(output.getvalue())["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
