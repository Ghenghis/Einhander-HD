"""Independent fake-transport test of the CANONICAL unassisted runner's default path (claude-einhander), r0.
Versioned file: never edited; a later revision is a new file.

Drives the real run() and the real enter_city() of C:/github/Einhander/remaster-audit/run_stage1_unassisted_review.py
through the real unassisted_command_guard (pre-send allowlist + durable intents + audit). Only the transport and
the OS boundary are replaced, in-process, and restored afterwards; no canonical file is written.

Replaced boundaries (every one is recorded in summary.json):
  * launch_ui_candidate.command and ui_candidate_probe.command (the socket transport) -> FakeRuntime, installed
    BEFORE guarded_commands so the guard wraps it exactly as in __main__. FakeRuntime writes receipts with the real
    launch_ui_candidate.write_command_receipt, in the same shape as the real transport (request incl. id=1, reply).
  * run_stage1_unassisted_review.fenced_launch -> fake that writes launch-candidate.json and returns FakeProcess
    (the fence itself is covered by root's 12 policy tests).
  * run_facade_ab_probe.identity (real Windows process query) -> fake reading launch-candidate.json.
  * run_facade_ab_probe.socket -> module whose create_connection always refuses (the runtime port is closed).
  * time in the runner, probe and close modules, and enter_city's _clock/_sleep -> one virtual clock, so the
    60-second default measurement and the 0.25-second route polling take no real time. The virtual sleep plays the
    operator: once the runner writes foreground-ready.json it creates FOREGROUND-READY.
  * run_stage1_pacing_ab.ROOT -> this run's private output directory (so nothing lands in the canonical tree).
Tripwires (must stay at zero): socket.socket, socket.create_connection, subprocess.Popen, subprocess.run.

Fixtures: the route screenshots are the PINNED 'hd' route references themselves (load_references verifies their
sha256). The harness first checks that classify_native puts each one in its intended state. The fake runtime starts
at title and advances title -> fighter -> arm -> city on each confirm press (set_input 0xBFFF). get_registers
advances the frame by 60 per call. All other replies carry exactly the fields the default path checks.

Cases:
  C1 default path   run() must finish with no errors and port_closed: route ok to city through 4 gates, 61 samples
                    with hd_cpu_profile each second, zero guard refusals, every command received was validated
                    (intents == transport receipts == runtime calls), audit clean, route set_input only in the
                    native-menu-route phase, no set_input in gameplay, zero tripwire hits.
  C2 focus loss     keyboard_focus 0 at gameplay second 7 -> run() must SystemExit(1) with the focus error, a
                    focus_rejected_sample, and still close (port_closed) and record the process exit.
  C3 injected       a savestate load is injected into the post-measurement capture path -> the guard must refuse it
     mutator        BEFORE transport (runtime never sees it, no intent written) and run() must SystemExit(1).
  C4 phase scope    with the guard active, set_input 0xBFFF in the gameplay phase and savestate are refused before
                    transport, while set_input 0xBFFF in the native-menu-route phase is accepted.
Usage: python fake_transport_default_path.r0.py --out-root DIR [--expect-runner-sha HEX --expect-guard-sha HEX]
Writes DIR/<stamp>/summary.json; exit 0 only if every case passes; 4 on a pin mismatch."""
import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_var] = "1"

import argparse  # noqa: E402
import contextlib  # noqa: E402
import datetime  # noqa: E402
import functools  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import socket  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import traceback  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

CANON = Path("C:/github/Einhander/remaster-audit")
RUNNER = CANON / "run_stage1_unassisted_review.py"
GUARD = CANON / "unassisted_command_guard.py"
DEPENDENCIES = ["native_ui_facade_route.py", "ui_candidate_probe.py", "launch_ui_candidate.py",
                "run_facade_ab_probe.py", "run_stage1_pacing_ab.py", "build_facade_ab_candidates.py",
                "run_h24_facade_review.py"]
FAKE_PID = 4242424
FRAME_STEP = 60


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class Tripwires:
    def __init__(self):
        self.hits = []

    def make(self, name):
        def tripped(*a, **k):
            self.hits.append(dict(name=name, args=repr(a)[:200]))
            raise AssertionError("tripwire: " + name)
        return tripped


class VirtualClock:
    def __init__(self):
        self.t = 1000.0
        self.slept = 0.0
        self.hooks = []

    def monotonic(self):
        return self.t

    def time(self):
        return 1.7e9 + self.t

    def sleep(self, seconds):
        seconds = max(0.0, float(seconds))
        self.t += seconds
        self.slept += seconds
        for hook in list(self.hooks):
            hook()

    def module(self):
        return SimpleNamespace(monotonic=self.monotonic, sleep=self.sleep, time=self.time,
                               perf_counter=self.monotonic)


class FakeProcess:
    def __init__(self):
        self.pid = FAKE_PID
        self.returncode = None

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired("fake-runtime", timeout)
        return self.returncode

    def terminate(self):
        if self.returncode is None:
            self.returncode = 1

    kill = terminate


class FakeRuntime:
    """Replies with exactly the fields the default path checks. Advances the route on each confirm press."""
    ORDER = ["title", "fighter", "arm", "city"]

    def __init__(self, ui, fixtures, process, focus_fail_second=None):
        self.ui, self.fixtures, self.process = ui, fixtures, process
        self.state = "title"
        self.frame = 1000
        self.present_seq = 0
        self.calls = []
        self.focus_fail_second = focus_fail_second
        self.gameplay_profile_calls = 0
        self.png = None

    def command(self, report, raw):
        evidence = Path(report["evidence"])
        if not (evidence / "launch-candidate.json").is_file():
            raise ValueError("Candidate must have a recorded launch before debug commands")
        request = json.loads(raw)
        if not isinstance(request, dict) or not isinstance(request.get("cmd"), str):
            raise ValueError("--command must be a JSON command object")
        request["id"] = 1
        fields = {k: v for k, v in request.items() if k not in ("cmd", "id")}
        self.calls.append(dict(cmd=request["cmd"], fields=fields, phase=report.get("command_phase", "gameplay"),
                               state=self.state, frame=self.frame))
        reply = self.dispatch(request["cmd"], fields, report)
        reply.setdefault("id", 1)
        self.ui.write_command_receipt(evidence / "commands",
                                      dict(at_utc=self.ui.stamp(), port=self.ui.PORT, request=request, reply=reply))
        return reply

    def dispatch(self, cmd, f, report):
        ok = dict(ok=True)
        if cmd == "get_registers":
            self.frame += FRAME_STEP
            return dict(ok=True, frame=self.frame, pc="0x80010000")
        if cmd == "screenshot":
            shutil.copyfile(self.fixtures[self.state], f["path"])
            return ok
        if cmd == "set_input":
            if f.get("buttons") == "0xBFFF" and self.state != "city":
                self.state = self.ORDER[self.ORDER.index(self.state) + 1]
            return ok
        if cmd in ("clear_input", "press", "display_ring_stats", "gpu_state"):
            return ok
        if cmd == "quit":
            self.process.returncode = 0
            return ok
        if cmd == "native_upload_selftest":
            return dict(ok=True, pbo_verified=True, state_restored=True, gl_error_test=0, gl_error_restore=0)
        if cmd in ("native_upload_ledger", "hd_upload_ledger"):
            return dict(ok=True, enabled=1, truncated=False, next_seq=0, total=0, entries=[])
        if cmd == "frame_phase_ring":
            return dict(ok=True, enabled=1, owner_bound=1, capacity=16384, qpc_frequency=10_000_000,
                        truncated=False, next_seq=0, events=[])
        if cmd == "gl_present_ring":
            return dict(ok=True, capacity=16384, truncated=False, missing=0, total=3,
                        events=[[0, 1], [1, 2], [2, 3]])
        if cmd == "hd_cpu_profile":
            if report.get("command_phase", "gameplay") == "gameplay":
                self.gameplay_profile_calls += 1
            lost = (self.focus_fail_second is not None and self.gameplay_profile_calls == self.focus_fail_second + 2)
            return dict(ok=True, keyboard_focus=0 if lost else 1, window_input_focus=1, hr_kept_leaks=0)
        if cmd in ("turbo", "turbo_state"):
            return dict(ok=True, enabled=0)
        if cmd == "read_ram":
            return dict(ok=True, addr=f.get("addr"), hex="00" * int(f.get("len", 1)))
        if cmd == "audio_stats":
            return dict(ok=True, taps=[], out=dict(underruns=0))
        if cmd == "present_shot_seq":
            return dict(ok=True, seq=self.present_seq, wrote=True)
        if cmd == "present_shot":
            from PIL import Image
            Image.new("RGB", (640, 480), (8, 16, 24)).save(f["path"])
            self.present_seq += 1
            return ok
        return dict(ok=False, error="fake runtime: unknown command " + cmd)


def load_canonical(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def default_report(directory):
    """visual/pacing profiles as prepare() builds them for the DEFAULT CLI (telemetry-only, 60 s, unassisted)."""
    visual = dict(kind="bounded stock/OpenGL gameplay review", normal_clock_settings=True,
                  stable_60fps_established=False, ordinary_fire=False, timer_only_assistance=False, lease_seconds=0,
                  stage_clear_acceptance=False, recorder_backend="gdigrab", capture_seconds=60, native_menus=False,
                  hd_pack_enabled=True, emissive=False, hires_stills=False, record_video=False,
                  source_capture=False, composed_stills=False, telemetry_only=True, cpu_profile=False,
                  runtime_perf=False, retain_host_audio=False, dirty_profile=False, media_profile=False,
                  rewind_capture=False, interp_pc_profile=False, process_loopback_seconds=0, post_video_seconds=0,
                  gpu_clock_profile=False, phase_profile=False, idle_skip_override=None, rewind_profile=False,
                  static_image_profile=False)
    return dict(evidence=str(directory), debug_port=4376, production_installed=False, files=[], emissive_files=[],
                visual_profile=visual,
                pacing_profile=dict(ram_writes=False, timer_assistance=False, hd_pack_enabled=True),
                launches=dict(candidate=dict(arguments=[str(directory / "runtime" / "fake.exe"),
                                                       "--window-title", "fake"], environment_overrides={})))


@contextlib.contextmanager
def patched(obj, name, value, log, tag):
    old = getattr(obj, name)
    setattr(obj, name, value)
    log.append(tag)
    try:
        yield
    finally:
        setattr(obj, name, old)


def run_case(case, out, mods, fixtures, focus_fail_second=None, inject_savestate=False):
    review, guard, route, ui, probe, close_mod, pacing = (mods[k] for k in
                                                          ("review", "guard", "route", "ui", "probe", "close", "pacing"))
    root = out / case
    batch, label = "fake-batch", "hd-on_rewind-off"
    directory = root / batch / label
    directory.mkdir(parents=True)
    (directory / "candidate.json").write_text(json.dumps(default_report(directory), indent=1) + "\n", encoding="utf-8")
    clock, trip, process = VirtualClock(), Tripwires(), FakeProcess()
    runtime = FakeRuntime(ui, fixtures, process, focus_fail_second)
    patches, launches, identities, connects = [], [], [], []

    def fake_fenced_launch(report):
        launches.append(now())
        pacing.base.write(Path(report["evidence"]) / "launch-candidate.json",
                          dict(pid=FAKE_PID, fake=True, at_utc=now()))
        return process

    def operator_hook():
        if (directory / "foreground-ready.json").exists() and not (directory / "FOREGROUND-READY").exists():
            (directory / "FOREGROUND-READY").write_text("fake operator handoff (virtual clock)\n")
    clock.hooks.append(operator_hook)

    def fake_identity(report):
        identities.append(now())
        return json.loads((Path(report["evidence"]) / "launch-candidate.json").read_bytes())

    def refused_connection(*a, **k):
        connects.append(repr(a)[:120])
        raise ConnectionRefusedError("fake runtime port closed")

    real_capture = probe.capture

    def capture_with_injection(report, label, hires=True):
        if inject_savestate:
            probe.request(report, "savestate", op="load", slot=0)
        return real_capture(report, label, hires=hires)

    vt = clock.module()
    result = dict(case=case)
    with contextlib.ExitStack() as stack:
        enter = stack.enter_context
        enter(patched(pacing, "ROOT", root, patches, "run_stage1_pacing_ab.ROOT"))
        enter(patched(review, "fenced_launch", fake_fenced_launch, patches, "review.fenced_launch"))
        enter(patched(review, "time", vt, patches, "review.time"))
        enter(patched(review, "enter_city", functools.partial(route.enter_city, _clock=clock.monotonic,
                                                              _sleep=clock.sleep), patches, "review.enter_city(_clock,_sleep)"))
        enter(patched(probe, "time", vt, patches, "ui_candidate_probe.time"))
        enter(patched(probe, "capture", capture_with_injection, patches, "ui_candidate_probe.capture(injection wrapper)"))
        enter(patched(close_mod, "time", vt, patches, "run_facade_ab_probe.time"))
        enter(patched(close_mod, "identity", fake_identity, patches, "run_facade_ab_probe.identity"))
        enter(patched(close_mod, "socket", SimpleNamespace(create_connection=refused_connection), patches,
                      "run_facade_ab_probe.socket"))
        enter(patched(ui, "command", runtime.command, patches, "launch_ui_candidate.command"))
        enter(patched(probe, "command", runtime.command, patches, "ui_candidate_probe.command"))
        enter(patched(socket, "socket", trip.make("socket.socket"), patches, "tripwire socket.socket"))
        enter(patched(socket, "create_connection", trip.make("socket.create_connection"), patches,
                      "tripwire socket.create_connection"))
        enter(patched(subprocess, "Popen", trip.make("subprocess.Popen"), patches, "tripwire subprocess.Popen"))
        enter(patched(subprocess, "run", trip.make("subprocess.run"), patches, "tripwire subprocess.run"))
        exit_code, error = 0, None
        try:
            with guard.guarded_commands(ui, probe):          # exactly as __main__ wraps run(args)
                review.run(SimpleNamespace(batch=batch, hd_pack_enabled=1, rewind=0))
        except SystemExit as e:
            exit_code = e.code
        except Exception as e:  # noqa: BLE001
            exit_code, error = "exception", traceback.format_exc()[-1500:]
    proof_path = directory / "world-flypast-proof.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8")) if proof_path.exists() else {}
    intents = list((directory / "command-intents").glob("*.json"))
    receipts = list((directory / "commands").glob("*.json"))
    route_proof = proof.get("route") or {}
    phases = {}
    for c in runtime.calls:
        key = c["cmd"] + (" " + json.dumps(c["fields"], sort_keys=True) if c["cmd"] in ("set_input", "press", "turbo") else "")
        phases.setdefault(key, {}).setdefault(c["phase"], 0)
        phases[key][c["phase"]] += 1
    result.update(exit_code=exit_code, exception=error, proof_errors=proof.get("errors"),
                  port_closed=(proof.get("close") or {}).get("port_closed"),
                  owned_process_exit=proof.get("owned_process_exit"),
                  route_ok=route_proof.get("ok"), route_final=route_proof.get("final_state"),
                  route_gates=[g.get("stage") + ":" + g.get("observed") for g in route_proof.get("gates", [])],
                  observations=len(proof.get("observations", [])),
                  focus_samples_ok=sum(1 for o in proof.get("observations", [])
                                       if (o.get("hd_cpu_profile") or {}).get("keyboard_focus") == 1),
                  focus_rejected=bool(proof.get("focus_rejected_sample")),
                  runtime_calls=len(runtime.calls), intents=len(intents), transport_receipts=len(receipts),
                  command_audit=proof.get("command_audit"), commands_by_phase=phases,
                  savestate_reached_runtime=any(c["cmd"] == "savestate" for c in runtime.calls),
                  fenced_launch_calls=len(launches), identity_calls=len(identities),
                  refused_port_probes=len(connects), tripwire_hits=trip.hits, patches=patches,
                  virtual_seconds_slept=round(clock.slept, 3), evidence=str(directory))
    return result


def phase_scope_case(out, mods):
    """C4: direct guard checks with the real guard and a recording transport."""
    guard, ui, probe = mods["guard"], mods["ui"], mods["probe"]
    directory = out / "C4" / "evidence"
    directory.mkdir(parents=True)
    (directory / "launch-candidate.json").write_text(json.dumps(dict(pid=FAKE_PID)) + "\n")
    report = default_report(directory)
    sent = []

    def recording(report_, raw):
        sent.append(json.loads(raw))
        return dict(ok=True)
    checks = {}
    with patched(ui, "command", recording, [], "ui.command"), patched(probe, "command", recording, [], "probe.command"):
        with guard.guarded_commands(ui, probe):
            for name, phase, cmd, fields, expect_ok in (
                    ("route_confirm_in_gameplay_refused", "gameplay", "set_input", dict(buttons="0xBFFF"), False),
                    ("route_down_in_gameplay_refused", "gameplay", "set_input", dict(buttons="0xFFBF"), False),
                    ("savestate_load_refused", "gameplay", "savestate", dict(op="load", slot=0), False),
                    ("savestate_in_route_refused", "native-menu-route", "savestate", dict(op="save", slot=0), False),
                    ("route_confirm_in_route_accepted", "native-menu-route", "set_input", dict(buttons="0xBFFF"), True)):
                report["command_phase"] = phase
                before_sent = len(sent)
                before_intents = len(list((directory / "command-intents").glob("*.json"))) \
                    if (directory / "command-intents").exists() else 0
                try:
                    probe.request(report, cmd, **fields)
                    accepted = True
                except ValueError:
                    accepted = False
                after_intents = len(list((directory / "command-intents").glob("*.json"))) \
                    if (directory / "command-intents").exists() else 0
                transported = len(sent) > before_sent
                checks[name] = dict(passed=(accepted == expect_ok and transported == expect_ok
                                            and (after_intents > before_intents) == expect_ok),
                                    accepted=accepted, transported=transported,
                                    intent_written=after_intents > before_intents)
    return dict(case="C4", checks=checks, passed=all(v["passed"] for v in checks.values()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--expect-runner-sha")
    ap.add_argument("--expect-guard-sha")
    a = ap.parse_args()
    pins = dict(harness=sha(__file__), runner=sha(RUNNER), guard=sha(GUARD),
                **{d: sha(CANON / d) for d in DEPENDENCIES})
    if (a.expect_runner_sha and pins["runner"] != a.expect_runner_sha.lower()) or \
            (a.expect_guard_sha and pins["guard"] != a.expect_guard_sha.lower()):
        print(json.dumps(dict(error="pin mismatch", pins=pins)))
        return 4
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(a.out_root) / stamp
    out.mkdir(parents=True, exist_ok=False)
    summary = dict(tool=Path(__file__).name, revision="r0", started_utc=now(), pid=os.getpid(), pins=pins, cases={})
    review = load_canonical("run_stage1_unassisted_review", RUNNER)   # inserts CANON on sys.path for its imports
    import unassisted_command_guard as guard
    import native_ui_facade_route as route
    import launch_ui_candidate as ui
    import ui_candidate_probe as probe
    import run_facade_ab_probe as close_mod
    import run_stage1_pacing_ab as pacing
    mods = dict(review=review, guard=guard, route=route, ui=ui, probe=probe, close=close_mod, pacing=pacing)
    summary["module_files"] = {k: str(Path(m.__file__).resolve()) for k, m in mods.items()}
    canon_ok = all(Path(f).resolve().parent == CANON.resolve() for f in summary["module_files"].values())
    summary["modules_are_canonical"] = canon_ok
    # Fixtures: the pinned 'hd' route references; each must classify as its intended state.
    refs, receipts = route.load_references("hd")
    fixtures = {name: Path(receipts[name]["path"]) for name in ("title", "fighter", "arm", "city")}
    fixture_states = {name: route.classify_native(refs[name], refs, "hd")["state"] for name in fixtures}
    summary["fixtures"] = dict(receipts=receipts, classified=fixture_states,
                               valid=fixture_states == dict(title="title", fighter="fighter", arm="arm", city="city"))
    if not (canon_ok and summary["fixtures"]["valid"]):
        summary["passed"] = False
    else:
        c1 = run_case("C1", out, mods, fixtures)
        c1["checks"] = dict(
            exit_0=c1["exit_code"] in (0, None), no_exception=c1["exception"] is None, no_errors=c1["proof_errors"] == [],
            port_closed=c1["port_closed"] is True, process_exit_0=c1["owned_process_exit"] == 0,
            route_city=c1["route_ok"] is True and c1["route_final"] == "city",
            route_gates_4=c1["route_gates"] == ["title-game-start:title", "fighter-mk2:fighter", "after-fighter:arm",
                                                 "city-hud:city"],
            samples_61=c1["observations"] == 61, focus_every_sample=c1["focus_samples_ok"] == 61,
            every_call_has_intent=c1["runtime_calls"] == c1["intents"] == c1["transport_receipts"],
            audit_clean=(c1["command_audit"] or {}).get("forbidden_or_malformed") == []
            and (c1["command_audit"] or {}).get("checked_records") == 2 * c1["runtime_calls"],
            route_inputs_only_in_route_phase=all(set(v) == {"native-menu-route"} for k, v in c1["commands_by_phase"].items()
                                                 if k.startswith("set_input")),
            launched_once=c1["fenced_launch_calls"] == 1, closed_once=c1["identity_calls"] == 1,
            no_tripwires=c1["tripwire_hits"] == [])
        c1["passed"] = all(c1["checks"].values())
        c2 = run_case("C2", out, mods, fixtures, focus_fail_second=7)
        c2["checks"] = dict(
            exit_1=c2["exit_code"] == 1,
            focus_error=any("lost keyboard focus" in e for e in (c2["proof_errors"] or [])),
            focus_rejected_sample=c2["focus_rejected"] is True, still_closed=c2["port_closed"] is True,
            process_exit_recorded=c2["owned_process_exit"] == 0, audit_clean=(c2["command_audit"] or {})
            .get("forbidden_or_malformed") == [], no_tripwires=c2["tripwire_hits"] == [])
        c2["passed"] = all(c2["checks"].values())
        c3 = run_case("C3", out, mods, fixtures, inject_savestate=True)
        c3["checks"] = dict(
            exit_1=c3["exit_code"] == 1,
            refused_before_send=any("refused before send: savestate" in e for e in (c3["proof_errors"] or [])),
            runtime_never_saw_savestate=c3["savestate_reached_runtime"] is False,
            no_savestate_intent=not any('"savestate"' in p.read_text(encoding="utf-8")
                                        for p in (Path(c3["evidence"]) / "command-intents").glob("*.json")),
            still_closed=c3["port_closed"] is True, audit_clean=(c3["command_audit"] or {})
            .get("forbidden_or_malformed") == [], no_tripwires=c3["tripwire_hits"] == [])
        c3["passed"] = all(c3["checks"].values())
        c4 = phase_scope_case(out, mods)
        summary["cases"] = dict(C1=c1, C2=c2, C3=c3, C4=c4)
        summary["passed"] = all(c["passed"] for c in summary["cases"].values())
    summary["ended_utc"] = now()
    path = out / "summary.json"
    with open(path, "x", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, default=str)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    print(json.dumps(dict(out=str(out), passed=summary["passed"], pins=pins,
                          cases={k: v.get("passed") for k, v in summary["cases"].items()},
                          fixtures_valid=summary["fixtures"]["valid"], modules_are_canonical=canon_ok)))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
