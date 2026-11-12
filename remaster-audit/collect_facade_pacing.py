"""Passive, report-bound facade pacing collector. No input or process control.

--self-test performs offline fixtures only. A live invocation requires an
existing candidate.json and its launch receipt. This script never launches,
quits, resets, captures pixels, starts a recorder, or changes runtime settings.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import socket
import statistics
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

KEY = "52F33418-5E9B9AC3"
UINT64 = 1 << 64
GETTERS = {"get_registers": {}, "gl_present_ring": {"n": 180},
           "latency": {"window": 240, "raw": 1, "count": 96},
           "gl_interp": {}, "turbo_state": {}, "frame_perf": {}}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value < UINT64


def stamp(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value < 1e15


def stats(values):
    values = sorted(values)
    if not values:
        return {"n": 0}
    quantile = lambda p: values[math.ceil((len(values) - 1) * p)]
    return {"n": len(values), "mean_ms": statistics.fmean(values), "p50_ms": quantile(.5),
            "p95_ms": quantile(.95), "p99_ms": quantile(.99), "max_ms": values[-1],
            "over_25_ms": sum(x > 25 for x in values),
            "over_33_4_ms": sum(x > 33.4 for x in values),
            "over_50_ms": sum(x > 50 for x in values)}


def latency_rows(response):
    rows = {}
    for row in response.get("frames", []):
        if not isinstance(row, dict) or not integer(row.get("f")) or not stamp(row.get("input")):
            continue
        complete = stamp(row.get("swap_begin")) and stamp(row.get("swap_end")) and row["swap_end"] >= row["swap_begin"] >= row["input"]
        old = rows.get(row["f"])
        if old is None or (complete and not old["complete"]):
            rows[row["f"]] = dict(row, complete=complete)
    return rows


class Tracker:
    """Deduplicate metrics by epoch/sequence; never subtract across responses."""
    def __init__(self, facade_window=None):
        self.epochs = []
        self.previous_rows = {}
        self.facade_window = facade_window

    def add(self, sample):
        heads = {"guest_frame": sample["get_registers"]["frame"],
                 "latency_cycle": sample["latency"]["summary"]["frames"],
                 "gl_present_seq": sample["gl_present_ring"]["total"]}
        require(all(integer(x) for x in heads.values()), "Invalid counter head")
        rows = latency_rows(sample["latency"])
        current = self.epochs[-1] if self.epochs else None
        reason = None
        if current and any(heads[k] < current["last_heads"][k] for k in heads):
            reason = "Counter regressed or wrapped; no cross-epoch differences"
        overlaps = [rows[f]["input"] - self.previous_rows[f]["input"]
                    for f in rows.keys() & self.previous_rows.keys()
                    if rows[f]["complete"] and self.previous_rows[f]["complete"]]
        if current and not reason and len(overlaps) >= 2 and max(overlaps) - min(overlaps) > 2:
            reason = "Overlap timestamps lack a consistent response-local anchor"
        if current is None or reason:
            current = {"epoch": len(self.epochs), "reason": reason or "Initial observation",
                       "first_heads": heads, "last_heads": heads, "guest_observations": [],
                       "native_period": {}, "swap_block": {}, "present_period": {},
                       "presents": {}, "latency_cycles_seen": set(), "incomplete_cycles": set(),
                       "latency_summaries": [], "interpolation": [], "anchor_checks": []}
            self.epochs.append(current)
            overlaps = []
        current["last_heads"] = heads
        current["guest_observations"].append((sample["guest_midpoint"], heads["guest_frame"]))
        current["latency_summaries"].append(sample["latency"]["summary"])
        current["interpolation"].append(sample.get("gl_interp", {}))
        current["anchor_checks"].append({"overlap_complete_rows": len(overlaps),
               "constant_offset_within_2us": max(overlaps) - min(overlaps) <= 2 if overlaps else None,
               "cross_response_timestamp_subtraction_used": False})
        floor = current["first_heads"]["latency_cycle"]
        for f, row in rows.items():
            # head-1 remains open: interpolation can overwrite an already
            # complete swap stamp. Finalize only after the next cycle begins.
            if not floor <= f < heads["latency_cycle"] - 1:
                continue
            current["latency_cycles_seen"].add(f)
            if not row["complete"]:
                current["incomplete_cycles"].add(f)
                continue
            current["incomplete_cycles"].discard(f)
            current["swap_block"].setdefault(f, (row["swap_end"] - row["swap_begin"]) / 1000)
            previous = rows.get(f - 1)
            if previous and previous["complete"] and row["input"] >= previous["input"]:
                current["native_period"].setdefault(f, (row["input"] - previous["input"]) / 1000)
        # Raw latency times have a new zero on EVERY response. Only this response's
        # neighboring complete rows are compared. Retain overlaps solely to detect
        # inconsistent anchors; never reconstruct an absolute cross-response clock.
        self.previous_rows = rows
        events = {}
        for row in sample["gl_present_ring"].get("events", []):
            if isinstance(row, list) and len(row) >= 8 and integer(row[0]) and integer(row[1]) and integer(row[3]) and row[3] < 1 << 32:
                events.setdefault(row[0], row)
        floor = current["first_heads"]["gl_present_seq"]
        for seq, row in events.items():
            if not floor <= seq < heads["gl_present_seq"]:
                continue
            current["presents"].setdefault(seq, row)
            previous = events.get(seq - 1)
            if previous:
                delta = (row[3] - previous[3]) & 0xFFFFFFFF
                if delta <= 60000:  # SDL's uint32 ms counter may wrap normally.
                    current["present_period"].setdefault(seq, (delta, row[1]))

    def report(self):
        result = []
        for epoch in self.epochs:
            first, last = epoch["first_heads"], epoch["last_heads"]
            points = epoch["guest_observations"]
            dt = points[-1][0] - points[0][0]
            progress = last["guest_frame"] - first["guest_frame"]
            native_count = last["latency_cycle"] - first["latency_cycle"]
            finalized_native_count = max(0, native_count - 1)
            present_count = last["gl_present_seq"] - first["gl_present_seq"]
            scoped = [value for value, guest in epoch["present_period"].values()
                      if self.facade_window and self.facade_window[0] <= guest <= self.facade_window[1]]
            result.append({"epoch": epoch["epoch"], "reason": epoch["reason"],
                "first_heads": first, "last_heads": last,
                "guest_observation_seconds": dt,
                "guest_vblank_progress": progress,
                "guest_vblanks_per_second": progress / dt if dt > 0 else None,
                "latency_cycle_progress": native_count, "gl_present_progress": present_count,
                "latency_finalized_cycle_progress": finalized_native_count,
                "latency_final_active_cycle_excluded": 1 if native_count else 0,
                "latency_missing_cycle_records": finalized_native_count - len(epoch["latency_cycles_seen"]),
                "latency_incomplete_cycle_records": len(epoch["incomplete_cycles"]),
                "latency_period_missing_records": finalized_native_count - len(epoch["native_period"]),
                "gl_missing_present_records": present_count - len(epoch["presents"]),
                "gl_period_missing_records": present_count - len(epoch["present_period"]),
                "native_cycle_input_mark_period": stats(epoch["native_period"].values()),
                "last_swap_block_per_native_cycle": stats(epoch["swap_block"].values()),
                "gl_pre_swap_period": stats(x[0] for x in epoch["present_period"].values()),
                "known_facade_guest_window_pre_swap_period": stats(scoped),
                "present_path_counts": dict(__import__("collections").Counter(x[2] for x in epoch["presents"].values())),
                "interpolation_observations": epoch["interpolation"],
                "latency_summary_snapshots": epoch["latency_summaries"],
                "anchor_checks": epoch["anchor_checks"]})
        return {"epochs": result, "counter_epoch_changes": max(0, len(result) - 1),
                "cross_epoch_rate_or_interval": None,
                "known_facade_guest_frame_window": self.facade_window,
                "per_key_decode_duration_ms": None, "per_key_gl_upload_duration_ms": None,
                "per_key_mip_generation_duration_ms": None,
                "target_resident_reuse_proven": False,
                "limits": ["Guest frame is simulated vblank count; latency f is a separate present-cycle sequence; GL row frame is the guest label and row seq counts every present including interpolation.",
                    "Latency raw timestamps are response-relative QPC microseconds. Incomplete/capped/gapped windows are reported and never bridged. The final active cycle is excluded because later interpolated swaps can overwrite it.",
                    "Latency swap stamps retain only the last swap of a native cycle. gl_present_ring retains interpolated swaps separately.",
                    "GL timestamps are millisecond pre-swap CPU timestamps, not display scanout/photon measurements; glerr=0 does not prove no errors when pixel probing is off.",
                    "Facade phase/window is operator-supplied correlation, not per-key upload/decode timing or proof of cache residency.",
                    "Getters add observation overhead. Recorders, screenshots, source capture, GPU jobs and first-use versus later-use passes must be controlled separately."]}


def binding(candidate):
    candidate = candidate.resolve()
    raw = candidate.read_bytes()
    report = json.loads(raw)
    directory = candidate.parent
    spec = report["launches"]["candidate"]
    launch_path = directory / "launch-candidate.json"
    launch = json.loads(launch_path.read_bytes())
    executable = Path(spec["arguments"][0]).resolve()
    port = report["debug_port"]
    require(Path(report["evidence"]).resolve() == directory, "Report/evidence directory mismatch")
    require(executable.is_relative_to(directory), "Executable must belong to this isolated candidate")
    require(integer(launch.get("pid")) and launch["pid"] > 0, "Missing launch PID")
    require(isinstance(port, int) and 1 <= port <= 65535, "Invalid report debug port")
    require(launch.get("debug_port") == port and Path(launch["executable"]).resolve() == executable,
            "Launch receipt differs from report")
    require(spec["arguments"][spec["arguments"].index("--debug-port") + 1] == str(port),
            "Command-line port differs from report")
    require(digest(executable) == spec["executable_sha256"], "Executable SHA256 differs from report")
    return {"candidate": str(candidate), "candidate_sha256": hashlib.sha256(raw).hexdigest(),
            "launch_receipt": str(launch_path), "launch_sha256": digest(launch_path),
            "executable": str(executable), "executable_sha256": spec["executable_sha256"],
            "pid": launch["pid"], "port": port, "evidence": str(directory),
            "declared_environment_overrides": spec.get("environment_overrides", {})}


def inspect_process(bound):
    # Only numeric PID/port enter the shell; no paths or arbitrary shell text.
    script = ("$p = Get-CimInstance Win32_Process -Filter 'ProcessId = " + str(bound["pid"]) + "'; "
              "$s = @(Get-NetTCPConnection -LocalPort " + str(bound["port"]) + " -State Listen -ErrorAction Stop); "
              "[PSCustomObject]@{pid=$p.ProcessId; executable=$p.ExecutablePath; created=$p.CreationDate.ToUniversalTime().ToString('o'); listeners=@($s | Select-Object -ExpandProperty OwningProcess -Unique)} | ConvertTo-Json -Compress")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                            capture_output=True, text=True, check=True, timeout=15)
    actual = json.loads(result.stdout)
    require(actual["pid"] == bound["pid"] and Path(actual["executable"]).resolve() == Path(bound["executable"]),
            "Actual PID/executable differs from launch receipt")
    require(isinstance(actual.get("created"), str) and bool(actual["created"]), "PID creation generation unavailable")
    require(set(actual["listeners"]) == {bound["pid"]}, "Debug port is not owned exclusively by launch PID")
    return actual


class Client:
    def __init__(self, port, raw_file, deadline):
        self.port, self.raw_file, self.deadline, self.serial = port, raw_file, deadline, 0

    def get(self, name):
        require(name in GETTERS, "Getter not allowed: " + name)
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Bounded observation deadline reached")
        self.serial += 1
        request = {"id": self.serial, "cmd": name, **GETTERS[name]}
        sent = time.monotonic()
        record = {"sent_monotonic": sent, "request": request}
        data = bytearray()
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=min(2, remaining)) as connection:
                connection.sendall((json.dumps(request) + "\n").encode("ascii"))
                while b"\n" not in data:
                    connection.settimeout(max(.001, min(2, self.deadline - time.monotonic())))
                    chunk = connection.recv(65536)
                    require(bool(chunk), "Debug socket closed before a complete response")
                    data.extend(chunk)
                    require(len(data) <= 1024 * 1024, "Getter response exceeds 1 MiB")
                    if time.monotonic() >= self.deadline and b"\n" not in data:
                        raise TimeoutError("Bounded observation deadline reached")
            response = json.loads(data.split(b"\n", 1)[0])
            require(response.get("id") == self.serial, "Response ID mismatch")
            record["response"] = response
            require(response.get("ok") is True, str(response))
            return response, (sent + time.monotonic()) / 2
        except Exception as error:
            record["error"] = str(error)
            if "response" not in record:
                record["incomplete_wire_utf8"] = data.decode("utf-8", errors="replace")
            raise
        finally:
            record["received_monotonic"] = time.monotonic()
            self.raw_file.write(json.dumps(record, allow_nan=False) + "\n")
            self.raw_file.flush()


def collect(args):
    require(1 <= args.seconds <= 30, "Observation duration must be 1..30 seconds")
    window = None
    if args.facade_frames:
        window = [int(x) for x in args.facade_frames.split(":")]
        require(len(window) == 2 and 0 <= window[0] <= window[1], "Expected facade guest-frame range start:end")
    bound = binding(args.candidate)
    actual = inspect_process(bound)
    output = args.output.resolve()
    require(output.parent == Path(bound["evidence"]).resolve(), "New output directory must be directly inside candidate evidence")
    require(not output.exists(), "New output directory required")
    output.mkdir()
    tracker = Tracker(window)
    report = {"binding": bound, "identity_before": actual, "collector_sha256": digest(Path(__file__)),
              "requested_seconds": args.seconds, "requested_phase_annotation": args.phase,
              "phase_is_not_residency_proof": True, "errors": [], "game_input_actions": 0,
              "runtime_mutations": 0, "process_actions": 0, "pixel_captures": 0,
              "raw_jsonl": str(output / "raw-getters.jsonl"), "frame_perf": None,
              "frame_perf_scope": "Optional final rolling aggregate of at most 256 samples with about four-frame query delay; not the exact collector interval"}
    started = time.monotonic()
    deadline = started + args.seconds
    with (output / "raw-getters.jsonl").open("x", encoding="utf-8") as raw:
        client = Client(bound["port"], raw, deadline)
        try:
            turbo, _ = client.get("turbo_state")
            require(turbo.get("enabled") == 0, "Manual turbo enabled; collector will not change it")
            tick = time.monotonic()
            while time.monotonic() < deadline:
                sample = {}
                sample["get_registers"], sample["guest_midpoint"] = client.get("get_registers")
                for command in ("gl_present_ring", "latency", "gl_interp"):
                    sample[command], _ = client.get(command)
                tracker.add(sample)
                if args.frame_perf and report["frame_perf"] is None and deadline - time.monotonic() <= 1.5:
                    try:
                        report["frame_perf"], _ = client.get("frame_perf")
                    except ValueError as error:
                        report["frame_perf"] = {"unavailable": str(error)}
                tick += 1
                wait = min(tick, deadline) - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
        except Exception as error:
            report["errors"].append(str(error))
    report["observation_wall_seconds"] = time.monotonic() - started
    try:
        require(binding(args.candidate) == bound, "Candidate/report/launch/executable changed during observation")
        report["identity_after"] = inspect_process(bound)
        require(report["identity_after"] == actual, "PID generation or debug-port owner changed")
    except Exception as error:
        report["errors"].append(str(error))
    report["analysis"] = tracker.report()
    epochs = report["analysis"]["epochs"]
    report["collection_finished_without_errors"] = not report["errors"]
    report["complete"] = not report["errors"] and len(epochs) == 1 and \
        epochs[0]["guest_vblank_progress"] > 0 and \
        epochs[0]["native_cycle_input_mark_period"]["n"] > 0 and \
        epochs[0]["gl_pre_swap_period"]["n"] > 0 and \
        epochs[0]["latency_period_missing_records"] == 0 and \
        epochs[0]["gl_period_missing_records"] == 0
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(output / "report.json"), "complete": report["complete"], "errors": report["errors"]}))
    return 0 if report["complete"] else 1


def fixture(head, rows, events=None, guest=None, midpoint=None):
    return {"get_registers": {"frame": head if guest is None else guest},
            "guest_midpoint": float(head if midpoint is None else midpoint),
            "latency": {"summary": {"frames": head}, "frames": rows},
            "gl_present_ring": {"total": head, "events": events or []}, "gl_interp": {"enabled": 0}}


def row(f, t, complete=True):
    return {"f": f, "input": t, "paced": t - 1,
            "swap_begin": t + 100 if complete else -1, "swap_end": t + 200 if complete else -1}


class OfflineFixtures(unittest.TestCase):
    def tracker(self):
        tracker = Tracker()
        tracker.add(fixture(2, [row(0, 0), row(1, 16000)]))
        return tracker

    def test_response_anchor_shift_and_dedupe(self):
        t = self.tracker()
        t.add(fixture(4, [row(1, 0), row(2, 16000), row(3, 32000)]))
        t.add(fixture(6, [row(2, 0), row(3, 16000), row(4, 32000)]))
        e = t.report()["epochs"][0]
        self.assertEqual(e["native_cycle_input_mark_period"]["n"], 3)
        self.assertEqual(e["native_cycle_input_mark_period"]["max_ms"], 16)
        self.assertEqual(len(t.epochs), 1)

    def test_incomplete_then_complete(self):
        t = self.tracker()
        t.add(fixture(5, [row(1, 0), row(2, 16000), row(3, 32000, False)]))
        self.assertEqual(t.report()["epochs"][0]["latency_incomplete_cycle_records"], 1)
        t.add(fixture(5, [row(1, 0), row(2, 16000), row(3, 32000)]))
        self.assertEqual(t.report()["epochs"][0]["latency_incomplete_cycle_records"], 0)
        self.assertEqual(t.report()["epochs"][0]["native_cycle_input_mark_period"]["n"], 2)

    def test_capped_window_does_not_bridge(self):
        t = self.tracker()
        t.add(fixture(13, [row(10, 0), row(11, 16000)]))
        e = t.report()["epochs"][0]
        self.assertEqual(e["native_cycle_input_mark_period"]["n"], 1)
        self.assertEqual(e["latency_missing_cycle_records"], 8)

    def test_duplicate_rows(self):
        t = self.tracker()
        t.add(fixture(4, [row(1, 0), row(2, 16000, False), row(2, 16000), row(2, 16000)]))
        self.assertEqual(t.report()["epochs"][0]["native_cycle_input_mark_period"]["n"], 1)

    def test_counter_epoch_reset(self):
        t = self.tracker()
        t.add(fixture(1, [row(0, 0)], midpoint=3))
        r = t.report()
        self.assertEqual(r["counter_epoch_changes"], 1)
        self.assertIsNone(r["cross_epoch_rate_or_interval"])

    def test_ring_index_wrap_is_continuous(self):
        t = Tracker()
        t.add(fixture(4095, [row(4094, 0)]))
        t.add(fixture(4098, [row(4094, 0), row(4095, 16000), row(4096, 32000)]))
        self.assertEqual(t.report()["epochs"][0]["native_cycle_input_mark_period"]["n"], 2)
        self.assertEqual(len(t.epochs), 1)

    def test_uint64_reset_is_new_epoch(self):
        t = Tracker()
        t.add(fixture(UINT64 - 1, []))
        t.add(fixture(2, [row(0, 0), row(1, 16000)]))
        self.assertEqual(len(t.epochs), 2)

    def test_gl_tick_wrap_and_guest_labels(self):
        t = self.tracker()
        events = [[1, 900, "vram", 0xFFFFFFF8, [], [], [], 0],
                  [2, 900, "interp", 8, [], [], [], 0]]
        t.facade_window = [900, 900]
        t.add(fixture(3, [], events, guest=1000))
        e = t.report()["epochs"][0]
        self.assertEqual(e["gl_pre_swap_period"]["max_ms"], 16)
        self.assertEqual(e["known_facade_guest_window_pre_swap_period"]["n"], 1)
        self.assertEqual(e["present_path_counts"], {"interp": 1})

    def test_gl_sequence_gap_not_bridged(self):
        t = self.tracker()
        t.add(fixture(5, [], [[2, 4, "vram", 100, [], [], [], 0], [4, 5, "vram", 150, [], [], [], 0]]))
        self.assertEqual(t.report()["epochs"][0]["gl_pre_swap_period"]["n"], 0)

    def test_invalid_latency_stamps(self):
        self.assertEqual(latency_rows({"frames": [row(1, float("nan")), row(2, 1e18), row(-1, 0)]}), {})

    def test_active_complete_cycle_waits_for_final_swap(self):
        t = self.tracker()
        t.add(fixture(3, [row(1, 0), row(2, 16000)]))
        self.assertEqual(t.report()["epochs"][0]["last_swap_block_per_native_cycle"]["n"], 0)
        completed = row(2, 16000)
        completed["swap_end"] = completed["swap_begin"] + 8000
        t.add(fixture(4, [row(1, 0), completed, row(3, 32000)]))
        self.assertEqual(t.report()["epochs"][0]["last_swap_block_per_native_cycle"]["max_ms"], 8)

    def test_inconsistent_anchor_creates_epoch(self):
        t = self.tracker()
        t.add(fixture(3, [row(0, 0), row(1, 20000), row(2, 36000)]))
        self.assertEqual(len(t.epochs), 2)

    def test_getter_allowlist_rejects_mutations_before_socket(self):
        c = Client(1, None, time.monotonic() + 1)
        for name in ("quit", "turbo", "set_input", "write_ram", "research_capture", "present_shot", "reset"):
            with self.assertRaisesRegex(ValueError, "Getter not allowed"):
                c.get(name)

    def test_report_binding_hash_and_port(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            exe = p / "runtime.exe"
            exe.write_bytes(b"offline fixture only")
            candidate = p / "candidate.json"
            report = {"evidence": str(p), "debug_port": 4377,
                      "launches": {"candidate": {"arguments": [str(exe), "--debug-port", "4377"], "executable_sha256": digest(exe)}}}
            candidate.write_text(json.dumps(report))
            launch = {"pid": 123, "debug_port": 4377, "executable": str(exe)}
            (p / "launch-candidate.json").write_text(json.dumps(launch))
            self.assertEqual(binding(candidate)["port"], 4377)
            exe.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "SHA256"):
                binding(candidate)
            exe.write_bytes(b"offline fixture only")
            launch["debug_port"] = 4378
            (p / "launch-candidate.json").write_text(json.dumps(launch))
            with self.assertRaisesRegex(ValueError, "receipt"):
                binding(candidate)

    def test_actual_pid_port_generation_validation(self):
        bound = {"pid": 123, "port": 4377, "executable": str(Path("offline.exe").resolve())}
        actual = {"pid": 123, "executable": bound["executable"], "created": "2026-11-12T00:00:00Z", "listeners": [123]}
        with patch("subprocess.run", return_value=SimpleNamespace(stdout=json.dumps(actual))):
            self.assertEqual(inspect_process(bound), actual)
        for field, value in [("pid", 124), ("listeners", [124]), ("created", None), ("executable", str(Path("wrong.exe").resolve()))]:
            bad = dict(actual, **{field: value})
            with patch("subprocess.run", return_value=SimpleNamespace(stdout=json.dumps(bad))):
                with self.assertRaises(ValueError):
                    inspect_process(bound)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seconds", type=float, default=10)
    parser.add_argument("--phase", choices=("first-encounter", "later-reentry", "unclassified"), default="unclassified")
    parser.add_argument("--facade-frames", help="Known guest frame interval start:end; correlation only")
    parser.add_argument("--frame-perf", action="store_true", help="Also read existing optional timer-query aggregate; never enables it")
    args = parser.parse_args()
    if args.self_test:
        unittest.main(argv=[__file__], verbosity=2)
    else:
        parser.error("--candidate and --output are required") if not args.candidate or not args.output else None
        raise SystemExit(collect(args))
