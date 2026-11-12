import hashlib
import json
from pathlib import Path
import struct
import tempfile
import time
import unittest
from unittest.mock import Mock

from research_service import (ARCHIVE_BYTES, DEFAULT_LIMITS, DEFAULT_WINDOWS, EVENT_BYTES, EVENT_RAM_BYTES,
                              EVENT_VRAM_BYTES, NATIVE_CONTRACT, NATIVE_NOT_READY, ResearchService, limits, source_filter_config)


class ResearchGame:
    vram = bytes(EVENT_VRAM_BYTES)
    vram_fnv = None

    def __init__(self, native=False):
        self.online = True
        self.frame = 100
        self.ram = bytearray(EVENT_RAM_BYTES)
        self.calls = []
        self.native = native
        self.contract = NATIVE_CONTRACT
        self.active = False
        self.native_path = None
        self.native_limits = {}
        self.events = 0
        self.bad_ack = False
        self.material_generation = 1
        self.tracker_ready = True
        self.start_error = None
        self.source_filter_supported = True
        self.source_filter = dict(policy="all", keys=[])
        self.bad_filter_ack = False

    def response(self):
        result = dict(ok=True, contract=self.contract, active=self.active, ready=self.tracker_ready, path=str(self.native_path or ""),
                      frame=self.frame, limits=dict(self.native_limits), counts=dict(events=self.events, sources=0, records=0, bytes=0, files=0))
        if self.source_filter_supported:
            fingerprint = ResearchService._fnv("".join(key+"\n" for key in sorted(self.source_filter["keys"])).encode("ascii"))
            result.update(source_filter_supported=True, source_filter=dict(policy=self.source_filter["policy"], key_count=len(self.source_filter["keys"]),
                                                                          keys_fnv1a32=fingerprint+int(self.bad_filter_ack), scope="raw_source_archives_only"))
        return result

    def __call__(self, request, timeout=1.):
        self.calls.append(dict(request))
        if not self.online:
            return dict(ok=False, error="Game disconnected")
        operation = request["cmd"]
        if operation == "gpu_state":
            return dict(ok=True, ws=dict(cur_frame=self.frame))
        if operation == "read_ram":
            address = int(request["addr"],16) & 0x1FFFFF
            return dict(ok=True, hex=bytes(self.ram[address:address+request["len"]]).hex())
        if operation == "skin_material":
            self.assert_read_only_material(request)
            return dict(ok=True, ready=True, contract="ein-material-v3", generation=self.material_generation,
                        player=dict(profile="aurora-teal", strength_percent=75), enemy=dict(profile="crimson-red", strength_percent=75))
        if operation == "research_capture":
            if not self.native:
                return dict(ok=False, error="unknown command")
            op = request["op"]
            if op == "status":
                return self.response()
            if op == "start":
                if self.start_error:
                    return dict(ok=False, error=self.start_error)
                if not self.tracker_ready:
                    return dict(ok=False, error=NATIVE_NOT_READY)
                self.native_path = Path(request["path"])
                self.native_limits = {key:value for key,value in request.items() if key.startswith("max_")}
                self.source_filter = dict(policy=request.get("source_policy", "all"), keys=request.get("source_keys", []))
                self.active = True
                result = self.response()
                if self.bad_ack:
                    result["limits"]["max_bytes"] += 1
                return result
            if op == "stop":
                self.active = False
                return self.response()
            if op == "mark":
                if not self.active or self.events >= self.native_limits["max_events"]:
                    return dict(ok=False, error="Native event budget exhausted")
                return self.event(request["label"])
        raise AssertionError("Unexpected or mutating game command: " + str(request))

    @staticmethod
    def assert_read_only_material(request):
        if set(request) != {"cmd"}:
            raise AssertionError("Recorder attempted a material write")

    def event(self, label):
        if ResearchGame.vram_fnv is None:
            ResearchGame.vram_fnv = ResearchService._fnv(ResearchGame.vram)
        header = bytearray(160)
        header[:8] = b"EINRC01\0"
        struct.pack_into("<IIQQIIII", header, 8, 1, 160, self.frame, 123456, 160, EVENT_RAM_BYTES, 160+EVENT_RAM_BYTES, EVENT_VRAM_BYTES)
        struct.pack_into("<IIIIIII", header, 48, 1, 0, 0, 0, 1, ResearchService._fnv(self.ram), ResearchGame.vram_fnv)
        encoded = label.encode("ascii")
        struct.pack_into("<III", header, 76, self.events, len(encoded), 1)
        header[96:96+len(encoded)] = encoded
        path = self.native_path / f"event-{self.events:04d}.bin"
        path.write_bytes(header + self.ram + ResearchGame.vram)
        response = dict(self.response(), event_file=path.name, event_index=self.events, frame=self.frame+1,
                        event_frame=self.frame, event_host_mono_ms=123456, event_bytes=EVENT_BYTES, bytes=EVENT_BYTES)
        self.events += 1
        return response


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "tools").mkdir()
        self.catalog = dict(scenarios=[dict(id="scenario_a", label="Weapons", task_ids=["ammo", "damage"]),
                                      dict(id="scenario_b", label="Another scenario", task_ids=["other"])],
                            tasks=[dict(id="ammo", label="Ammo", scenario_ids=["scenario_a"], status="research_required"),
                                   dict(id="damage", label="Damage", scenario_ids=["scenario_a"], status="research_required"),
                                   dict(id="other", label="Other", scenario_ids=["scenario_b"], status="research_required")])
        (self.root / "tools" / "research_catalog.json").write_text(json.dumps(self.catalog))
        self.game = ResearchGame()
        self.service = ResearchService(self.root, self.game, watch_interval=0.02,
                                       context=lambda:dict(holds=[dict(field="lives", value=9)], bot=dict(running=False)))
        self.addCleanup(self.service.shutdown)

    def start(self, **extra):
        request = dict(scenario="scenario_a", limits=dict(interval_seconds=0.25, duration_seconds=5.))
        request.update(extra)
        return self.service.start(request)

    def wait_finished(self, timeout=4.):
        deadline = time.monotonic()+timeout
        while self.service.active is not None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIsNone(self.service.active)

    def test_offline_start_creates_no_run_and_overview_never_polls_engine(self):
        self.game.online = False
        before = len(self.game.calls)
        self.assertFalse(self.service.overview()["status"]["running"])
        self.assertEqual(len(self.game.calls), before)
        with self.assertRaisesRegex(RuntimeError, "disconnected"):
            self.start()
        self.assertFalse((self.root / "tools" / "research-runs").exists())

    def test_exact_source_filter_validates_bounds_and_never_truncates(self):
        keys = [f"{index:08X}-55667788" for index in range(256)]
        self.assertEqual(source_filter_config(dict(policy="include", keys=keys[::-1]))["keys"], keys)
        for config in (dict(policy="include", keys=[]), dict(policy="all", keys=keys[:1]), dict(policy="bogus", keys=[]),
                       dict(policy="include", keys=keys+["FFFF0000-55667788"]), dict(policy="exclude", keys=keys[:1]*2),
                       dict(policy="include", keys=["11223344-5566778a"]), dict(policy="include", keys=keys[:1], extra=True)):
            with self.assertRaises(ValueError):
                source_filter_config(config)

    def test_explicit_filter_rejects_legacy_runtime_without_creating_a_run(self):
        self.game.native = True
        self.game.source_filter_supported = False
        with self.assertRaisesRegex(ValueError, "does not support exact source filtering"):
            self.start(source_filter=dict(policy="include", keys=["11223344-55667788"]))
        self.assertIsNone(self.service.active)
        self.assertFalse((self.root / "tools" / "research-runs").exists())
        self.assertFalse(any(call.get("op") == "start" for call in self.game.calls))

    def test_filter_is_acknowledged_and_preserved_in_session_and_manifest(self):
        self.game.native = True
        config = dict(policy="include", keys=["FFFFFFFF-55667788", "11223344-55667788"])
        result = self.start(source_filter=config)
        self.assertTrue(result["ok"])
        self.assertTrue(self.service.active["native_supported"])
        run_path = self.service.active["path"]
        start = next(call for call in self.game.calls if call.get("op") == "start")
        self.assertEqual(start["source_keys"], sorted(config["keys"]))
        self.assertEqual(start["source_policy"], "include")
        self.assertTrue(all(set(call) == {"cmd"} for call in self.game.calls if call["cmd"] == "skin_material"))
        self.service.stop()
        for name in ("session.json", "manifest.json"):
            self.assertEqual(json.loads((run_path/name).read_bytes())["source_filter"], source_filter_config(config))

    def test_mismatched_filter_ack_stops_own_native_run_without_fallback(self):
        self.game.native = True
        self.game.bad_filter_ack = True
        result = self.start(source_filter=dict(policy="exclude", keys=["11223344-55667788"]))
        self.assertFalse(result["ok"])
        self.assertIn("acknowledgement failed", result["error"])
        self.assertFalse(self.game.active)
        self.assertIsNone(self.service.active)
        starts = [call for call in self.game.calls if call.get("op") == "start"]
        self.assertEqual(len(starts), 1)
        self.assertEqual(starts[0]["source_policy"], "exclude")

    def test_default_start_preserves_legacy_wire_contract(self):
        self.game.native = True
        self.game.source_filter_supported = False
        self.assertTrue(self.start()["ok"])
        start = next(call for call in self.game.calls if call.get("op") == "start")
        self.assertNotIn("source_keys", start)
        self.assertNotIn("source_policy", start)

    def test_unknown_scenario_and_outside_capture_roots_are_rejected(self):
        for request in (dict(scenario="unknown"), dict(scenario="scenario_a", capture_root="hd-textures"),
                        dict(scenario="scenario_a", capture_root="../outside"), dict(scenario="scenario_a", capture_root=str(self.root))):
            with self.assertRaises(ValueError):
                self.service.start(request)
        self.assertEqual(self.game.calls, [])

    def test_read_only_run_finalizes_immutable_manifest_with_context_hashes(self):
        result = self.start()
        self.assertTrue(result["ok"])
        run_path = self.service.active["path"]
        self.assertFalse(result["native_capture"]["ok"])
        self.assertTrue(self.service.stop()["stopped"])
        manifest_path = run_path / "manifest.json"
        content = manifest_path.read_bytes()
        manifest = json.loads(content)
        self.assertFalse(manifest["verified"])
        self.assertFalse(manifest["native_capture"]["supported"])
        for row in manifest["files"]:
            self.assertEqual(hashlib.sha256((run_path/row["path"]).read_bytes()).hexdigest(), row["sha256"])
        snapshot = json.loads(next(run_path.glob("snapshot-*.json")).read_bytes())
        self.assertEqual(sum(window["length"] for window in snapshot["windows"]), 1792)
        self.assertEqual(snapshot["context"]["materials"]["generation"], 1)
        self.assertEqual(snapshot["context"]["local_assists"]["holds"][0]["field"], "lives")
        self.assertFalse(snapshot["atomic"])
        self.assertEqual(self.service.overview()["history"][0]["manifest_sha256"], hashlib.sha256(content).hexdigest())
        self.service.stop()
        self.assertEqual(manifest_path.read_bytes(), content)
        self.assertTrue(all(call["cmd"] in {"gpu_state","read_ram","skin_material","research_capture"} for call in self.game.calls))

    def test_before_after_pairs_inherit_task_and_produce_candidates_never_verification(self):
        self.start()
        before = self.service.mark(dict(phase="before", label="Pickup", task_id="ammo"))
        self.game.ram[0x84832] = 99
        self.game.frame += 10
        after = self.service.mark(dict(phase="after", label="Pickup complete", pair_id=before["pair_id"]))
        self.assertEqual(after["event"]["task_id"], "ammo")
        self.assertEqual(after["event"]["changes"]["changed_bytes"], 1)
        self.assertFalse(after["event"]["changes"]["verified"])
        self.assertEqual(after["event"]["changes"]["candidates"][0]["address"], "0x80084832")
        self.assertEqual(self.service.status()["open_pairs"], [])
        with self.assertRaises(ValueError):
            self.service.mark(dict(phase="after", pair_id=before["pair_id"]))
        self.service.stop()
        overview = self.service.overview()
        self.assertFalse(overview["coverage"]["scenario_a"]["verified"])
        self.assertEqual(overview["catalog"]["tasks"][0]["status"], "research_required")

    def test_invalid_task_missing_pair_duplicate_before_and_task_mismatch(self):
        self.start()
        for request in (dict(phase="after", pair_id="missing"), dict(task_id="unknown"), dict(task_id="other")):
            with self.assertRaises(ValueError):
                self.service.mark(request)
        before = self.service.mark(dict(phase="before", label="Pickup", task_id="ammo"))
        with self.assertRaisesRegex(ValueError, "already open"):
            self.service.mark(dict(phase="before", label="Pickup", task_id="ammo"))
        with self.assertRaisesRegex(ValueError, "must match"):
            self.service.mark(dict(phase="after", pair_id=before["pair_id"], task_id="damage"))

    def test_disconnect_and_frame_reset_auto_finalize(self):
        self.start()
        self.game.online = False
        self.wait_finished()
        self.assertEqual(self.service._history()[-1]["stop_reason"], "disconnected_or_read_error")
        self.game.online = True
        self.start()
        self.game.frame = 1
        self.wait_finished()
        self.assertEqual(self.service._history()[-1]["stop_reason"], "frame_reset")

    def test_sample_duration_disk_and_event_budgets_are_enforced(self):
        self.start(limits=dict(interval_seconds=0.25, max_samples=2, max_events=1))
        self.service.mark(dict(label="One event"))
        with self.assertRaisesRegex(ValueError, "event budget"):
            self.service.mark(dict(label="Too many"))
        self.wait_finished()
        self.assertEqual(self.service._history()[-1]["stop_reason"], "sample_limit")
        now = [100.]
        self.service.clock = lambda:now[0]
        self.start()
        now[0] += 6
        self.wait_finished()
        self.assertEqual(self.service._history()[-1]["stop_reason"], "duration_limit")
        self.start(limits=dict(interval_seconds=0.25, max_disk_bytes=1024*1024))
        self.service.active["backend_bytes"] = 1024*1024-512*1024-1
        self.wait_finished()
        self.assertEqual(self.service._history()[-1]["stop_reason"], "disk_limit")

    def test_stage_budget_profile_accepted_and_cumulative_budget_checked(self):
        requested = dict(duration_seconds=300, max_disk_bytes=134217728, native_max_sources=256, native_max_records=20000,
                         native_max_events=32, native_max_frames=18000, native_max_bytes=117440512)
        self.assertEqual(limits(requested)["native_max_bytes"], 117440512)
        self.service._atomic_json("tools/research-index.json", [dict(id="existing", scenario="scenario_a", bytes=ARCHIVE_BYTES)])
        with self.assertRaisesRegex(ValueError, "archive budget"):
            self.start()
        self.assertEqual(self.game.calls, [])

    def test_auto_arm_starts_once_and_does_not_retry_start_budget_on_same_connection(self):
        original = self.service.start
        failed = Mock(side_effect=ValueError("archive budget reached"))
        self.service.start = failed
        self.service.arm(dict(enabled=True, scenario="scenario_a"))
        time.sleep(0.15)
        self.assertEqual(failed.call_count, 1)
        self.assertTrue(self.service.status()["armed"])
        self.service.shutdown(persist_disarm=True)
        self.assertFalse(self.service.status()["watcher_alive"])
        self.service.start = original

    def test_auto_arm_waits_for_new_connection_after_sample_limit(self):
        self.service.arm(dict(enabled=True, scenario="scenario_a", limits=dict(interval_seconds=0.25, max_samples=2)))
        deadline = time.monotonic()+4
        while len(self.service._history()) < 1 and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual(len(self.service._history()), 1)
        time.sleep(0.1)
        self.assertEqual(len(self.service._history()), 1)
        self.game.online = False
        time.sleep(0.05)
        self.game.online = True
        deadline = time.monotonic()+4
        while len(self.service._history()) < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual(len(self.service._history()), 2)
        self.service.shutdown(persist_disarm=True)
        self.assertFalse(self.service.status()["running"])
        self.assertFalse(self.service.status()["watcher_alive"])
        self.assertFalse(json.loads((self.root/"tools/research-arm.json").read_text())["enabled"])

    def test_native_contract_and_limit_acknowledgements_are_checked(self):
        self.game.native = True
        self.game.contract = "wrong-contract"
        self.start()
        self.assertFalse(self.service.active["native_supported"])
        self.assertFalse(any(call.get("op") == "start" for call in self.game.calls))
        self.service.stop()
        self.game.contract = NATIVE_CONTRACT
        self.game.bad_ack = True
        self.start()
        self.assertFalse(self.service.active["native_supported"])
        self.assertFalse(self.game.active)
        self.service.stop()

    def test_native_status_expiration_is_refreshed_while_ram_collection_continues(self):
        self.game.native = True
        self.start()
        self.assertEqual(DEFAULT_LIMITS["native_max_frames"], 10800)
        self.game.active = False
        deadline = time.monotonic()+3
        while self.service.active and self.service.status()["native_capture"]["active"] and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(self.service.status()["running"])
        self.assertFalse(self.service.status()["native_capture"]["active"])

    def test_native_pair_captures_whole_ram_candidates_outside_known_windows(self):
        self.game.native = True
        self.start(limits=dict(interval_seconds=10.))
        run_path = self.service.active["path"]
        before = self.service.mark(dict(phase="before", label="Unknown object", task_id="ammo"))
        self.game.ram[0x102030] = 23
        self.game.frame += 5
        after = self.service.mark(dict(phase="after", pair_id=before["pair_id"]))
        self.assertTrue(after["event"]["native_evidence"]["ram_fnv_verified"])
        self.assertTrue(after["event"]["native_evidence"]["cpu_vram_may_be_stale"])
        self.assertEqual(after["event"]["whole_ram_candidates"]["changed_bytes"], 1)
        data = json.loads((run_path/after["event"]["whole_ram_candidates"]["file"]).read_text())
        self.assertEqual(data["candidates_u8"][0]["address"], "0x80102030")
        self.assertFalse(data["verified"])
        evidence = after["event"]["native_evidence"]
        tampered = dict(evidence["acknowledgement"], event_file="../../outside.bin")
        with self.assertRaises(ValueError):
            self.service._event_binary(self.service.active, tampered)
        path = run_path/evidence["file"]
        path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, "length"):
            self.service._event_binary(self.service.active, evidence["acknowledgement"])

    def pending_native(self, **extra_limits):
        now = [100.]
        self.service.clock = lambda:now[0]
        self.game.native = True
        self.game.tracker_ready = False
        chosen = dict(interval_seconds=10., duration_seconds=60.)
        chosen.update(extra_limits)
        self.start(limits=chosen)
        run = self.service.active
        self.assertEqual(run["native_attach"]["state"], "pending_readiness")
        return now, run

    def test_late_native_attach_uses_same_empty_directory_and_remaining_budgets(self):
        now, run = self.pending_native(max_disk_bytes=8*1024*1024, native_max_bytes=6*1024*1024)
        path = run["path"] / "native"
        self.assertFalse(any(call.get("op") == "start" for call in self.game.calls))
        self.game.tracker_ready = True
        self.game.frame += 420
        now[0] += 7
        run["samples"] = 6
        run["backend_bytes"] = 4*1024*1024
        self.service._native_attach(run, retry=True)
        self.assertTrue(run["native_supported"])
        self.assertEqual(run["native_attach"]["state"], "attached")
        starts = [call for call in self.game.calls if call.get("op") == "start"]
        self.assertEqual(len(starts), 1)
        self.assertEqual(Path(starts[0]["path"]), path)
        self.assertEqual(starts[0]["max_seconds"], 53)
        self.assertEqual(starts[0]["max_frames"], DEFAULT_LIMITS["native_max_frames"]-420)
        self.assertEqual(starts[0]["max_bytes"], 8*1024*1024-4*1024*1024-512*1024)
        self.assertEqual(run["native_attach"]["ram_only_prefix_seconds"], 7.)

    def test_pending_attach_requires_five_samples_and_seconds_and_expires_at_thirty(self):
        now, run = self.pending_native()
        initial = len(self.game.calls)
        self.game.tracker_ready = True
        now[0] += 4
        run["samples"] = 6
        self.service._native_attach(run, retry=True)
        self.assertEqual(len(self.game.calls), initial)
        now[0] += 2
        run["samples"] = 5
        self.service._native_attach(run, retry=True)
        self.assertEqual(len(self.game.calls), initial)
        now[0] = 130.
        run["samples"] = 100
        self.service._native_attach(run, retry=True)
        self.assertEqual(run["native_attach"]["state"], "readiness_window_expired")
        self.assertEqual(len(self.game.calls), initial)

    def test_only_exact_readiness_error_retries_and_maximum_three_starts(self):
        now = [100.]
        self.service.clock = lambda:now[0]
        self.game.native = True
        self.game.start_error = NATIVE_NOT_READY
        self.start(limits=dict(interval_seconds=10., duration_seconds=60.))
        run = self.service.active
        for sample, elapsed in ((6,6), (11,12), (16,18)):
            now[0] = 100.+elapsed
            run["samples"] = sample
            self.service._native_attach(run, retry=True)
        self.assertEqual(len([call for call in self.game.calls if call.get("op") == "start"]), 3)
        self.assertEqual(run["native_attach"]["state"], "readiness_attempt_limit")
        self.service.stop()
        self.game.start_error = "Capture metadata could not be committed within limits"
        self.start(limits=dict(interval_seconds=10., duration_seconds=60.))
        run = self.service.active
        initial = len(self.game.calls)
        now[0] += 6
        run["samples"] = 6
        self.service._native_attach(run, retry=True)
        self.assertEqual(run["native_attach"]["state"], "start_rejected")
        self.assertEqual(len(self.game.calls), initial)

    def test_unknown_command_and_owned_capture_are_not_readiness_retried(self):
        self.start(limits=dict(interval_seconds=10.))
        run = self.service.active
        initial = len(self.game.calls)
        self.game.native = True
        run["samples"] = 100
        self.service._native_attach(run, retry=True)
        self.assertEqual(len(self.game.calls), initial)
        self.assertEqual(run["native_attach"]["state"], "unsupported_or_invalid_contract")
        self.service.stop()
        self.game.active = True
        self.start(limits=dict(interval_seconds=10.))
        run = self.service.active
        initial = len(self.game.calls)
        run["samples"] = 100
        self.service._native_attach(run, retry=True)
        self.assertEqual(run["native_attach"]["state"], "owned_elsewhere")
        self.assertEqual(len(self.game.calls), initial)

    def test_pending_stop_and_exhausted_frame_budget_cannot_attach(self):
        now, run = self.pending_native(native_max_frames=100)
        self.game.tracker_ready = True
        self.game.frame += 101
        now[0] += 6
        run["samples"] = 6
        self.service._native_attach(run, retry=True)
        self.assertEqual(run["native_attach"]["state"], "remaining_budget_exhausted")
        self.assertFalse(any(call.get("op") == "start" for call in self.game.calls))
        self.service.stop()
        self.game.tracker_ready = False
        now, run = self.pending_native()
        self.service.stop()
        initial = len(self.game.calls)
        self.game.tracker_ready = True
        now[0] += 6
        run["samples"] = 6
        self.service._native_attach(run, retry=True)
        self.assertEqual(len(self.game.calls), initial)
        self.assertEqual(run["native_attach"]["state"], "cancelled_before_attachment")

    def test_pending_attach_never_overwrites_an_existing_native_directory(self):
        now, run = self.pending_native()
        sentinel = run["path"] / "native" / "existing.json"
        sentinel.write_text("preserve me")
        self.game.tracker_ready = True
        now[0] += 6
        run["samples"] = 6
        self.service._native_attach(run, retry=True)
        self.assertEqual(run["native_attach"]["state"], "native_directory_not_empty")
        self.assertEqual(sentinel.read_text(), "preserve me")
        self.assertFalse(any(call.get("op") == "start" for call in self.game.calls))

    def test_sampling_worker_performs_bounded_late_attachment(self):
        now = [100.]
        self.service.clock = lambda:now[0]
        self.game.native = True
        self.game.tracker_ready = False
        self.start(limits=dict(interval_seconds=0.25, duration_seconds=60.))
        run = self.service.active
        self.game.tracker_ready = True
        self.game.frame += 360
        now[0] += 6
        deadline = time.monotonic()+4
        while not run["native_supported"] and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertTrue(run["native_supported"])
        self.assertGreaterEqual(run["samples"], 6)
        self.assertEqual(run["native_attach"]["state"], "attached")
        self.assertEqual(len([call for call in self.game.calls if call.get("op") == "start"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
