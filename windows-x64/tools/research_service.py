"""Bounded, read-only research runs. Observations never verify game addresses.

Each run owns a unique directory. Snapshots and event lines are append-only;
the final manifest is written once and its SHA256 is recorded in the index.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import threading
import time
import uuid

DEFAULT_WINDOWS = [
    dict(id="player_counters", address="0x80081320", length=0x140),
    dict(id="weapon_objects", address="0x80084800", length=0x500),
    dict(id="player_object", address="0x800856E0", length=0xA0),
    dict(id="progression", address="0x800ADA40", length=0x20),
]
DEFAULT_LIMITS = dict(duration_seconds=180., interval_seconds=1., max_samples=300, max_events=64,
                      max_disk_bytes=32*1024*1024, native_max_sources=32, native_max_records=5000,
                      native_max_events=6, native_max_frames=10800, native_max_bytes=24*1024*1024)
LIMIT_BOUNDS = dict(duration_seconds=(5., 300.), interval_seconds=(0.25, 10.), max_samples=(2, 1800),
                    max_events=(1, 128), max_disk_bytes=(1024*1024, 128*1024*1024), native_max_sources=(1, 256),
                    native_max_records=(1, 20000), native_max_events=(1, 32), native_max_frames=(1, 18000),
                    native_max_bytes=(256*1024, 128*1024*1024))
ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_RUNS = 128
RESERVE_BYTES = 512 * 1024
NATIVE_CONTRACT = "ein-research-v1"
EVENT_HEADER_BYTES = 160
EVENT_RAM_BYTES = 2 * 1024 * 1024
EVENT_VRAM_BYTES = 1024 * 1024
EVENT_BYTES = EVENT_HEADER_BYTES + EVENT_RAM_BYTES + EVENT_VRAM_BYTES
NATIVE_ATTACH_WINDOW_SECONDS = 30.
NATIVE_ATTACH_MAX_ATTEMPTS = 3
NATIVE_ATTACH_MAX_CHECKS = 7
NATIVE_NOT_READY = "OpenGL HD source tracker is not ready"


def utc():
    return datetime.now(timezone.utc).isoformat()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def confined(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Research paths must remain inside this workspace")
    return path


def label(value, default="Observation"):
    if value is None:
        value = default
    if not isinstance(value, str) or any(ord(char) < 32 for char in value) or len(value) > 160:
        raise ValueError("Use a label of at most 160 characters without control characters")
    return value.strip() or default


def limits(request):
    requested = request or {}
    if not isinstance(requested, dict) or set(requested) - set(DEFAULT_LIMITS):
        raise ValueError("Unknown research limit")
    result = dict(DEFAULT_LIMITS)
    for key, value in requested.items():
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError(key + " must be a finite number")
        low, high = LIMIT_BOUNDS[key]
        if not low <= value <= high or isinstance(DEFAULT_LIMITS[key], int) and int(value) != value:
            raise ValueError(f"{key} must be between {low} and {high}")
        result[key] = value
    # Leave room for RAM windows, event records and the immutable manifest.
    backend_reserve = min(4*1024*1024, result["max_disk_bytes"]//4)
    result["native_max_bytes"] = min(result["native_max_bytes"], result["max_disk_bytes"]-backend_reserve)
    return result


def source_filter_config(value=None):
    """Validate an optional exact raw-source filter; never silently truncate it."""
    value = dict(policy="all", keys=[]) if value is None else value
    if not isinstance(value, dict) or set(value) - {"policy", "keys"}:
        raise ValueError("Source filter accepts only policy and keys")
    policy, keys = value.get("policy", "all"), value.get("keys", [])
    if not isinstance(policy, str) or policy not in ("all", "include", "exclude"):
        raise ValueError("Source filter policy must be all, include or exclude")
    if not isinstance(keys, list) or len(keys) > 256 or any(not isinstance(key, str) or re.fullmatch(r"[0-9A-F]{8}-[0-9A-F]{8}", key) is None for key in keys):
        raise ValueError("Source filter keys must be at most256 uppercase CRC pairs")
    if len(set(keys)) != len(keys) or (policy == "all") != (len(keys) == 0):
        raise ValueError("Source filter requires unique keys; include/exclude requires nonempty keys and all accepts none")
    return dict(policy=policy, keys=sorted(keys))


class ResearchStopped(RuntimeError):
    pass


class ResearchBudget(RuntimeError):
    pass


class ResearchService:
    def __init__(self, root, command, clock=time.monotonic, watch_interval=2., context=None):
        self.root = Path(root).resolve()
        self.command = command
        self.context = context
        self.clock = clock
        self.watch_interval = watch_interval
        self.lock = threading.RLock()
        self.io_lock = threading.RLock()
        self.start_lock = threading.Lock()
        self.active = None
        self.worker = None
        self.watcher = None
        self.watch_stop = threading.Event()
        self.armed = False
        self.arm_config = None
        self.watch_status = "disarmed"
        self.last_error = None
        self.last_completed = None
        self._watch_online = False
        self._watch_frame = None
        self._pending_edge = False

    def catalog(self):
        path = self.root / "tools" / "research_catalog.json"
        if path.is_file() and path.stat().st_size <= 1024*1024:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        else:
            data = dict(scenarios=[dict(id="free_observation", label="Free observation", description="Candidate data only; manual game actions.", task_ids=[])], tasks=[], limitations=["Detailed research catalog is unavailable."])
        for scenario in data.get("scenarios", []):
            scenario.setdefault("label", scenario.get("title", scenario.get("id")))
            scenario.setdefault("description", "Manual observation; captured differences remain candidates.")
            scenario.setdefault("task_ids", [])
        data.setdefault("tasks", [])
        data["ram_windows"] = DEFAULT_WINDOWS
        data["ram_window_bytes"] = sum(window["length"] for window in DEFAULT_WINDOWS)
        data["default_limits"] = DEFAULT_LIMITS
        data["limit_bounds"] = LIMIT_BOUNDS
        return data

    def _history(self):
        path = confined(self.root, "tools/research-index.json")
        if not path.is_file():
            return []
        if path.stat().st_size > 1024*1024:
            raise ValueError("Research index exceeds its 1 MiB budget")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, list) or len(value) > MAX_RUNS:
            raise ValueError("Research index is invalid or exceeds its run budget")
        if any(not isinstance(row, dict) or not isinstance(row.get("bytes"), int) or row["bytes"] < 0 for row in value):
            raise ValueError("Research index contains invalid run sizes")
        return value

    def _archive_usage(self):
        base = confined(self.root, "tools/research-runs")
        total, files = 0, 0
        if base.is_dir():
            for path in base.rglob("*"):
                if path.is_file() and not path.is_symlink():
                    if not path.resolve().is_relative_to(base):
                        raise ValueError("Research archive contains an external file alias")
                    total += path.stat().st_size
                    files += 1
                    if total > ARCHIVE_BYTES or files > MAX_RUNS*2048:
                        raise ValueError("Cumulative research archive budget reached")
        return total

    def _atomic_json(self, relative, value):
        path = confined(self.root, relative)
        if (self.root / relative).is_symlink():
            raise ValueError("Research preference and index files cannot be symlinks")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = confined(self.root, str(Path(relative).parent / (".research-" + uuid.uuid4().hex + ".json")))
        try:
            with temporary.open("xb") as output:
                output.write(json_bytes(value))
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def _probe(self):
        reply = self.command(dict(cmd="gpu_state"), timeout=1.)
        if not reply.get("ok"):
            raise RuntimeError(reply.get("error", "Game is offline"))
        frame = reply.get("ws", {}).get("cur_frame")
        if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
            raise RuntimeError("Runtime does not expose a valid frame counter")
        return reply, frame

    def _native_size(self, run):
        total, count = 0, 0
        for path in (run["path"] / "native").glob("*"):
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
                count += 1
        return total, count

    def _write(self, run, relative, body, append=False, final=False):
        data = body if isinstance(body, bytes) else json_bytes(body)
        native_bytes, native_files = self._native_size(run)
        limit = run["limits"]["max_disk_bytes"] - (0 if final else RESERVE_BYTES)
        if run["backend_bytes"] + native_bytes + len(data) > limit:
            raise ResearchBudget("Run disk budget reached")
        if not final and native_files + run["backend_files"] >= 2047:
            raise ResearchBudget("Run file budget reached")
        path = confined(run["path"], relative)
        exists = path.exists()
        with path.open("ab" if append else "xb") as output:
            output.write(data)
        run["backend_bytes"] += len(data)
        if not exists:
            run["backend_files"] += 1
        return relative

    def _runtime_artifact(self):
        receipt_path = self.root / "tools" / "material-runtime.json"
        result = dict(active_process_sha_verified=False, scope="Local build artifact receipt; executable identity of the connected process is not exposed by this protocol")
        if not receipt_path.is_file() or receipt_path.stat().st_size > 1024*1024:
            return dict(result, available=False)
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            executable = Path(receipt.get("executable", "")).resolve()
            result.update(available=True, receipt_sha256=hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
                          contract=receipt.get("contract"), executable=str(executable), declared_sha256=receipt.get("sha256"))
            if executable.is_relative_to(self.root) and executable.is_file():
                result["artifact_sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
                result["artifact_matches_receipt"] = result["artifact_sha256"] == receipt.get("sha256")
            return result
        except (OSError, ValueError, TypeError) as exc:
            return dict(result, available=False, error=str(exc))

    def _context(self, run, why):
        result = dict(available=False)
        if self.context is not None:
            try:
                result = dict(available=True, local_assists=self.context())
            except Exception as exc:
                result = dict(available=False, error=str(exc))
        # One read-only material query per sample/marker detects live color
        # generation changes. Unsupported builds are not repeatedly queried.
        if run.get("material_unsupported"):
            result["materials"] = dict(available=False, error=run["material_unsupported"])
        else:
            material = self.command(dict(cmd="skin_material"), timeout=1.)
            result["materials"] = material
            if not material.get("ok"):
                run["material_unsupported"] = material.get("error", "Material status unsupported")
        return result

    def _snapshot(self, run, why, allow_stopping=False):
        if run["stop"].is_set() and not allow_stopping:
            raise ResearchStopped()
        _, frame = self._probe()
        if run.get("last_frame") is not None and frame < run["last_frame"]:
            raise RuntimeError("frame_reset")
        windows = []
        for window in DEFAULT_WINDOWS:
            if run["stop"].is_set() and not allow_stopping:
                raise ResearchStopped()
            response = self.command(dict(cmd="read_ram", addr=window["address"], len=window["length"]), timeout=1.)
            if not response.get("ok"):
                raise RuntimeError(response.get("error", "RAM read disconnected"))
            raw = response.get("hex", response.get("data", ""))
            try:
                data = bytes.fromhex(raw)
            except (TypeError, ValueError) as exc:
                raise RuntimeError("Malformed RAM snapshot") from exc
            if len(data) != window["length"]:
                raise RuntimeError("RAM snapshot length differs from request")
            windows.append(dict(window, hex=data.hex(), sha256=hashlib.sha256(data).hexdigest()))
        snapshot = dict(id="snapshot-" + uuid.uuid4().hex[:12], at=utc(), frame=frame, why=why,
                        atomic=False, scope="Sequential read-only windows; not a same-frame snapshot", windows=windows,
                        context=self._context(run, why))
        filename = snapshot["id"] + ".json"
        self._write(run, filename, snapshot)
        snapshot["file"] = filename
        run["last_frame"] = frame
        return snapshot

    @staticmethod
    def _changes(before, after, cap=128):
        candidates, count = [], 0
        if not before:
            return dict(changed_bytes=0, candidates=[], truncated=False, verified=False)
        old = {row["id"]: row for row in before["windows"]}
        for row in after["windows"]:
            previous = old.get(row["id"])
            if not previous:
                continue
            a, b = bytes.fromhex(previous["hex"]), bytes.fromhex(row["hex"])
            for offset, (left, right) in enumerate(zip(a, b)):
                if left != right:
                    count += 1
                    if len(candidates) < cap:
                        candidates.append(dict(address=f"0x{int(row['address'],16)+offset:08X}", width=1, before=left, after=right, window=row["id"], status="candidate_unverified"))
        return dict(changed_bytes=count, candidates=candidates, truncated=count > len(candidates), verified=False,
                    before_frame=before["frame"], after_frame=after["frame"], scope="Observed byte differences; ownership and causality are unverified")

    def _native(self, run, operation, **extra):
        request = dict(cmd="research_capture", op=operation, **extra)
        response = self.command(request, timeout=2.)
        response = dict(response, observed_at=utc())
        run["native_last"] = response
        return response

    def _native_valid(self, response, run=None):
        if not isinstance(response, dict) or response.get("ok") is not True or response.get("contract") != NATIVE_CONTRACT:
            return False
        if run is not None:
            try:
                if Path(response.get("path", "")).resolve() != (run["path"] / "native").resolve():
                    return False
            except (OSError, TypeError, ValueError):
                return False
        return True

    def _native_limits_valid(self, response, budget):
        acknowledged = response.get("limits", {})
        mapping = dict(max_sources="native_max_sources", max_records="native_max_records", max_events="native_max_events",
                       max_frames="native_max_frames", max_seconds="duration_seconds", max_bytes="native_max_bytes")
        return all(isinstance(acknowledged.get(key), (int, float)) and not isinstance(acknowledged[key], bool)
                   and math.isfinite(acknowledged[key]) and 0 < acknowledged[key] <= budget[source] for key, source in mapping.items())

    def _native_filter_valid(self, response, config):
        if config["policy"] == "all":
            return True  # Older runtimes retain their original unfiltered behavior.
        acknowledged = response.get("source_filter", {})
        fingerprint = self._fnv("".join(key + "\n" for key in config["keys"]).encode("ascii"))
        return (response.get("source_filter_supported") is True and acknowledged.get("policy") == config["policy"]
                and acknowledged.get("key_count") == len(config["keys"]) and acknowledged.get("keys_fnv1a32") == fingerprint
                and acknowledged.get("scope") == "raw_source_archives_only")

    @staticmethod
    def _fnv(data):
        value = 2166136261
        for byte in data:
            value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
        return value

    def _event_binary(self, run, response, expected_sha=None):
        if not self._native_valid(response, run) or not response.get("event_file"):
            raise ValueError("Native event lacks a validated capture contract/path acknowledgement")
        native = (run["path"] / "native").resolve()
        raw_path = response["event_file"]
        if not isinstance(raw_path, str):
            raise ValueError("Invalid native event path")
        path = (native / raw_path).resolve()
        if not path.is_relative_to(native) or not re.fullmatch(r"event-[0-9]{4,6}\.bin", path.name):
            raise ValueError("Native event path is outside its unique run directory")
        if not path.is_file() or path.stat().st_size != EVENT_BYTES:
            raise ValueError("Native event binary has an invalid bounded length")
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if expected_sha and digest != expected_sha:
            raise ValueError("Native event binary changed after acknowledgement")
        if data[:8] != b"EINRC01\0" or struct.unpack_from("<II", data, 8) != (1, EVENT_HEADER_BYTES):
            raise ValueError("Unknown native event binary schema")
        ram_offset, ram_size, vram_offset, vram_size = struct.unpack_from("<IIII", data, 32)
        if (ram_offset, ram_size, vram_offset, vram_size) != (160, EVENT_RAM_BYTES, 160+EVENT_RAM_BYTES, EVENT_VRAM_BYTES):
            raise ValueError("Native event memory offsets do not match the declared schema")
        frame = struct.unpack_from("<Q", data, 16)[0]
        host_mono_ms = struct.unpack_from("<Q", data, 24)[0]
        event_index, label_length, flags = struct.unpack_from("<III", data, 76)
        if label_length > 63 or not flags & 1 or frame != response.get("event_frame", response.get("frame")) or event_index != response.get("event_index"):
            raise ValueError("Native event frame/index/CPU-only flags do not match acknowledgement")
        if response.get("event_host_mono_ms", host_mono_ms) != host_mono_ms or response.get("event_bytes", response.get("bytes", EVENT_BYTES)) != EVENT_BYTES:
            raise ValueError("Native event timestamp/byte length does not match its exact acknowledgement")
        try:
            event_label = data[96:96+label_length].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("Native event label is not ASCII") from exc
        if any(ord(char) < 32 or ord(char) > 126 for char in event_label):
            raise ValueError("Native event label contains control characters")
        ram = data[ram_offset:ram_offset+ram_size]
        vram = data[vram_offset:vram_offset+vram_size]
        ram_fnv, vram_fnv = struct.unpack_from("<II", data, 68)
        if self._fnv(ram) != ram_fnv or self._fnv(vram) != vram_fnv:
            raise ValueError("Native event RAM/VRAM integrity check failed")
        dirty, pending, pack_dirty = struct.unpack_from("<III", data, 48)
        metadata = dict(file=path.relative_to(run["path"]).as_posix(), sha256=digest, bytes=len(data), frame=frame, host_mono_ms=host_mono_ms,
                        event_index=event_index, ram_sha256=hashlib.sha256(ram).hexdigest(), ram_fnv_verified=True,
                        label=event_label,
                        vram_fnv_verified=True, atomic_emulation_safe_point=True, gpu_readback=False,
                        cpu_vram_may_be_stale=True, coherence_flags=dict(gpu_dirty=dirty, pending_cpu_upload_rects=pending, pack_dirty=pack_dirty), candidate_only=True,
                        acknowledgement=response)
        return metadata, ram

    def _whole_ram_changes(self, run, before, after):
        _, a = self._event_binary(run, before["acknowledgement"], before["sha256"])
        _, b = self._event_binary(run, after["acknowledgement"], after["sha256"])
        changed = 0
        preferred, other, words = [], [], []
        windows = [(int(window["address"],16) & 0x1FFFFF, (int(window["address"],16) & 0x1FFFFF)+window["length"]) for window in DEFAULT_WINDOWS]
        for offset, (left, right) in enumerate(zip(a, b)):
            if left != right:
                changed += 1
                target = preferred if any(low <= offset < high for low, high in windows) else other
                if len(target) < 64:
                    target.append(dict(address=f"0x{0x80000000+offset:08X}", width=1, before=left, after=right, status="candidate_unverified"))
        candidates = (preferred + other)[:64]
        word_offsets = []
        for candidate in candidates:
            offset = (int(candidate["address"],16)-0x80000000) & ~1
            if offset not in word_offsets:
                word_offsets.append(offset)
            if len(word_offsets) == 32:
                break
        for offset in word_offsets:
            words.append(dict(address=f"0x{0x80000000+offset:08X}", width=2, before=int.from_bytes(a[offset:offset+2],"little"),
                              after=int.from_bytes(b[offset:offset+2],"little"), status="candidate_unverified"))
        return dict(changed_bytes=changed, candidates_u8=candidates, candidates_u16=words, truncated=changed > len(candidates), verified=False,
                    before_frame=before["frame"], after_frame=after["frame"], before_sha256=before["sha256"], after_sha256=after["sha256"],
                    scope="Two validated full-RAM safe-point observations; byte differences do not prove causality, entity identity or field semantics")

    def _native_mark(self, run, event_id):
        if not run["native_supported"]:
            state = run.get("native_attach", {}).get("state", "unavailable")
            return dict(ok=False, status=state, error="Native draw/event capture is not attached for this run: " + state)
        return self._native(run, "mark", label=event_id[:63])

    def _native_attach(self, run, retry=False):
        """Attach only startup-readiness failures; never renew an ended capture."""
        attach = run.setdefault("native_attach", dict(state="initial", attempts=0, checks=0, max_attempts=NATIVE_ATTACH_MAX_ATTEMPTS,
                                                       max_checks=NATIVE_ATTACH_MAX_CHECKS, window_seconds=NATIVE_ATTACH_WINDOW_SECONDS,
                                                       last_check_clock=run["started_clock"], last_check_sample=0))
        elapsed = self.clock()-run["started_clock"]
        if run["stop"].is_set():
            attach["state"] = "cancelled_before_attachment"
            return dict(ok=False, error="Research run is stopping")
        if retry:
            if attach["state"] != "pending_readiness":
                return None
            if elapsed >= NATIVE_ATTACH_WINDOW_SECONDS:
                attach["state"] = "readiness_window_expired"
                return None
            if attach["checks"] >= NATIVE_ATTACH_MAX_CHECKS or attach["attempts"] >= NATIVE_ATTACH_MAX_ATTEMPTS:
                attach["state"] = "readiness_attempt_limit"
                return None
            if run["samples"]-attach["last_check_sample"] < 5 or self.clock()-attach["last_check_clock"] < 5.:
                return None
        attach["checks"] += 1
        attach["last_check_clock"] = self.clock()
        attach["last_check_sample"] = run["samples"]
        capability = self._native(run, "status")
        result = dict(ok=False, error="Native capture contract is unavailable", capability=capability)
        if not self._native_valid(capability):
            attach["state"] = "unsupported_or_invalid_contract"
        elif capability.get("active") is not False:
            attach["state"] = "owned_elsewhere"
            result["error"] = "Another capture already owns the runtime"
        elif run.get("source_filter", {}).get("policy", "all") != "all" and capability.get("source_filter_supported") is not True:
            raise ValueError("Connected runtime does not support exact source filtering; no unfiltered fallback was started")
        elif capability.get("ready") is False:
            attach["state"] = "pending_readiness"
            result["error"] = NATIVE_NOT_READY
        elif capability.get("ready") is not True:
            attach["state"] = "invalid_readiness_acknowledgement"
        else:
            current_frame = capability.get("frame")
            if isinstance(current_frame, bool) or not isinstance(current_frame, int) or current_frame < 0:
                attach["state"] = "invalid_frame_acknowledgement"
                result["error"] = "Native capture frame is invalid"
            else:
                run.setdefault("native_frame_origin", current_frame)
                origin = run["native_frame_origin"]
                native_bytes, _ = self._native_size(run)
                remaining_seconds = int(run["limits"]["duration_seconds"]-elapsed)
                remaining_frames = int(run["limits"]["native_max_frames"]-(current_frame-origin))
                remaining_bytes = int(min(run["limits"]["native_max_bytes"]-native_bytes,
                                          run["limits"]["max_disk_bytes"]-run["backend_bytes"]-native_bytes-RESERVE_BYTES))
                chosen = dict(run["limits"], duration_seconds=remaining_seconds, native_max_frames=remaining_frames, native_max_bytes=remaining_bytes)
                native_directory = run["path"] / "native"
                if current_frame < origin or remaining_seconds < 1 or remaining_frames < 1 or remaining_bytes < 256*1024:
                    attach["state"] = "remaining_budget_exhausted"
                    result["error"] = "Original run has insufficient remaining native time/frame/byte budget"
                elif any(native_directory.iterdir()):
                    attach["state"] = "native_directory_not_empty"
                    result["error"] = "Owned native directory is not empty; capture will not be restarted or overwritten"
                else:
                    attach["attempts"] += 1
                    attach["requested_limits"] = chosen
                    config = run.get("source_filter", dict(policy="all", keys=[]))
                    filter_fields = dict(source_policy=config["policy"], source_keys=config["keys"]) if config["policy"] != "all" else {}
                    result = self._native(run, "start", path=str(native_directory), max_sources=int(chosen["native_max_sources"]),
                                          max_records=int(chosen["native_max_records"]), max_events=int(chosen["native_max_events"]),
                                          max_frames=remaining_frames, max_seconds=remaining_seconds, max_bytes=remaining_bytes, **filter_fields)
                    run["native_cleanup_needed"] = result.get("ok") is True
                    run["native_supported"] = (self._native_valid(result, run) and result.get("active") is True
                                               and self._native_limits_valid(result, chosen) and self._native_filter_valid(result, config))
                    if run["native_supported"]:
                        attach.update(state="attached", attached_frame=result.get("start_frame", result.get("frame")),
                                      attached_elapsed_seconds=round(elapsed,3), ram_only_prefix_seconds=round(elapsed,3))
                        run["baseline_native"] = self._native_mark(run, "baseline")
                        try:
                            run["latest_native"], _ = self._event_binary(run, run["baseline_native"])
                        except ValueError as exc:
                            run["native_binary_error"] = str(exc)
                    elif result.get("ok") is False and result.get("error") == NATIVE_NOT_READY:
                        attach["state"] = "pending_readiness"
                    else:
                        attach["state"] = "start_rejected"
                        if run["native_cleanup_needed"]:
                            run["native_rejected_stop"] = self._native(run, "stop")
                            run["native_cleanup_needed"] = False
                        if config["policy"] != "all":
                            raise ValueError("Exact source filter start/acknowledgement failed; unfiltered collection is not accepted")
        if self._native_valid(capability) and isinstance(capability.get("frame"), int) and not isinstance(capability["frame"], bool):
            run.setdefault("native_frame_origin", capability["frame"])
        if attach["state"] == "pending_readiness" and attach["attempts"] >= NATIVE_ATTACH_MAX_ATTEMPTS:
            attach["state"] = "readiness_attempt_limit"
        attach["last_reason"] = result.get("error")
        run.setdefault("native_initial_start", result)
        run["native_start"] = result
        self._write(run, "native-attach.jsonl", dict(at=utc(), elapsed_seconds=round(elapsed,3), retry=retry,
                                                     state=attach["state"], attempts=attach["attempts"], checks=attach["checks"],
                                                     capability=capability, result=result), append=True)
        return result

    def _request(self, request):
        catalog = self.catalog()
        identity = request.get("scenario", "free_observation")
        scenario = next((item for item in catalog.get("scenarios", []) if item.get("id") == identity), None)
        if scenario is None:
            raise ValueError("Choose a scenario from the research catalog")
        root = request.get("capture_root", "tools/research-runs")
        if not isinstance(root, str) or Path(root).is_absolute():
            raise ValueError("Research capture root must be project-relative")
        capture_root = confined(self.root, root)
        allowed_root = confined(self.root, "tools/research-runs")
        if not capture_root.is_relative_to(allowed_root):
            raise ValueError("Capture roots must remain under tools/research-runs (optional subdirectories are allowed)")
        return scenario, limits(request.get("limits")), capture_root, label(request.get("label"), scenario["label"]), source_filter_config(request.get("source_filter"))

    def start(self, request, auto=False):
        with self.start_lock:
            scenario, budget, capture_root, name, source_filter = self._request(request)
            if self.worker and self.worker.is_alive() or self.active:
                raise ValueError("A research run is already active or stopping")
            history = self._history()
            if len(history) >= MAX_RUNS or max(sum(row.get("bytes", 0) for row in history), self._archive_usage())+budget["max_disk_bytes"] > ARCHIVE_BYTES:
                raise ValueError("Cumulative research archive budget reached; preserve/export existing runs before starting more")
            self._probe()  # Offline start creates no run directory or evidence.
            if source_filter["policy"] != "all":
                capability = self.command(dict(cmd="research_capture", op="status"), timeout=2.)
                if not self._native_valid(capability) or capability.get("source_filter_supported") is not True:
                    raise ValueError("Connected runtime does not support exact source filtering; no run was started")
            identity = "research-" + time.strftime("%Y%m%d-%H%M%S", time.gmtime()) + "-" + uuid.uuid4().hex[:8]
            path = confined(capture_root, identity)
            path.mkdir(parents=True, exist_ok=False)
            (path / "native").mkdir()
            catalog_path = self.root / "tools" / "research_catalog.json"
            run = dict(id=identity, path=path, scenario=scenario["id"], label=name, limits=budget, started_at=utc(),
                       started_clock=self.clock(), stop=threading.Event(), stop_reason="manual_stop", samples=0, events=0,
                       backend_bytes=0, backend_files=0, pairs={}, candidate_bytes=0, native_supported=False, native_last={},
                       last_frame=None, latest=None, auto=auto, source_filter=source_filter,
                       catalog_sha256=hashlib.sha256(catalog_path.read_bytes()).hexdigest() if catalog_path.is_file() else None)
            run["runtime_artifact"] = self._runtime_artifact()
            self.active = run
            try:
                with self.io_lock:
                    self._write(run, "session.json", dict(id=identity, scenario=run["scenario"], label=name, started_at=run["started_at"], limits=budget,
                                                         ram_windows=DEFAULT_WINDOWS, catalog_sha256=run["catalog_sha256"], mode="read_only_candidate_collection", auto_armed=auto,
                                                         source_filter=source_filter))
                    run["latest"] = self._snapshot(run, "baseline")
                    run["samples"] = 1
                    if run["stop"].is_set():
                        raise ResearchStopped()
                    native = self._native_attach(run)
                if run["stop"].is_set():
                    raise ResearchStopped()
                self.worker = threading.Thread(target=self._loop, args=(run,), name="research-run", daemon=True)
                self.worker.start()
                if self.armed:
                    self._pending_edge = False
                    self._watch_online = True
                    self._watch_frame = run["last_frame"]
                return dict(ok=True, status=self.status(), native_capture=native,
                            note="Read-only collection started. Byte changes and texture receipts remain candidates, not verified addresses.")
            except (OSError, ValueError, RuntimeError, ResearchBudget, ResearchStopped) as exc:
                if not run["stop"].is_set():
                    run["stop_reason"] = "start_failed"
                run["error"] = str(exc)
                self._finish(run)
                return dict(ok=False, error=str(exc), status=self.status())

    def _loop(self, run):
        try:
            while not run["stop"].wait(run["limits"]["interval_seconds"]):
                if self.clock() - run["started_clock"] >= run["limits"]["duration_seconds"]:
                    run["stop_reason"] = "duration_limit"
                    break
                if run["samples"] >= run["limits"]["max_samples"]:
                    run["stop_reason"] = "sample_limit"
                    break
                with self.io_lock:
                    snapshot = self._snapshot(run, "periodic")
                    changes = self._changes(run["latest"], snapshot, cap=32)
                    self._write(run, "samples.jsonl", dict(at=snapshot["at"], frame=snapshot["frame"], snapshot=snapshot["file"], changes=changes), append=True)
                    run["candidate_bytes"] += changes["changed_bytes"]
                    run["latest"] = snapshot
                    run["samples"] += 1
                    if not run["native_supported"]:
                        self._native_attach(run, retry=True)
                    if run["native_supported"] and run["samples"] % 5 == 0 and not run["stop"].is_set():
                        native = self._native(run, "status")
                        if native.get("ok") and not self._native_valid(native, run):
                            run["native_supported"] = False
                            run["native_cleanup_needed"] = False
                            run["native_ownership_lost"] = True
        except ResearchStopped:
            pass
        except (OSError, ValueError, RuntimeError, ResearchBudget) as exc:
            run["stop_reason"] = "frame_reset" if str(exc) == "frame_reset" else "disk_limit" if isinstance(exc, ResearchBudget) else "disconnected_or_read_error"
            run["error"] = str(exc)
        finally:
            self._finish(run)

    def mark(self, request):
        try:
            return self._mark(request)
        except ResearchBudget as exc:
            if self.active:
                self.active["stop_reason"] = "disk_limit"
                self.active["error"] = str(exc)
                self.active["stop"].set()
            raise

    def _mark(self, request):
        with self.io_lock:
            run = self.active
            if not run or run["stop"].is_set():
                raise ValueError("Start a research run before marking an event")
            if run["events"] >= run["limits"]["max_events"]:
                raise ValueError("Research event budget reached")
            phase = request.get("phase", "point")
            if phase not in ("point", "before", "after"):
                raise ValueError("Event phase must be point, before or after")
            name = label(request.get("label"))
            task_id = request.get("task_id") or None
            if task_id is not None:
                task = next((task for task in self.catalog().get("tasks", []) if task.get("id") == task_id), None)
                if task is None or task.get("scenario_ids") and run["scenario"] not in task["scenario_ids"]:
                    raise ValueError("Unknown task id or task does not belong to the active scenario")
            pair_id = request.get("pair_id")
            if phase == "after" and (not isinstance(pair_id, str) or pair_id not in run["pairs"]):
                raise ValueError("Choose an open before-event pair_id")
            if phase == "after":
                paired_task = run["pairs"][pair_id]["task_id"]
                if task_id is not None and task_id != paired_task:
                    raise ValueError("After marker task_id must match its before marker")
                task_id = paired_task
            if phase == "before" and any(pair["label"] == name and pair["task_id"] == task_id for pair in run["pairs"].values()):
                raise ValueError("A before marker is already open for this label/task; close its pair first")
            before = run["pairs"][pair_id]["snapshot"] if phase == "after" else run["latest"]
            native_before = run["pairs"][pair_id].get("native_evidence") if phase == "after" else run.get("latest_native")
            event_id = "event-" + uuid.uuid4().hex[:12]
            try:
                snapshot = self._snapshot(run, "mark_" + phase)
            except (RuntimeError, ResearchBudget, OSError) as exc:
                run["stop_reason"] = "frame_reset" if str(exc) == "frame_reset" else "marker_read_or_budget_error"
                run["error"] = str(exc)
                run["stop"].set()
                raise
            native = self._native_mark(run, event_id)
            event = dict(id=event_id, phase=phase, label=name, task_id=task_id, at=utc(), frame=snapshot["frame"],
                         before_snapshot=before["file"] if before else None, after_snapshot=snapshot["file"],
                         native=native, changes=self._changes(before, snapshot), verified=False,
                         timing_scope="Explicit paired manual observations" if phase in ("before", "after") else "Latest prior sample to marker; approximate event window")
            try:
                native_evidence, _ = self._event_binary(run, native)
                if native_evidence["label"] != event_id:
                    raise ValueError("Native event label does not match the requested marker")
                event["native_evidence"] = native_evidence
                if phase != "before" and native_before:
                    whole = self._whole_ram_changes(run, native_before, native_evidence)
                    filename = event_id + "-whole-ram-candidates.json"
                    self._write(run, filename, whole)
                    event["whole_ram_candidates"] = dict(file=filename, changed_bytes=whole["changed_bytes"], verified=False,
                                                        before_frame=whole["before_frame"], after_frame=whole["after_frame"])
                run["latest_native"] = native_evidence
            except (ValueError, OSError) as exc:
                event["native_evidence"] = dict(available=False, error=str(exc), whole_ram_candidate_extraction="unavailable_for_this_marker")
            if phase == "before":
                pair_id = event_id
                run["pairs"][pair_id] = dict(snapshot=snapshot, label=name, task_id=task_id, native=native,
                                             native_evidence=event.get("native_evidence") if event.get("native_evidence", {}).get("sha256") else None)
            event["pair_id"] = pair_id
            if phase == "after":
                del run["pairs"][pair_id]
            self._write(run, "events.jsonl", event, append=True)
            run["events"] += 1
            run["latest"] = snapshot
            run["candidate_bytes"] += event["changes"]["changed_bytes"]
            return dict(ok=True, event=event, pair_id=pair_id, status=self.status())

    def stop(self, reason="manual_stop", wait=True):
        run = self.active
        if not run:
            return dict(ok=True, stopped=True, status=self.status())
        run["stop_reason"] = reason
        run["stop"].set()
        worker = self.worker
        if wait and worker and worker is not threading.current_thread():
            worker.join(timeout=4.)
        if wait and not worker:
            deadline = time.monotonic()+4.
            while self.active is run and not run.get("finalized") and time.monotonic() < deadline:
                time.sleep(0.01)
        stopping = self.active is run and not run.get("finalized")
        return dict(ok=not stopping, stopped=not stopping, status=self.status(),
                    note="Capture stop requested; pending read is finishing" if stopping else "Research run finalized; no sampling worker remains")

    def _finish(self, run):
        with self.io_lock:
            if run.get("finalized"):
                return
            run["stop"].set()
            if run.get("native_attach", {}).get("state") == "pending_readiness":
                run["native_attach"]["state"] = "cancelled_before_attachment"
            if run["native_supported"] or run.get("native_cleanup_needed"):
                try:
                    ownership = self._native(run, "status")
                    if self._native_valid(ownership, run):
                        run["native_stop"] = self._native(run, "stop")
                    else:
                        run["native_stop"] = dict(ok=False, error="Native capture ownership could not be confirmed; no global stop was sent", status=ownership)
                except Exception as exc:
                    run["native_stop"] = dict(ok=False, error=str(exc), note="Native hard deadline and byte limits remain the final safety bound")
            files = []
            for path in sorted(run["path"].rglob("*")):
                if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(run["path"].resolve()):
                    files.append(dict(path=path.relative_to(run["path"]).as_posix(), bytes=path.stat().st_size,
                                      sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            manifest = dict(schema_version=1, id=run["id"], scenario=run["scenario"], label=run["label"], started_at=run["started_at"],
                            ended_at=utc(), status="finalized", stop_reason=run["stop_reason"], error=run.get("error"), limits=run["limits"], source_filter=run.get("source_filter", dict(policy="all", keys=[])),
                            counters=dict(samples=run["samples"], events=run["events"], candidate_byte_changes=run["candidate_bytes"], incomplete_pairs=len(run["pairs"])),
                            native_capture=dict(supported=run["native_supported"], start=run.get("native_start"), baseline=run.get("baseline_native"),
                                                initial_start=run.get("native_initial_start"), attachment=run.get("native_attach"),
                                                baseline_validation_error=run.get("native_binary_error"), stop=run.get("native_stop"),
                                                ownership_lost=run.get("native_ownership_lost", False), rejected_start_stop=run.get("native_rejected_stop")),
                            files=files, catalog_sha256=run["catalog_sha256"], runtime_artifact=run["runtime_artifact"], verified=False,
                            limitations=["Sequential RAM windows are approximate observations, not same-frame captures or verified field ownership.",
                                         "Validated native event binaries enable bounded whole-RAM u8/u16 candidates; missing/invalid binary evidence is explicitly unavailable. CPU VRAM may be stale and no GPU readback is performed.",
                                         "File counts, changed bytes and source receipts do not verify an address, ship, weapon, effect or complete-stage coverage."])
            try:
                self._write(run, "manifest.json", manifest, final=True)
                path = run["path"] / "manifest.json"
                summary = dict(id=run["id"], scenario=run["scenario"], label=run["label"], status="finalized", stop_reason=run["stop_reason"],
                               started_at=run["started_at"], ended_at=manifest["ended_at"], events=run["events"], samples=run["samples"],
                               bytes=sum(row["bytes"] for row in files)+path.stat().st_size, verified=False,
                               manifest_path=str(path), manifest_url="/files/" + path.relative_to(self.root).as_posix(),
                               manifest_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                history = self._history()
                if len(history) < MAX_RUNS:
                    self._atomic_json("tools/research-index.json", history + [summary])
                self.last_completed = summary
            except (OSError, ValueError, ResearchBudget) as exc:
                self.last_error = "Finalization error: " + str(exc)
            run["finalized"] = True
            if self.active is run:
                self.active = None

    def status(self):
        run = self.active
        result = dict(running=bool(run), armed=self.armed, watcher_alive=bool(self.watcher and self.watcher.is_alive()), watch_status=self.watch_status,
                      last_error=self.last_error, last_completed=self.last_completed, default_limits=DEFAULT_LIMITS,
                      archive_limits=dict(max_bytes=ARCHIVE_BYTES, max_runs=MAX_RUNS), armed_config=self.arm_config)
        if run:
            native_bytes, _ = self._native_size(run)
            result.update(id=run["id"], scenario=run["scenario"], label=run["label"], state="stopping" if run["stop"].is_set() else "recording",
                          elapsed_seconds=round(self.clock()-run["started_clock"], 2), limits=run["limits"],
                          counters=dict(samples=run["samples"], events=run["events"], bytes=run["backend_bytes"]+native_bytes, candidate_byte_changes=run["candidate_bytes"]),
                          native_capture=dict(supported=run["native_supported"], active=run["native_last"].get("active") is True,
                                              attachment=run.get("native_attach"),
                                              last=run["native_last"], ownership_lost=run.get("native_ownership_lost", False)),
                          open_pairs=[dict(id=key, label=value["label"], task_id=value["task_id"], frame=value["snapshot"]["frame"]) for key,value in run["pairs"].items()])
        return result

    def overview(self):
        history = self._history()
        coverage = {}
        for row in history:
            current = coverage.setdefault(row["scenario"], dict(runs=0, marked_events=0, verified=False, status="candidate_evidence_only"))
            current["runs"] += 1
            current["marked_events"] += row.get("events", 0)
        return dict(ok=True, catalog=self.catalog(), status=self.status(), coverage=coverage, history=list(reversed(history)))

    def arm(self, request, persist=True):
        enabled = request.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("Arm requires enabled:true or enabled:false")
        if not enabled:
            self.armed = False
            self.watch_stop.set()
            if self.watcher and self.watcher is not threading.current_thread():
                self.watcher.join(timeout=3.)
            result = self.stop(reason="disarmed")
            self.watch_status = "disarmed"
            if persist:
                self._atomic_json("tools/research-arm.json", dict(enabled=False))
            return dict(ok=result["ok"], status=self.status())
        scenario, budget, capture_root, name, source_filter = self._request(request)
        if self.watcher and self.watcher.is_alive():
            raise ValueError("Research watcher is already armed; disarm before changing its scenario")
        self.arm_config = dict(scenario=scenario["id"], label=name, limits=budget, capture_root=capture_root.relative_to(self.root).as_posix(), source_filter=source_filter)
        if persist:
            self._atomic_json("tools/research-arm.json", dict(enabled=True, **self.arm_config))
        self.armed = True
        self._watch_online = False
        self._watch_frame = None
        self._pending_edge = False
        self.watch_status = "waiting_for_runtime"
        self.watch_stop = threading.Event()
        self.watcher = threading.Thread(target=self._watch, name="research-auto-arm", daemon=True)
        self.watcher.start()
        return dict(ok=True, status=self.status())

    def _watch(self):
        while not self.watch_stop.is_set() and self.armed:
            try:
                _, frame = self._probe()
            except (RuntimeError, ValueError, OSError) as exc:
                self.last_error = str(exc)
                self.watch_status = "waiting_for_runtime"
                self._watch_online = False
                self._watch_frame = None
            else:
                edge = not self._watch_online or self._watch_frame is not None and frame < self._watch_frame
                self._watch_online, self._watch_frame = True, frame
                if edge:
                    self._pending_edge = True
                if self._pending_edge and self.active is None and not (self.worker and self.worker.is_alive()):
                    self._pending_edge = False
                    if self.armed and not self.watch_stop.is_set():
                        try:
                            self.start(self.arm_config, auto=True)
                        except (RuntimeError, ValueError, OSError) as exc:
                            # Start-budget errors are not disconnect edges. Do
                            # not turn a full archive into a retry loop.
                            self.last_error = str(exc)
                self.watch_status = "recording" if self.active else "waiting_for_new_connection_or_reset"
            if self.watch_stop.wait(self.watch_interval):
                break

    def restore_arm(self):
        path = confined(self.root, "tools/research-arm.json")
        if path.is_file():
            try:
                config = json.loads(path.read_text(encoding="utf-8"))
                if config.get("enabled") is True:
                    self.arm(config, persist=False)
            except (OSError, ValueError, TypeError) as exc:
                self.last_error = "Saved arm preference was not restored: " + str(exc)

    def shutdown(self, persist_disarm=False):
        return self.arm(dict(enabled=False), persist=persist_disarm)

    def dispatch(self, request):
        action = request.get("action")
        if action == "start":
            return self.start(request)
        if action == "mark":
            return self.mark(request)
        if action == "stop":
            return self.stop()
        if action == "arm":
            return self.arm(request)
        raise ValueError("Use research action start, mark, stop or arm")
