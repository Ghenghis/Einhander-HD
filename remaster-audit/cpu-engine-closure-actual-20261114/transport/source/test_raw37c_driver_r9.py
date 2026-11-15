"""Controls r9 = r8 fe9f5467 plus ONE fixture fix. The actual granted r8 run (23:47:56Z, log b8022ef9) crashed at
cleanup_fail_recorded with KeyError cleanup_holder: since driver r7 the run verifies the holder closure modules are
in sys.modules from their pinned files, and the r8 fake load_module never registered them, so the fake run aborted
before the holder existed. r9 models the closure with real temporary module files pinned in a patched
HOLDER_CLOSURE and registered by the fake load_module (the post-import check passes genuinely), adds a negative
case (closure file sha mismatch -> abort before Popen), and makes these checks report the abort reason instead
of crashing. Run: python -I -B test_raw37c_driver_r9.py raw37c_driver_r11.py <exclusive log>
r8 header (kept): Controls r8 = r7 b569ff68 plus r11 cases: owned create_time changes during the settle (nothing sent), the deadline
expires during a successful settle (nothing sent), and two rows hold the 4-tuple after the reply (abort with raw
unqualified only). Run: python -I -B test_raw37c_driver_r8.py raw37c_driver_r11.py <exclusive log>
r7 header (kept): Controls r7 = r6 010e6f2b adjusted to r10 ordering: NNN-raw.json (qualified:false) is written before the post
bracket; NNN-reply.json (qualified:true) only after it. Run: python -I -B test_raw37c_driver_r7.py raw37c_driver_r10.py <log>
r6 header (kept): Controls r6 = r5 cac25fef (written for withdrawn r8) adjusted to r9 one-shot semantics: the reply receipt now has
peer_before only and a separate NNN-post.json; added cases: the server row vanishes after the reply (still OK, reply
persisted), and a foreign pid holding the 4-tuple after the reply aborts AFTER the reply receipt is written.
Run: python -I -B test_raw37c_driver_r6.py raw37c_driver_r9.py <exclusive log>
r5 header (kept): Controls r5 = r4 4cb68281 plus psutil-like peer rows for the r8 settled-peer check: conns_with() now also yields
the ESTABLISHED server-side row of the fake socket (owned pid, optionally appearing late, foreign or duplicated),
and four r8 cases are added (late peer settles, never-visible peer is bounded, ambiguous and foreign refuse before
send). Run: python -I -B test_raw37c_driver_r5.py raw37c_driver_r8.py <exclusive log>
r4 header (kept): Controls r4 = r3 316a1e3e plus ONE fixture fix: the actual r3 run (23:18Z, log raw37c-controls-r3-2318.log 28ae6aa2)
aborted at reverify_ok with "private settings changed": the fixture wrote settings.toml with write_text(), which on
Windows writes CRLF, so its bytes did not hash to H(b"x = 1\n"). The fixture now uses write_bytes. Driver unchanged.
r3 header (kept): Controls r3 = r2 fd48acf1 byte-identical below, plus ONE change: argv[2] names an exclusive log that receives
stdout, stderr and any traceback. The r2 grant (CPU14, 23:16Z) ran under fa5 --no-window: CREATE_NO_WINDOW without
handle inheritance sent the output to a hidden console, so exit 1 was recorded without its cause.
Run: python -I -B test_raw37c_driver_r3.py raw37c_driver_r2.py <exclusive log path>"""
import sys as _sys
if len(_sys.argv) != 3:
    raise SystemExit("usage: test_raw37c_driver_r9.py <driver> <exclusive log>")
_LOG = open(_sys.argv[2], "x", encoding="utf-8", buffering=1)
_sys.stdout = _sys.stderr = _LOG
"""Pure controls r2 for raw37c_driver_r2.py (r1 controls 237b1b81 kept). Guard doubles model the REAL
schemas: check -> {action,exit:0,allowed:True,committed:...}; start -> {action,exit:0,allowed:None,committed:True}.
 (source only; NOT run). Temp files and doubles only: no game, no real
socket connection, no broker/GPU, no input. Run (when granted): python -I -B test_raw37c_driver_r2.py <raw37c_driver_r2.py>"""
import hashlib, importlib.util, json, os, socket, sys, tempfile, time, types
from pathlib import Path

spec = importlib.util.spec_from_file_location("drv", sys.argv[1])
drv = importlib.util.module_from_spec(spec); spec.loader.exec_module(drv)
fails, n = [], 0
H = lambda b: hashlib.sha256(b).hexdigest()


def check(name, cond):
    global n
    n += 1
    if not cond:
        fails.append(name)


def raises(name, fn, exc=drv.Abort):
    try:
        fn()
    except exc:
        check(name, True); return
    except Exception as e:  # noqa: BLE001
        check(f"{name} (wrong exception {type(e).__name__}: {e})", False); return
    check(f"{name} (no exception)", False)


C = types.SimpleNamespace
PID, CT = 4242, 1794697000.5


class Addr(tuple):
    ip = property(lambda s: s[0])
    port = property(lambda s: s[1])


def conns_with(listen_pids, peer_pids=(PID,), appear_after=0, vanish_after=None, post_pids=None):
    calls = [0]
    def f():
        calls[0] += 1
        rows = [C(laddr=Addr(("127.0.0.1", drv.PORT)), raddr=None, status="LISTEN", pid=p, family=2) for p in listen_pids]
        if vanish_after is not None and calls[0] > vanish_after:
            rows += [C(laddr=Addr(("127.0.0.1", drv.PORT)), raddr=Addr(("127.0.0.1", 50000)), status="TIME_WAIT",
                       pid=p, family=socket.AF_INET) for p in (post_pids or (0,))]
            return rows
        if calls[0] > appear_after:
            rows += [C(laddr=Addr(("127.0.0.1", drv.PORT)), raddr=Addr(("127.0.0.1", 50000)), status="ESTABLISHED",
                       pid=p, family=socket.AF_INET) for p in peer_pids]
        return rows
    return f


def select_ok(conns, server, client, owned_pid):
    return {"server": list(server), "client": list(client), "pid": owned_pid}


def select_foreign(conns, server, client, owned_pid):
    raise drv.Abort("connected debug TCP peer belongs to another process")


class FakeConn:
    def __init__(self, log, chunks, delay=0.0):
        self.log, self.chunks, self.delay = log, list(chunks), delay

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def getsockname(self): return ("127.0.0.1", 50000)
    def settimeout(self, t): self.log.append(("timeout", t))
    def sendall(self, b): self.log.append(("send", b))

    def recv(self, k):
        time.sleep(self.delay)
        return self.chunks.pop(0) if self.chunks else b""


def make_dbg(ev, log, chunks=(b'{"id":1,"ok":true}\n',), listen=(PID,), ctime=CT, select=select_ok, delay=0.0,
             peer_pids=(PID,), appear_after=0, settle_s=1.0, vanish_after=None, post_pids=None,
             budget=30.0, request_s=15.0):
    def connect(addr, timeout=None):
        log.append(("connect", timeout, (Path(ev) / "commands" / f"{len([x for x in log if x[0] == 'connect']) + 1:03d}-intent.json").is_file()))
        return FakeConn(log, chunks, delay)
    return drv.Debug(ev, drv.Budget(budget), (PID, CT), conns_with(listen, peer_pids, appear_after, vanish_after, post_pids), lambda pid: ctime, select,
                     settle_s=settle_s, settle_poll=0.01,
                     connect=connect, request_s=request_s)


with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    # (4)+allowlist: refusal before intent/connect; per-connection owned listener + audited peer before/after
    ev = t / "ev"; ev.mkdir(); log = []
    dbg = make_dbg(ev, log)
    raises("refuse_savestate", lambda: dbg("savestate", op="load", slot=0))
    raises("refuse_extra_arg", lambda: dbg("audio_stats", reset=1))
    raises("refuse_shot_outside", lambda: dbg("present_shot", path=str(t / "x.png")))
    check("no_intent_or_connect_on_refusal", log == [] and not any((ev / "commands").iterdir()))
    r = dbg("audio_stats")
    rep = json.loads((ev / "commands" / "001-reply.json").read_bytes())
    check("allowed_reply", r == {"id": 1, "ok": True} and rep["peer_before"]["pid"] == PID and
          (ev / "commands" / "001-post.json").is_file() and "peer_after" not in rep and rep["qualified"] is True and
          json.loads((ev / "commands" / "001-raw.json").read_bytes())["qualified"] is False)
    check("intent_before_connect", log[0][0] == "connect" and log[0][2] is True and log[0][1] <= 8.0)
    for name, kw in [("listener_foreign", dict(listen=(PID, 999))), ("listener_absent", dict(listen=())),
                     ("ctime_changed", dict(ctime=CT + 1))]:
        e2 = t / f"ev_{name}"; e2.mkdir(); l2 = []
        raises(name, lambda: make_dbg(e2, l2, **kw)("audio_stats"))
        check(f"{name}_no_connect", not any(x[0] == "connect" for x in l2))
    e3 = t / "ev_peer"; e3.mkdir(); l3 = []
    raises("peer_foreign", lambda: make_dbg(e3, l3, select=select_foreign)("audio_stats"))
    check("peer_foreign_nothing_sent", not any(x[0] == "send" for x in l3))
    # r8 settled-peer cases (same connected socket, no reconnect)
    e6 = t / "ev_late"; e6.mkdir(); l6 = []
    r6 = make_dbg(e6, l6, appear_after=3)("audio_stats")
    rp = json.loads((e6 / "commands" / "001-reply.json").read_bytes())
    check("late_peer_settles", r6 == {"id": 1, "ok": True} and rp["peer_before"]["settle_polls"] >= 3 and
          sum(1 for x in l6 if x[0] == "connect") == 1)
    e7 = t / "ev_never"; e7.mkdir(); l7 = []
    t7 = time.monotonic()
    raises("peer_never_visible_bounded", lambda: make_dbg(e7, l7, peer_pids=(), settle_s=0.3)("audio_stats"))
    check("peer_never_bounded_time_and_nothing_sent", time.monotonic() - t7 < 1.5 and not any(x[0] == "send" for x in l7))
    e8 = t / "ev_amb"; e8.mkdir(); l8 = []
    raises("peer_ambiguous_refused", lambda: make_dbg(e8, l8, peer_pids=(PID, PID))("audio_stats"))
    check("peer_ambiguous_nothing_sent", not any(x[0] == "send" for x in l8))
    e9 = t / "ev_foreign_row"; e9.mkdir(); l9 = []
    raises("peer_row_foreign_refused", lambda: make_dbg(e9, l9, peer_pids=(999,))("audio_stats"))
    check("peer_row_foreign_nothing_sent", not any(x[0] == "send" for x in l9))
    # r9 one-shot semantics: the server row vanishes after the reply (pid 0 TIME_WAIT) -> OK, post recorded
    e10 = t / "ev_closed"; e10.mkdir(); l10 = []
    r10 = make_dbg(e10, l10, vanish_after=2)("audio_stats")
    post = json.loads((e10 / "commands" / "001-post.json").read_bytes())
    check("post_reply_closed_ok", r10 == {"id": 1, "ok": True} and post["rows"] and post["rows"][0]["status"] == "TIME_WAIT")
    # foreign pid holding the 4-tuple after the reply -> abort, but the reply receipt was already persisted
    e11 = t / "ev_post_foreign"; e11.mkdir(); l11 = []
    raises("post_reply_foreign_aborts", lambda: make_dbg(e11, l11, vanish_after=2, post_pids=(999,))("audio_stats"))
    # r11 (1a): owned create_time changes during the settle -> pre-send recheck aborts, nothing sent
    e12 = t / "ev_ctime_settle"; e12.mkdir(); l12 = []
    d12 = make_dbg(e12, l12, appear_after=2)
    ct_calls = [0]
    def ct_flip(pid):
        ct_calls[0] += 1
        return CT if ct_calls[0] == 1 else CT + 1
    d12.ctime = ct_flip
    raises("ctime_change_during_settle_refused", lambda: d12("audio_stats"))
    check("ctime_change_nothing_sent", not any(x[0] == "send" for x in l12))
    # r11 (1b): deadline expires during a successful settle -> nothing sent
    e13 = t / "ev_deadline_settle"; e13.mkdir(); l13 = []
    d13 = make_dbg(e13, l13, request_s=0.15)
    inner = d13.conns
    def slow():
        time.sleep(0.1)
        return inner()
    d13.conns = slow
    raises("deadline_expired_before_send_refused", lambda: d13("audio_stats"))
    check("deadline_expired_nothing_sent", not any(x[0] == "send" for x in l13))
    # r11 (2): two rows hold the 4-tuple after the reply -> ambiguous abort, raw unqualified only
    e14 = t / "ev_post_amb"; e14.mkdir(); l14 = []
    raises("post_reply_ambiguous_aborts", lambda: make_dbg(e14, l14, vanish_after=2, post_pids=(0, 0))("audio_stats"))
    check("post_reply_ambiguous_no_qualified_reply", (e14 / "commands" / "001-raw.json").is_file() and
          not (e14 / "commands" / "001-reply.json").exists())
    raw11 = json.loads((e11 / "commands" / "001-raw.json").read_bytes())
    check("post_reply_foreign_raw_persisted_unqualified", raw11["qualified"] is False and raw11["bytes"] > 0 and
          not (e11 / "commands" / "001-reply.json").exists() and not (e11 / "commands" / "001-post.json").exists())
    # (5) slow drip: one byte per recv, never a newline -> bounded by the request deadline, timeout re-armed each recv
    e4 = t / "ev_drip"; e4.mkdir(); l4 = []
    t0 = time.monotonic()
    raises("slow_drip_bounded", lambda: make_dbg(e4, l4, chunks=[b"x"] * 1000, delay=0.05, request_s=0.6)("audio_stats"))
    tos = [x[1] for x in l4 if x[0] == "timeout"]
    check("slow_drip_time", time.monotonic() - t0 < 2.0)
    check("timeout_rearmed_decreasing", len(tos) >= 3 and all(a >= b for a, b in zip(tos, tos[1:])))
    e5 = t / "ev_budget"; e5.mkdir(); l5 = []
    raises("budget_exhausted", lambda: make_dbg(e5, l5, budget=0.0)("audio_stats"))
    check("budget_no_connect", not any(x[0] == "connect" for x in l5))

    # (2) inherited namespace cleared case-insensitively, explicit overlay, token never inherited
    env, dropped = drv.build_env({"PSXRECOMP_HD_TEXTURE_ROOT": "r", "psx_hle_scheduler": "", "psxrecomp_hd_emissive": "0"},
                                 base={"psxrecomp_skin_targets": "x", "Psx_Load_Slot": "0", "EINHANDER_SHARED_GPU_TOKEN": "t",
                                       "SDL_AUDIODRIVER": "y", "PATH": "p", "PSXRECOMP_HD_EMISSIVE": "1"})
    up = {k.upper(): v for k, v in env.items()}
    check("env_namespace_cleared", set(up) == {"PATH", "PSXRECOMP_HD_TEXTURE_ROOT", "PSXRECOMP_HD_EMISSIVE"})
    check("env_overlay_case_insensitive", up["PSXRECOMP_HD_EMISSIVE"] == "0" and len(env) == 3)
    check("env_dropped_names_only", "EINHANDER_SHARED_GPU_TOKEN" in dropped and "t" not in dropped)

    # (1) reverify: exact name+hash map, not count; settings bound to exe dir
    rt = t / "stage" / "runtime"; rt.mkdir(parents=True)
    exe = rt / "Einhander_Recompiled.exe"; exe.write_bytes(b"fake-37c")
    (rt / "settings.toml").write_bytes(b"x = 1\n")
    pack = t / "stage" / "pack" / "einhander-texture-replacements"; pack.mkdir(parents=True)
    (pack / "A.png").write_bytes(b"a"); (pack / "B.png").write_bytes(b"b"); (pack.parent / "Hashes.ini").write_bytes(b"i")
    lbf = t / "stage" / "game.toml"; lbf.write_bytes(b"g")
    st = {"spec": {"arguments": [str(exe)], "cwd": "C:/github/Einhander/windows-x64"},
          "launch_binding": {"small": {"game_toml": {"path": str(lbf), "sha256": H(b"g")}}},
          "settings": {"path": str(rt / "settings.toml"), "sha256": H(b"x = 1\n")},
          "pack": {"root": str(pack.parent), "png_pins": {"einhander-texture-replacements/A.png": H(b"a"),
                                                          "einhander-texture-replacements/B.png": H(b"b")},
                   "unpinned_nonpng": {"Hashes.ini": H(b"i")}}}
    stj = t / "staging.json"
    def put(s):
        stj.write_text(json.dumps(s)); return stj
    real_exe_sha = drv.EXE_SHA
    drv.EXE_SHA = H(b"fake-37c")
    try:
        check("reverify_ok", drv.reverify(put(st))["pack"]["png_pins"] == st["pack"]["png_pins"])
        (pack / "B.png").rename(pack / "C.png")                      # same COUNT, different name
        raises("reverify_png_renamed_same_count", lambda: drv.reverify(put(st)))
        (pack / "C.png").rename(pack / "B.png")
        (pack / "B.png").write_bytes(b"B")
        raises("reverify_png_changed", lambda: drv.reverify(put(st)))
        (pack / "B.png").write_bytes(b"b"); (pack.parent / "Hashes.ini").write_bytes(b"I")
        raises("reverify_nonpng_changed", lambda: drv.reverify(put(st)))
        (pack.parent / "Hashes.ini").write_bytes(b"i"); (rt / "settings.toml").write_bytes(b"x = 2\n")
        raises("reverify_settings_changed", lambda: drv.reverify(put(st)))
        (rt / "settings.toml").write_bytes(b"x = 1\n")
        raises("reverify_settings_path_not_exe_dir", lambda: drv.reverify(put(dict(st, settings=dict(st["settings"], path=str(t / "settings.toml"))))))
        lbf.write_bytes(b"G")
        raises("reverify_launch_source_changed", lambda: drv.reverify(put(st)))
        lbf.write_bytes(b"g")
        check("reverify_cwd_not_changed", drv.reverify(put(st))["spec"]["cwd"] == "C:/github/Einhander/windows-x64")
    finally:
        drv.EXE_SHA = real_exe_sha

    # (b) launch source chain bound once
    ls = t / "launch"; ls.mkdir()
    for nme, b in [("game.toml", b"g"), ("SCPH1001.BIN", b"bios"), ("Einhander (USA).bin", b"disc"), ("card1.mcd", b"c")]:
        (ls / nme).write_bytes(b)
    (ls / "Einhander (USA).cue").write_text('FILE "Einhander (USA).bin" BINARY\n  TRACK 01 MODE2/2352\n')
    sp = {"arguments": ["x.exe", "--game", str(ls / "game.toml"), "--disc", str(ls / "Einhander (USA).cue"),
                        "--bios", str(ls / "SCPH1001.BIN")]}
    lb = drv.launch_binding(sp, ls / "card1.mcd")
    check("launch_binding", lb["bins"][0]["sha256"] == H(b"disc") and lb["small"]["bios"]["sha256"] == H(b"bios")
          and set(lb["small"]) == {"game_toml", "bios", "cue", "card1"})
    (ls / "Einhander (USA).cue").write_text('FILE "missing.bin" BINARY\n')
    raises("launch_binding_missing_bin", lambda: drv.launch_binding(sp, ls / "card1.mcd"))
    raises("launch_binding_repeated_flag", lambda: drv.launch_binding({"arguments": sp["arguments"] + ["--bios", "y"]}, ls / "card1.mcd"))

    # pack copy at stage time
    src = t / "src"; (src / "einhander-texture-replacements").mkdir(parents=True)
    (src / "einhander-texture-replacements" / "A.png").write_bytes(b"a"); (src / "Hashes.ini").write_bytes(b"i")
    pins = {"einhander-texture-replacements/A.png": H(b"a")}
    res = drv.copy_pack(src, t / "d1", pins)
    check("pack_ok", res["png"] == pins and res["unpinned_nonpng"] == {"Hashes.ini": H(b"i")})
    (src / "einhander-texture-replacements" / "X.png").write_bytes(b"x")
    raises("pack_unpinned_png", lambda: drv.copy_pack(src, t / "d2", pins))

    # fence: the existing coordinator protocol, with no token in any receipt
    class Guard:
        def __init__(self, allowed=True, check_ok=True, start_ok=True):
            self.calls, self.allowed, self.check_ok, self.start_ok = [], allowed, check_ok, start_ok
        def current_permission(self, token):
            self.calls.append("perm"); return {"allowed": self.allowed, "owner": "claude-einhander", "errors": []}
        def broker_action(self, action, token, output, **f):
            self.calls.append((action, sorted(f)))
            if action == "check":
                return {"action": "check", "exit": 0, "allowed": self.check_ok, "committed": self.check_ok, "event_id": None}
            return {"action": "start", "exit": 0, "allowed": None, "committed": self.start_ok, "event_id": "ev_x"}
    raises("fence_no_token", lambda: drv.fence_before_launch(Guard(), "", t))
    raises("fence_not_allowed", lambda: drv.fence_before_launch(Guard(allowed=False), "tok", t))
    raises("fence_check_refused", lambda: drv.fence_before_launch(Guard(check_ok=False), "tok", t))
    g = Guard(); f = drv.fence_before_launch(g, "tok", t)
    check("fence_ok_no_token", "tok" not in json.dumps(f) and g.calls == ["perm", ("check", [])])
    raises("fence_start_refused", lambda: drv.fence_register_game(Guard(start_ok=False), "tok", t, PID, CT, ["x.exe"]))
    class WrongAction(Guard):
        def broker_action(self, action, token, output, **f):
            return {"action": "check", "exit": 0, "allowed": True, "committed": True}
    raises("fence_start_wrong_action", lambda: drv.fence_register_game(WrongAction(), "tok", t, PID, CT, ["x.exe"]))
    class BadExit(Guard):
        def broker_action(self, action, token, output, **f):
            return {"action": action, "exit": 1, "allowed": True, "committed": True}
    raises("fence_check_bad_exit", lambda: drv.fence_before_launch(BadExit(), "tok", t))
    raises("fence_start_bad_exit", lambda: drv.fence_register_game(BadExit(), "tok", t, PID, CT, ["x.exe"]))
    g2 = Guard(); reg = drv.fence_register_game(g2, "tok", t, PID, CT, ["x.exe", "--debug-port", "4376"])
    check("fence_start_real_schema_allowed_none_accepted", reg["allowed"] is None and reg["committed"] is True)
    check("fence_registers_actual_game", g2.calls == [("start", ["command", "created_utc", "pid"])] and
          reg["registered_pid"] == PID and "tok" not in json.dumps(reg))

    # gates: bounded poll, exact keys, owned screenshots, foreground before/after
    me = 4242
    ge = t / "g1"; ge.mkdir()
    raises("gate_not_foreground", lambda: drv.gate("G2", ["Right"], False, ge, me, drv.Budget(5), 1, fg=lambda: 1))
    t1 = time.monotonic()
    raises("gate_timeout_bounded", lambda: drv.gate("G2", ["Right"], False, ge, me, drv.Budget(5), 0.3, fg=lambda: me, poll=5.0))
    check("gate_poll_sleep_bounded", time.monotonic() - t1 < 1.5)
    ge2 = t / "g2"; ge2.mkdir(); shot = ge2 / "s.png"; shot.write_bytes(b"s")
    (ge2 / "gate-G1.done").write_text(json.dumps({"gate": "G1", "keys": ["F6"], "screenshots": [{"path": str(shot)}]}))
    gr = drv.gate("G1", ["F6"], True, ge2, me, drv.Budget(5), 1, fg=lambda: me)
    check("gate_ok", gr["screenshots"][0]["sha256"] == H(b"s"))
    ge3 = t / "g3"; ge3.mkdir()
    (ge3 / "gate-G1.done").write_text(json.dumps({"gate": "G1", "keys": ["F6"], "screenshots": []}))
    raises("gate_shot_required", lambda: drv.gate("G1", ["F6"], True, ge3, me, drv.Budget(5), 1, fg=lambda: me))

    # readiness: bounded wait for ready + opengl_ready + hd_ready
    seq = iter([{"ok": True, "out": {"ready": False, "opengl_ready": True, "hd_ready": False}},
                {"ok": True, "out": {"ready": True, "opengl_ready": True, "hd_ready": True}}])
    w = drv.wait_ready(lambda cmd: next(seq), drv.Budget(5), 3, poll=0.01)
    check("ready_after_poll", w["attempts"] == 2)
    raises("ready_never", lambda: drv.wait_ready(lambda cmd: {"ok": True, "out": {"ready": True, "hd_ready": False}},
                                                 drv.Budget(5), 0.2, poll=0.05))

    # (6) cleanup raising still yields exclusive ABORTED evidence; fence order perm -> check -> Popen -> start
    import psutil
    order = []
    class Holder:
        def __init__(self, popen):
            order.append("popen->holder"); self.pid = os.getpid(); self.create_time = psutil.Process(self.pid).create_time()
            self.facts = {}; self.process = popen
        @property
        def identity(self): return (self.pid, self.create_time)
        def cleanup(self, deadline_s=3.0): raise RuntimeError("cleanup boom (control)")
    fake_aud = t / "audited.py"; fake_aud.write_text("# fake")
    class G(Guard):
        def current_permission(self, token): order.append("perm"); return super().current_permission(token)
        def broker_action(self, action, token, output, **f): order.append(action); return super().broker_action(action, token, output, **f)
    saved = (drv.verify_pins, drv.reverify, drv.load_module, drv.listeners, drv.subprocess.Popen,
             drv.job_active_processes_self_inclusive, dict(drv.PINS), os.environ.get(drv.TOKEN_ENV))
    saved_closure = dict(drv.HOLDER_CLOSURE)
    fake_closure = {}
    for nm in saved_closure:                                   # r9: real temp files standing in for the closure
        fp = t / (nm + ".py"); fp.write_bytes(("# fake " + nm + "\n").encode())
        fake_closure[nm] = (fp, H(fp.read_bytes()))
    def fake_load(name, path, extra=None):
        if name == "owned_process_cleanup_r0":
            for nm, (fp, _) in fake_closure.items():
                sys.modules[nm] = C(__file__=str(fp))
        return mods[name]
    try:
        drv.verify_pins = lambda names: {}
        drv.reverify = lambda s: {"spec": {"arguments": [str(t / "staged.exe")], "cwd": str(t), "environment_overrides": {}}}
        drv.listeners = lambda port, conns: []
        drv.PINS["audited_r1"] = (fake_aud, H(b"# fake"))
        mods = {"owned_process_cleanup_r0": C(OwnedProcessHolder=Holder, audited=C(__file__=str(fake_aud), select_owned_tcp_peer=select_ok)),
                "shared_gpu_guard": G()}
        drv.HOLDER_CLOSURE.clear(); drv.HOLDER_CLOSURE.update(fake_closure)
        drv.load_module = fake_load
        drv.subprocess.Popen = lambda *a, **k: (order.append("Popen"), C(poll=lambda: None))[1]
        drv.job_active_processes_self_inclusive = lambda: None
        os.environ[drv.TOKEN_ENV] = "secret-token-control"
        (t / "staging-unused.json").write_text("{}")          # run() hashes it before the fence
        rc = drv.run(t / "staging-unused.json", t / "runev", 5, 1, 1)
        e = json.loads((t / "runev" / "raw37c-evidence.json").read_bytes())
        raw = (t / "runev" / "raw37c-evidence.json").read_text()
        check(f"cleanup_fail_recorded [abort={e.get('abort')}]", rc == 1 and e["verdict"] == "ABORTED" and
              (e.get("cleanup_holder") or {}).get("verdict") == "CLEANUP-FAIL")
        check("holder_closure_recorded", set((e.get("holder_closure") or {})) == set(fake_closure))
        check("abort_reason_kept", "not the staged 37c exe" in e.get("abort", ""))
        check("fence_order", order[:4] == ["perm", "check", "Popen", "popen->holder"] and "start" in order)
        check("token_never_in_evidence", "secret-token-control" not in raw)
        check("logs_captured", (t / "runev" / "game.stdout.log").is_file() and (t / "runev" / "game.stderr.log").is_file())
        raises("run_evidence_exclusive", lambda: drv.run(t / "x.json", t / "runev", 5, 1), FileExistsError)
        # r9 negative: a holder-closure file whose sha does not match its pin aborts BEFORE any Popen
        order.clear()
        nm0 = next(iter(fake_closure))
        drv.HOLDER_CLOSURE[nm0] = (fake_closure[nm0][0], "0" * 64)
        rc2 = drv.run(t / "staging-unused.json", t / "runev2", 5, 1, 1)
        e2 = json.loads((t / "runev2" / "raw37c-evidence.json").read_bytes())
        check(f"holder_closure_mismatch_aborts_before_popen [abort={e2.get('abort')}]",
              rc2 == 1 and "not pinned" in (e2.get("abort") or "") and "Popen" not in order and "cleanup_holder" not in e2)
    finally:
        (drv.verify_pins, drv.reverify, drv.load_module, drv.listeners, drv.subprocess.Popen,
         drv.job_active_processes_self_inclusive) = saved[:6]
        drv.PINS.clear(); drv.PINS.update(saved[6])
        drv.HOLDER_CLOSURE.clear(); drv.HOLDER_CLOSURE.update(saved_closure)
        for nm in fake_closure:
            sys.modules.pop(nm, None)
        if saved[7] is None:
            os.environ.pop(drv.TOKEN_ENV, None)
        else:
            os.environ[drv.TOKEN_ENV] = saved[7]
    src_text = Path(sys.argv[1]).read_text(encoding="utf-8")
    check("no_pass_verdict_in_source", '"PASS"' not in src_text)
    check("no_cwd_rewrite_in_source", 'spec["cwd"] =' not in src_text)
    raises("main_budget_cap", lambda: drv.main(["--run", "x.json", "--evidence", str(t / "e"), "--budget", "500"]), SystemExit)

print(json.dumps({"checks": n, "failures": fails, "result": "FAIL" if fails else "PASS"}))
sys.exit(1 if fails else 0)
