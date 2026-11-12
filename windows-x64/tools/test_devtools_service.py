"""Behavioral tests; use a byte-accurate fake native debug server."""
import base64
import io
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import http.client
import http.server
import threading

from devtools_service import DevTools, FIELD_MAP, scoped_path
import ein_bridge
from research_service import ResearchService


class FakeGame:
    def __init__(self):
        self.ram = {}
        self.calls = []
        self.frame = 100
        self.online = True
        self.fail_address = None
        self.ram[int(FIELD_MAP["lives"]["address"], 16)] = 3

    def __call__(self, request, timeout=1.5):
        self.calls.append(dict(request))
        if not self.online:
            return dict(ok=False, error="Disconnected")
        operation = request["cmd"]
        if operation == "gpu_state":
            return dict(ok=True, ws=dict(cur_frame=self.frame))
        if operation in ("skin_material", "research_capture"):
            return dict(ok=False, error="unknown command")
        if operation in ("clear_input", "savestate", "reset", "input_route_start", "pad_status", "press"):
            return dict(ok=True)
        address = int(request["addr"], 16)
        if operation == "read_ram":
            return dict(ok=True, hex=bytes(self.ram.get(address + offset, 0) for offset in range(request["len"])).hex())
        if operation == "write_ram":
            if address == self.fail_address:
                return dict(ok=False, error="Injected byte failure")
            value = int(request["val"], 16)
            assert 0 <= value <= 255
            self.ram[address] = value
            return dict(ok=True)
        raise AssertionError(request)


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = FakeGame()
        self.now = 100.
        self.service = DevTools(self.temp.name, self.game, clock=lambda: self.now)

    def test_u16_is_little_endian_and_read_back(self):
        result = self.service.write(dict(field="ammo", value="0x1234"))
        self.assertTrue(result["ok"])
        writes = [call for call in self.game.calls if call["cmd"] == "write_ram"]
        self.assertEqual(writes, [dict(cmd="write_ram", addr="0x80084832", val="0x34"), dict(cmd="write_ram", addr="0x80084833", val="0x12")])
        self.assertEqual(result["operation"]["readback"], 0x1234)
        self.assertEqual(self.service.status()["values"]["ammo"]["value"], 0x1234)

    def test_research_and_out_of_range_writes_do_not_mutate(self):
        for request in (dict(field="stage_select", value=1), dict(field="lives", value=256), dict(field="ammo", value=-1), dict(field="lives", value=True)):
            with self.assertRaises(ValueError):
                self.service.write(request)
        self.assertEqual(self.game.calls, [])

    def test_undo_restores_only_if_value_unchanged(self):
        result = self.service.write(dict(field="ammo", value=1234))
        self.game.ram[0x80084832] = 77
        with self.assertRaisesRegex(ValueError, "newer game state"):
            self.service.undo(dict(id=result["operation"]["id"]))
        self.game.ram[0x80084832] = 0xD2
        self.assertTrue(self.service.undo(dict(id=result["operation"]["id"]))["ok"])
        self.assertEqual(self.service._read(FIELD_MAP["ammo"]), 0)

    def test_partial_u16_failure_is_recorded_without_false_success(self):
        self.game.fail_address = 0x80084833
        result = self.service.write(dict(field="ammo", value=65535))
        self.assertFalse(result["ok"])
        self.assertIn("1/2 bytes", result["error"])
        self.assertFalse(result["operation"]["verified"])

    def test_hold_expires_and_never_restores_old_combat_state(self):
        self.assertTrue(self.service.lock(dict(field="lives", value=9, ttl_seconds=5))["ok"])
        self.now += 6
        self.service.tick()
        self.assertEqual(self.service.locks, {})
        self.assertEqual(self.game.ram[0x800813C4], 9)
        self.assertIn("expired", self.service.last_stop_reason)

    def test_hold_stops_on_disconnect_or_frame_reset(self):
        self.service.lock(dict(field="lives", value=9))
        self.game.frame = 1
        self.service.tick()
        self.assertFalse(self.service.locks)
        self.assertIn("reset", self.service.last_stop_reason)
        self.game.frame = 101
        self.service.lock(dict(field="lives", value=9))
        self.game.online = False
        self.service.tick()
        self.assertFalse(self.service.locks)
        self.assertIn("disconnected", self.service.last_stop_reason)

    def test_unverified_hold_and_invalid_player_state_rejected(self):
        with self.assertRaises(ValueError):
            self.service.lock(dict(field="ammo", value=999))
        self.game.ram[0x800813C4] = 0
        with self.assertRaises(ValueError):
            self.service.lock(dict(field="lives", value=9))

    def test_release_has_no_hidden_write(self):
        self.service.lock(dict(field="invincibility", value=165))
        self.game.calls.clear()
        self.assertTrue(self.service.lock(dict(field="invincibility", enabled=False))["ok"])
        self.assertEqual(self.game.calls, [])

    def test_skin_workspace_stays_draft_and_names_are_scoped(self):
        for name in ("../escape", "a/b", "", "a.b"):
            with self.assertRaises(ValueError):
                self.service.skin_action(dict(name=name))
        result = self.service.skin_action(dict(name="Arctic-01", style="arctic"))
        self.assertEqual(result["manifest"]["status"], "draft_uninstalled")
        self.assertEqual(self.service.skins()["packs"][0]["name"], "Arctic-01")
        self.assertFalse((Path(self.temp.name) / "hd-textures").exists())

    def test_skin_png_import_rejects_changed_alpha_and_dimensions(self):
        from PIL import Image
        self.service.skin_action(dict(name="Test"))
        source = Path(self.temp.name) / "hd-textures" / "stage1-v1" / "einhander-texture-replacements"
        source.mkdir(parents=True)
        Image.new("RGBA", (4, 4), (0, 0, 0, 255)).save(source / "ABC-DEF.png")
        (source.parent / "manifest.json").write_text(json.dumps(dict(files=[dict(key="ABC-DEF", sha256=hashlib.sha256((source / "ABC-DEF.png").read_bytes()).hexdigest())])))
        def encoded(size, alpha):
            output = io.BytesIO()
            Image.new("RGBA", size, (60, 70, 80, alpha)).save(output, format="PNG")
            return base64.b64encode(output.getvalue()).decode()
        for size, alpha in (((2, 2), 255), ((4, 4), 128), ((4, 4), 0)):
            with self.assertRaises(ValueError):
                self.service.skin_action(dict(action="import", name="Test", key="ABC-DEF", png_base64=encoded(size, alpha)))
        result = self.service.skin_action(dict(action="import", name="Test", key="ABC-DEF", png_base64=encoded((4, 4), 255)))
        self.assertTrue(result["ok"])
        self.assertFalse(result["manifest"]["assets"][0]["in_game"])
        with self.assertRaises(ValueError):
            self.service.skin_action(dict(action="import", name="Test", key="ABC-DEF", png_base64=encoded((4, 4), 255)))

    def test_skin_import_preserves_exact_alpha_including_stp_threshold(self):
        from PIL import Image
        self.service.skin_action(dict(name="Effects"))
        source = Path(self.temp.name) / "hd-textures" / "stage1-v1" / "einhander-texture-replacements"
        source.mkdir(parents=True)
        Image.new("RGBA", (2, 2), (20, 30, 40, 64)).save(source / "ABC-DEF.png")
        expected_sha = hashlib.sha256((source / "ABC-DEF.png").read_bytes()).hexdigest()
        (source.parent / "manifest.json").write_text(json.dumps(dict(files=[dict(key="ABC-DEF", sha256=expected_sha)])))
        output = io.BytesIO()
        Image.new("RGBA", (2, 2), (50, 60, 70, 128)).save(output, format="PNG")
        with self.assertRaisesRegex(ValueError, "alpha bytes"):
            self.service.skin_action(dict(action="import", name="Effects", key="ABC-DEF", png_base64=base64.b64encode(output.getvalue()).decode()))
        self.assertFalse((self.service.skin_root / "Effects" / "einhander-texture-replacements" / "ABC-DEF.png").exists())
        assets = self.service.skins()["source_assets"]
        self.assertEqual((assets[0]["width"], assets[0]["height"]), (2, 2))
        self.assertEqual(assets[0]["sha256"], expected_sha)
        self.assertEqual(assets[0]["semantic_mapping"], "unverified")

    def test_skin_import_rejects_modified_source_hash(self):
        from PIL import Image
        self.service.skin_action(dict(name="HashCheck"))
        source = Path(self.temp.name) / "hd-textures" / "stage1-v1" / "einhander-texture-replacements"
        source.mkdir(parents=True)
        image = Image.new("RGBA", (2, 2), (20, 30, 40, 255))
        image.save(source / "ABC-DEF.png")
        (source.parent / "manifest.json").write_text(json.dumps(dict(files=[dict(key="ABC-DEF", sha256="wrong")])) )
        output = io.BytesIO()
        image.save(output, format="PNG")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            self.service.skin_action(dict(action="import", name="HashCheck", key="ABC-DEF", png_base64=base64.b64encode(output.getvalue()).decode()))

    def test_collection_style_is_saved_as_inactive_metadata_only(self):
        from PIL import Image
        collection = Path(self.temp.name) / "tools" / "skin_collection"
        collection.mkdir(parents=True)
        Image.new("RGB", (8, 4), (30, 200, 190)).save(collection / "aurora-teal.png")
        sha = hashlib.sha256((collection / "aurora-teal.png").read_bytes()).hexdigest()
        (collection / "collection.json").write_text(json.dumps(dict(skins=[dict(id="aurora-teal", name="Aurora Vector", role="player", width=8, height=4, sha256=sha,
            image="/files/tools/skin_collection/aurora-teal.png", palette=["#22CCBB", "not a color"])])))
        style = next(style for style in self.service.skins()["styles"] if style["id"] == "aurora-teal")
        self.assertEqual(style["kind"], "generated_concept")
        result = self.service.skin_action(dict(action="create", name="AuroraPack", style="aurora-teal"))
        manifest = result["manifest"]
        self.assertEqual(manifest["concept_art"]["sha256"], sha)
        self.assertEqual(manifest["concept_art"]["palette"], ["#22CCBB"])
        self.assertFalse(manifest["concept_art"]["in_game"])
        self.assertEqual(manifest["assets"], [])
        self.assertEqual(manifest["status"], "draft_uninstalled")
        result = self.service.skin_action(dict(action="set-style", name="AuroraPack", style="stock"))
        self.assertEqual(result["manifest"]["style"], "stock")
        self.assertNotIn("concept_art", result["manifest"])
        self.assertEqual(result["manifest"]["assets"], [])
        self.assertFalse((Path(self.temp.name) / "hd-textures").exists())

    def test_collection_style_rejects_unsafe_url_and_mismatched_hash(self):
        collection = Path(self.temp.name) / "tools" / "skin_collection"
        collection.mkdir(parents=True)
        (collection / "collection.json").write_text(json.dumps(dict(skins=[
            dict(id="unsafe", name="Unsafe", image="javascript:alert(1)"),
            dict(id="missing", name="Missing", image="/files/tools/skin_collection/missing.png", sha256="wrong", width=1, height=1)])))
        ids = [style["id"] for style in self.service.skins()["styles"]]
        self.assertNotIn("unsafe", ids)
        with self.assertRaisesRegex(ValueError, "SHA256"):
            self.service.skin_action(dict(action="create", name="BadPack", style="missing"))
        self.assertFalse((self.service.skin_root / "BadPack").exists())

    def test_path_guard_rejects_sibling_prefix_and_parent(self):
        root = Path(self.temp.name) / "proof"
        for relative in ("../proof-other/file.png", "../../outside"):
            with self.assertRaises(ValueError):
                scoped_path(root, relative)


class CompatibilityTests(unittest.TestCase):
    def test_existing_size_clients_use_native_len_and_get_data_alias(self):
        sent = []
        def send(line, timeout):
            sent.append(json.loads(line))
            return '{"ok":true,"hex":"3412"}'
        with patch.object(ein_bridge, "send_cmd", send):
            result = ein_bridge.cmd(dict(cmd="read_ram", addr="0x80084832", size=2))
        self.assertEqual(sent[0]["len"], 2)
        self.assertNotIn("size", sent[0])
        self.assertEqual(result["data"], "3412")

    def test_raw_native_write_cannot_silently_truncate(self):
        with patch.object(ein_bridge, "send_cmd") as send:
            result = ein_bridge.cmd(dict(cmd="write_ram", addr="0x80084832", val="0xFFFF"))
            self.assertFalse(result["ok"])
            send.assert_not_called()

    def test_bot_config_rejects_invalid_timing_and_types(self):
        for request in (dict(tick=0), dict(tick=-1), dict(weave="false")):
            with self.assertRaises(ValueError):
                ein_bridge.Robin().apply(request)
        bot = ein_bridge.Robin()
        with self.assertRaises(ValueError):
            bot.apply(dict(autofire=False, weave="invalid"))
        self.assertTrue(bot.autofire)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.game = FakeGame()
        self.service = DevTools(self.temp.name, self.game)
        self.replace = patch.object(ein_bridge, "DEVTOOLS", self.service)
        self.replace.start()
        self.addCleanup(self.replace.stop)
        self.research = ResearchService(self.temp.name, self.game, watch_interval=0.02)
        self.addCleanup(self.research.shutdown)
        research_patch = patch.object(ein_bridge, "RESEARCH", self.research)
        research_patch.start()
        self.addCleanup(research_patch.stop)
        command_patch = patch.object(ein_bridge, "cmd", self.game)
        command_patch.start()
        self.addCleanup(command_patch.stop)
        self.bot = ein_bridge.Robin()
        bot_patch = patch.object(ein_bridge, "BOT", self.bot)
        bot_patch.start()
        self.addCleanup(bot_patch.stop)
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), ein_bridge.Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        data = json.loads(response.read())
        status = response.status
        connection.close()
        return status, data

    def test_catalog_and_explicit_write_routes(self):
        status, result = self.request("GET", "/dev/catalog")
        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])
        status, result = self.request("POST", "/dev/write", json.dumps(dict(field="ammo", value=1234)))
        self.assertEqual(status, 200)
        self.assertEqual(result["operation"]["readback"], 1234)

    def test_material_list_does_not_poll_game_and_live_apply_requires_explicit_pair(self):
        status, result = self.request("GET", "/dev/materials")
        self.assertEqual(status, 200)
        self.assertFalse(result["live_supported"]["engine_polled"])
        self.assertFalse(result["saved_selection"]["exists"])
        self.assertEqual(self.game.calls, [])
        status, result = self.request("POST", "/dev/materials", json.dumps(dict(action="apply", profile="aurora-teal")))
        self.assertEqual(status, 400)
        self.assertFalse(result["ok"])
        self.assertEqual(self.game.calls, [])

    def test_research_routes_stop_on_state_transition_and_emergency_disarms(self):
        status, overview = self.request("GET", "/dev/research")
        self.assertEqual(status, 200)
        self.assertFalse(overview["status"]["armed"])
        self.assertEqual(self.game.calls, [])
        status, result = self.request("POST", "/dev/research", json.dumps(dict(action="start", scenario="free_observation")))
        self.assertEqual(status, 200)
        self.assertTrue(result["status"]["running"])
        status, result = self.request("POST", "/cmd", json.dumps(dict(line=json.dumps(dict(cmd="savestate", op="save", slot=0)))))
        self.assertEqual(status, 200)
        self.assertFalse(self.research.status()["running"])
        self.assertEqual(self.research._history()[-1]["stop_reason"], "raw_state_transition")
        status, result = self.request("POST", "/dev/research", json.dumps(dict(action="arm", enabled=True, scenario="free_observation")))
        self.assertEqual(status, 200)
        self.service.lock(dict(field="invincibility", value=165, ttl_seconds=60))
        self.bot.running = True  # No bot thread is started in this test.
        status, result = self.request("POST", "/dev/emergency", "{}")
        self.assertEqual(status, 200)
        self.assertEqual(self.service.locks, {})
        self.assertFalse(self.bot.running)
        self.assertFalse(self.research.status()["armed"])
        self.assertFalse(self.research.status()["running"])
        self.assertFalse(self.research.status()["watcher_alive"])

    def test_clear_input_keeps_invulnerability_hold_and_armed_research(self):
        self.service.lock(dict(field="invincibility", value=165, ttl_seconds=60))
        status, result = self.request("POST", "/dev/research", json.dumps(dict(action="arm", enabled=True, scenario="free_observation")))
        self.assertEqual(status, 200)
        import time
        deadline = time.monotonic()+2
        while self.research.active is None and time.monotonic() < deadline:
            time.sleep(0.01)
        run_id = self.research.status()["id"]
        status, result = self.request("POST", "/cmd", json.dumps(dict(line=json.dumps(dict(cmd="clear_input")))))
        self.assertEqual(status, 200)
        self.assertTrue(result["ok"])
        self.assertIn("invincibility", self.service.locks)
        self.assertTrue(self.research.status()["armed"])
        self.assertTrue(self.research.status()["running"])
        self.assertEqual(self.research.status()["id"], run_id)
        self.game.ram[0x80085718] = 1
        self.service.tick()
        self.assertEqual(self.game.ram[0x80085718], 165)

    def test_explicit_state_and_input_route_transitions_still_release_holds(self):
        for command in (dict(cmd="savestate", op="save", slot=0), dict(cmd="reset"), dict(cmd="input_route_start")):
            with self.subTest(command=command["cmd"]):
                self.service.lock(dict(field="invincibility", value=165, ttl_seconds=60))
                status, result = self.request("POST", "/cmd", json.dumps(dict(line=json.dumps(command))))
                self.assertEqual(status, 200)
                self.assertTrue(result["ok"])
                self.assertEqual(self.service.locks, {})

    def test_demo_release_is_input_only_while_watch_and_exit_release_holds(self):
        self.service.lock(dict(field="invincibility", value=165, ttl_seconds=60))
        status, result = self.request("POST", "/demo", json.dumps(dict(action="release")))
        self.assertEqual(status, 200)
        self.assertIn("invincibility", self.service.locks)
        for action in ("watch", "exit"):
            with self.subTest(action=action):
                if "invincibility" not in self.service.locks:
                    self.service.lock(dict(field="invincibility", value=165, ttl_seconds=60))
                status, result = self.request("POST", "/demo", json.dumps(dict(action=action)))
                self.assertEqual(status, 200)
                self.assertEqual(self.service.locks, {})

    def test_invalid_json_and_remote_origin_return_json_errors(self):
        status, result = self.request("POST", "/dev/write", "{")
        self.assertEqual(status, 400)
        self.assertFalse(result["ok"])
        status, result = self.request("POST", "/cmd", '{"line":123}')
        self.assertEqual(status, 400)
        self.assertFalse(result["ok"])

    def test_dns_rebinding_host_is_rejected_even_when_origin_matches(self):
        remote_host = "example.org:" + str(self.server.server_port)
        status, result = self.request("POST", "/dev/write", "{}", {"Host": remote_host, "Origin": "http://" + remote_host})
        self.assertEqual(status, 403)
        self.assertFalse(result["ok"])
        status, result = self.request("GET", "/dev/catalog", headers={"Host": remote_host})
        self.assertEqual(status, 403)
        status, result = self.request("POST", "/dev/write", "{}", {"Origin": "https://example.org"})
        self.assertEqual(status, 403)
        self.assertFalse(result["ok"])

    def test_evidence_traversal_rejected_and_missing_report_is_honest(self):
        status, result = self.request("GET", "/dev/evidence/files/../../outside.png")
        self.assertEqual(status, 400)
        self.assertFalse(result["ok"])
        status, result = self.request("GET", "/dev/evidence")
        self.assertEqual(status, 200)
        self.assertFalse(result["available"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
