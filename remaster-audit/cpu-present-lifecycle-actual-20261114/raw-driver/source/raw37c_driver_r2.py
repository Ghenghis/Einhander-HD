"""raw37c_driver_r2.py - s67 W1 r2 (r0 fcd5dd1a and r1 48bf9e72 frozen, unchanged).
r2 vs r1 (root msg_667df9f8 / crash-check msg_042f15aa): (a) the broker START schema is the real one: guard
    cb767d1f returns allowed=first.get("allowed") and shared-gpu.mjs start returns {ok,event,...} with NO allowed
    field, so a successful start is allowed=None/committed=True. r2 requires action=="start", exit==0 and
    committed is True (r1 also required allowed is True, which aborts every real start). The CHECK still
    requires action=="check", exit==0 and allowed is True. The broker, tokens and grant policy are unchanged.
(b) Staging records the launch source chain once: game.toml, BIOS, disc .cue, every .bin the cue names (hashed
    ONCE at staging) and card1. --run re-hashes the small files (game.toml, BIOS, cue, card1); the BIN is not
    re-hashed per run. Adapter-dependent results remain unqualified without actual adapter evidence.
r1 notes follow. SOURCE ONLY, NOT RUN. Raw data only, never acceptance.

r1 fixes, per root msg_e0e58389:
 (1) Staging stores the exact pinned PNG map {relative path: sha256}. reverify() checks every staged PNG's name AND
     hash against that map (set equality) and every non-PNG file's hash. The pins are split accurately: 1699 from
     candidate.files and 2 from candidate.emissive_files. Both are sha-pinned in the candidate; emissive stays off
     (PSXRECOMP_HD_EMISSIVE=0).
 (2) Inherited environment: every key whose upper-cased name starts with PSX, EIN or SDL_ is dropped
     (case-insensitive; this includes PSXRECOMP_SKIN_*, HD, proof and telemetry controls and EINHANDER_SHARED_GPU_TOKEN).
     The reviewed spec overrides are then overlaid case-insensitively, minus the deleted keys. Dropped names are
     recorded; values never are.
 (3) Settings resolution is source-bound, not assumed. Staging pins the actual 37c main source d8abf287 and requires
     its exe-dir anchor `exe_dir_from_argv(argv[0]) / "settings.toml"` (GetModuleFileNameW on Windows). argv[0] is
     the absolute staged exe. cwd is NOT changed (precedent windows-x64, recorded for any relative outputs). The
     private settings sha is checked before launch and recorded after exit; logs are scanned for the private path
     as a config marker (recorded, not assumed). card2 is disabled (enable2 = false) and its private path stays
     absent.
 (4) Every debug connection verifies the owned endpoint. Before connecting, the 4376 listener set must be exactly
     the owned pid with an unchanged create_time. After connecting and after the reply, support audited r1
     select_owned_tcp_peer (9f455093) must show this socket's server peer is the owned pid. No foreign-pid or
     network edits are made.
 (5) The recv timeout is recomputed from the remaining request and global budget on every recv. Gate poll sleeps
     are bounded by the remaining time.
 (6) If holder.cleanup() raises, the failure is recorded as cleanup FAIL, and the exclusive evidence is still
     written.
 Also: game stdout/stderr go to private files under <EV> (hash-recorded), so an adapter proof can bind the same
 image and log. G1 waits, bounded, for a skin_material reply with ready, opengl_ready and hd_ready all true. Title
 screen is NOT proven by this; the G1 operator screenshot is the only visual evidence.
Modes: --stage (CPU staging grant) / --run (GPU+game grant; Job child of normal wrapper c1fc81d4). The operator does
ALL UI through CUA. This driver sends no input and does no capture or close. Verdicts: RAW-COLLECTED or ABORTED.
"""
import argparse, ctypes, hashlib, importlib.util, json, math, os, re, shutil, socket, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path

GH = Path("C:/github/Einhander")
HERE = Path(__file__).resolve().parent
N = GH / "remaster-audit/runtime-review/gpu-texture-remix-20261114"
UI = GH / ".claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui"
SUP = GH / ".claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support/adapter-binding"
PRECEDENT = GH / "remaster-audit/dev-center-evidence/stage1-completion-20261112/v68-unassisted-r1/hd-on_rewind-off/candidate.json"
PINS = {
    "pacing_own_cache": (N / "pacing-own-cache.py", "a6e25f8330c4a43846d1b7882232cc019b0a240161420388349e25b052caa4d7"),
    "precedent_candidate": (PRECEDENT, "261dc3d2ab2675dce8d99e0f14bd6af8eb2e0d245346985b755a78e9204007aa"),
    "runtime_receipt": (HERE / "p1-37c-runtime.json", "1eafad2a2e359318164766d3dccf75d767b60a83da4315e2607c055e56e6fa40"),
    "ui_live_check_plan": (UI / "proposals/p1-player-color/build/LIVE-CHECK-PLAN-p1-v69-2240.md",
                           "d0bb13e577b2b87aa2943e8e406026def70cd931478dfbb3562d6db8d8e8032c"),
    "owner_build_receipt": (UI / "proposals/p1-player-color/build/BUILD-RECEIPT-p1-v69-2240.md",
                            "97c1da1f6bca8061a255f9679a160d5c4f93edba39ebdd3c797acf2dceb1a821"),
    "holder": (SUP / "owned_process_cleanup_r0.py", "8aff5a5a44a1bdc63e3e65731366f10d40a5e160d8b7e77fb99d97199ea88d84"),
    "audited_r1": (SUP / "owned_gl_adapter_observation_audited_r1.py",
                   "9f4550930ee5a980b89c62b00c6dcea966ccf10ff4f93036d8c5726993723b9c"),
    "p1_main_source": (UI / "builds/p1-v69-2240/src/main.cpp",
                       "d8abf287ee313e15b8dbe01837b1a217ef13f57d290e51d2d47947671c82e144"),
    "gpu_guard": (GH / "tools/coordination/shared_gpu_guard.py",
                  "cb767d1f5cf4c1795eb46d369a558bdfedf33c9e51b529123893c53c47685ac7"),
}
TOKEN_ENV = "EINHANDER_SHARED_GPU_TOKEN"   # read from the driver's own environment; never recorded, never given to the game
SETTINGS_ANCHOR = 'exe_dir_from_argv(argv[0]) / "settings.toml"'
EXE_SHA = "37c137e8af8c53d141d53623f9dafa8ce59555cc6a365152098fa49f1be4d9cc"
LEG = "hd-on_rewind-off"
PORT = 4376
DELETE_ENV = ("PSX_LOAD_SLOT", "PSX_HLE_SCHEDULER")
INHERIT_DROP_PREFIXES = ("PSX", "EIN", "SDL_")
ALLOW = {"skin_material": frozenset(), "audio_stats": frozenset(), "present_shot": frozenset({"path"}),
         "present_shot_seq": frozenset()}
REPLY_CAP = 8 * 2 ** 20
GATES = [("G1", ["F6"], True), ("G2", ["Right", "Right", "Enter"], False), ("G3a", ["F6"], True),
         ("G3b", ["Esc"], False), ("END", ["Alt+F4"], False)]
NOT_RUN = {"L5": "held F6: no supported CUA hold API", "L6": "held steering: no supported CUA hold API",
           "L7": "held fire: no supported CUA hold API", "L8": "follow-up profile", "L9": "follow-up profile",
           "L10": "needs a second launch", "L11": "follow-up profile (quit while open)"}


class Abort(Exception):
    pass


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def utc():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() * 1000) % 1000:03d}Z"


def write_x(path, obj):
    with open(path, "xb") as f:
        f.write((json.dumps(obj, indent=2, default=str) + "\n").encode("utf-8"))
        f.flush()
        os.fsync(f.fileno())


def verify_pins(names):
    got = {}
    for n in names:
        p, want = PINS[n]
        h = sha(p)
        if h != want:
            raise Abort(f"pin {n} {p} is {h}, want {want}")
        got[n] = {"path": str(p), "sha256": h}
    return got


def inside(child, parent):
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def load_module(name, path, extra_path=None):
    if extra_path:
        sys.path.insert(0, str(extra_path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Budget:
    def __init__(self, seconds):
        self.end = time.monotonic() + seconds

    def left(self):
        return self.end - time.monotonic()

    def need(self, what):
        left = self.left()
        if left <= 0:
            raise Abort(f"global budget exhausted at {what}")
        return left


# ---------------------------------------------------------------- staging (CPU grant)
def copy_pack(src, dst, pins):
    """pins {relative posix path: sha256} for every PNG. Returns {png: {rel: sha}, unpinned_nonpng: {rel: sha}}."""
    png, unpinned, bad = {}, {}, []
    for p in sorted(Path(src).rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(src).as_posix()
        out = Path(dst) / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, out)
        h = sha(out)
        if rel.lower().endswith(".png"):
            if pins.get(rel) != h:
                bad.append(rel)
            png[rel] = h
        else:
            unpinned[rel] = h
    missing = sorted(set(pins) - set(png))
    if bad or missing:
        raise Abort(f"pack verify failed: {len(bad)} unpinned/mismatched PNG (first {bad[:5]}), "
                    f"{len(missing)} pinned missing (first {missing[:5]})")
    return {"png": png, "unpinned_nonpng": unpinned}


def set_setting(text, name, value, raw=False):
    text, n = re.subn(r"(?m)^" + name + r"\s*=.*$", name + " = " + (value if raw else json.dumps(value)), text)
    if n != 1:
        raise Abort(f"ambiguous setting {name}")
    return text


def arg_value(args, flag):
    if args.count(flag) != 1:
        raise Abort(f"launch argument {flag} missing or repeated")
    return Path(args[args.index(flag) + 1])


def launch_binding(spec, card1):
    """Hash the launch source chain once: game.toml, BIOS, disc cue, each .bin named by the cue, card1."""
    args = spec["arguments"]
    game, bios, cue = arg_value(args, "--game"), arg_value(args, "--bios"), arg_value(args, "--disc")
    bins = []
    for line in cue.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r'\s*FILE\s+"([^"]+)"', line, re.I)
        if m:
            b = cue.parent / m.group(1)
            if not b.is_file():
                raise Abort(f"cue names a missing file: {b}")
            bins.append({"path": str(b), "sha256": sha(b), "bytes": b.stat().st_size})
    if not bins:
        raise Abort("cue names no data file")
    small = {"game_toml": game, "bios": bios, "cue": cue, "card1": Path(card1)}
    return {"small": {k: {"path": str(p), "sha256": sha(p)} for k, p in small.items()}, "bins": bins,
            "note": "BIN hashed once at staging; --run re-hashes only the small files"}


def stage(batch):
    pins = verify_pins(["pacing_own_cache", "precedent_candidate", "runtime_receipt", "ui_live_check_plan",
                        "owner_build_receipt", "p1_main_source"])
    src_lines = PINS["p1_main_source"][0].read_text(encoding="utf-8", errors="replace").splitlines()
    anchor_lines = [i + 1 for i, line in enumerate(src_lines) if SETTINGS_ANCHOR in line]
    if not anchor_lines:
        raise Abort("37c main source has no exe-dir settings anchor")
    t0 = time.monotonic()
    pacing = load_module("pacing_own_cache", PINS["pacing_own_cache"][0], N)
    ns = argparse.Namespace(batch=batch, runtime=PINS["runtime_receipt"][0], candidate=PRECEDENT, supersampling=2,
                            gpu_queries=0, world_sampling=0, native_menus=False, guest_frames=0, emissive=0)
    report = pacing.prepare(LEG, ns)                      # prepare() only: never run()/launch()
    d = Path(report["evidence"])
    spec = report["launches"]["candidate"]
    exe = Path(spec["arguments"][0])
    if not exe.is_absolute() or sha(exe) != EXE_SHA or spec["executable_sha256"] != EXE_SHA:
        raise Abort("staged executable is not an absolute 37c137e8")
    if any((exe.parent / "cache").iterdir()):
        raise Abort("own cache is not empty")
    env = spec["environment_overrides"]
    src = Path(env["PSXRECOMP_HD_TEXTURE_ROOT"])
    rel = lambda row: Path(row["composed_path"]).relative_to(src).as_posix()
    files = {rel(r): r["sha256"] for r in report["files"]}
    emissive = {rel(r): r["sha256"] for r in report.get("emissive_files", [])}
    if set(files) & set(emissive):
        raise Abort("files and emissive pins overlap")
    pack = copy_pack(src, d / "pack", {**files, **emissive})
    deleted = {k: any(e.upper() == k for e in env) for k in DELETE_ENV}
    for k in [e for e in env if e.upper() in DELETE_ENV]:
        env.pop(k)
    env["PSXRECOMP_HD_TEXTURE_ROOT"] = str(d / "pack")
    if env.get("PSXRECOMP_HD_PROOF_CONTROL", "") != "" or (d / "replacement-control.txt").exists():
        raise Abort("HD state not owned: a replacement control is present")
    if env.get("PSXRECOMP_HD_EMISSIVE") != "0":
        raise Abort("emissive must stay off")
    settings_path = exe.parent / "settings.toml"
    text = settings_path.read_text(encoding="utf-8")
    text = set_setting(text, "hd_texture_root", (d / "pack").as_posix())
    text = set_setting(text, "enable2", "false", raw=True)
    settings_path.write_text(text, encoding="utf-8")
    cards = {}
    for name in ("card1", "card2"):
        m = re.search(r"(?m)^" + name + r"\s*=\s*\"(.*)\"\s*$", text)
        if not m or not inside(m.group(1), d / "state"):
            raise Abort(f"{name} path is not private")
        cards[name] = {"path": m.group(1), "exists": Path(m.group(1)).exists()}
    if cards["card2"]["exists"]:
        raise Abort("card2 unexpectedly present")
    cards["enable2"] = False
    if not cards["card1"]["exists"]:
        raise Abort("private card1 seed missing")
    binding = launch_binding(spec, cards["card1"]["path"])
    spec["settings_sha256"] = sha(settings_path)
    rec = {"schema": "s67-raw37c-staging-r2", "launch_binding": binding, "batch": batch, "directory": str(d), "pins": pins, "spec": spec,
           "executable_sha256": EXE_SHA, "cwd": {"value": spec["cwd"], "changed": False,
           "note": "precedent cwd kept; recorded for any relative outputs (present_shot uses an absolute path)"},
           "settings": {"path": str(settings_path), "sha256": spec["settings_sha256"],
                        "source_binding": {"file": str(PINS["p1_main_source"][0]), "sha256": PINS["p1_main_source"][1],
                                           "anchor": SETTINGS_ANCHOR, "lines": anchor_lines},
                        "argv0_absolute_staged_exe": str(exe)},
           "own_cache": {"path": str(exe.parent / "cache"), "empty_at_stage": True,
                         "note": "cold cache: startup compile load expected and recorded at run; no v68 cache"},
           "pack": {"root": str(d / "pack"), "source_root": str(src), "png_pins": pack["png"],
                    "pinned_from_candidate_files": len(files),
                    "pinned_from_candidate_emissive_files": sorted(emissive),
                    "unpinned_nonpng": pack["unpinned_nonpng"],
                    "note": "every PNG sha-pinned by the candidate (files + emissive_files); emissive OFF; non-PNG "
                            "files are not pinned by the candidate and are hash-recorded only; no immutable claim"},
           "env_deleted": deleted, "hd_state": "on from boot; no replacement-control; PROOF_CONTROL empty",
           "cards": cards, "stage_seconds": round(time.monotonic() - t0, 3), "at_utc": utc()}
    write_x(d / "raw37c-staging.json", rec)
    return d / "raw37c-staging.json"


# ---------------------------------------------------------------- run (GPU+game grant)
def reverify(staging):
    st = json.loads(Path(staging).read_bytes())
    spec = st["spec"]
    exe = Path(spec["arguments"][0])
    if not exe.is_absolute() or sha(exe) != EXE_SHA:
        raise Abort("staged exe changed")
    if Path(st["settings"]["path"]).resolve() != (exe.parent / "settings.toml").resolve():
        raise Abort("recorded settings path is not the staged exe-dir settings")
    if sha(exe.parent / "settings.toml") != st["settings"]["sha256"]:
        raise Abort("private settings changed")
    for k, v in st["launch_binding"]["small"].items():
        if sha(v["path"]) != v["sha256"]:
            raise Abort(f"launch source {k} changed")
    root = Path(st["pack"]["root"])
    seen = {p.relative_to(root).as_posix(): p for p in root.rglob("*") if p.is_file()}
    want = {**st["pack"]["png_pins"], **st["pack"]["unpinned_nonpng"]}
    if set(seen) != set(want):
        raise Abort(f"private pack file set changed: +{sorted(set(seen) - set(want))[:5]} "
                    f"-{sorted(set(want) - set(seen))[:5]}")
    for r, h in want.items():
        if sha(seen[r]) != h:
            raise Abort(f"pack file changed: {r}")
    return st


def build_env(overrides, base=None):
    base = os.environ if base is None else base
    dropped = sorted(k for k in base if k.upper().startswith(INHERIT_DROP_PREFIXES))
    env = {k: v for k, v in base.items() if not k.upper().startswith(INHERIT_DROP_PREFIXES)}
    for k, v in overrides.items():
        if k.upper() in DELETE_ENV:
            continue
        for e in [e for e in env if e.upper() == k.upper()]:
            env.pop(e)
        env[k] = v
    if any(k.upper() in DELETE_ENV for k in env):
        raise Abort("deleted env key survived")
    return env, dropped


def listeners(port, conns):
    return [c.pid for c in conns() if c.laddr and c.laddr.port == port and c.status == "LISTEN"]


def foreground_pid():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    hwnd = user32.GetForegroundWindow()
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def job_active_processes_self_inclusive():
    """Accounting of this driver's own Job (NULL handle). Includes the driver. A fact only; never fed to the holder."""
    class ACC(ctypes.Structure):
        _fields_ = [("TotalUserTime", ctypes.c_longlong), ("TotalKernelTime", ctypes.c_longlong),
                    ("ThisPeriodTotalUserTime", ctypes.c_longlong), ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                    ("TotalPageFaultCount", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
                    ("ActiveProcesses", wintypes.DWORD), ("TotalTerminatedProcesses", wintypes.DWORD)]
    a = ACC()
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    if not k32.QueryInformationJobObject(None, 1, ctypes.byref(a), ctypes.sizeof(a), None):
        return None
    return int(a.ActiveProcesses)


class Debug:
    """Allowlisted client. owner=(pid, create_time). conns() -> psutil-like connections; ctime(pid) -> create_time;
    select(conns, server=, client=, owned_pid=) -> audited peer record or raises."""

    def __init__(self, ev, budget, owner, conns, ctime, select, port=PORT, connect=None, request_s=15.0):
        self.ev, self.budget, self.owner, self.port, self.n = Path(ev), budget, owner, port, 0
        self.conns, self.ctime, self.select = conns, ctime, select
        self.connect = connect or socket.create_connection
        self.request_s = request_s
        (self.ev / "commands").mkdir(exist_ok=True)

    def _owned_listener(self, what):
        pid, ct = self.owner
        if self.ctime(pid) != ct:
            raise Abort(f"{what}: owned identity changed")
        owners = set(listeners(self.port, self.conns))
        if owners != {pid}:
            raise Abort(f"{what}: {self.port} listener set {sorted(owners)} is not exactly the owned pid")

    def __call__(self, cmd, **kw):
        if cmd not in ALLOW or not set(kw) <= ALLOW[cmd]:
            raise Abort(f"refused before send: {cmd} {sorted(kw)}")
        if cmd == "present_shot" and not inside(kw["path"], self.ev):
            raise Abort("refused before send: present_shot path outside evidence")
        self.n += 1
        req = dict(kw, cmd=cmd, id=self.n)
        write_x(self.ev / "commands" / f"{self.n:03d}-intent.json", {"at_utc": utc(), "port": self.port, "request": req})
        end = time.monotonic() + min(self.request_s, self.budget.need(cmd))
        self._owned_listener(cmd)
        with self.connect(("127.0.0.1", self.port), timeout=max(0.05, min(8.0, end - time.monotonic()))) as c:
            client = tuple(c.getsockname()[:2])
            peer_before = self.select(self.conns(), server=("127.0.0.1", self.port), client=client,
                                      owned_pid=self.owner[0])
            c.sendall(json.dumps(req).encode("utf-8") + b"\n")
            buf = bytearray()
            while b"\n" not in buf:
                left = min(end - time.monotonic(), self.budget.need(cmd))
                if left <= 0:
                    raise Abort(f"{cmd}: request deadline passed during recv")
                c.settimeout(max(0.05, left))
                b = c.recv(65536)
                if not b:
                    raise Abort(f"{cmd}: connection closed without reply")
                buf.extend(b)
                if len(buf) > REPLY_CAP:
                    raise Abort(f"{cmd}: reply exceeded cap")
            peer_after = self.select(self.conns(), server=("127.0.0.1", self.port), client=client,
                                     owned_pid=self.owner[0])
        reply = json.loads(buf.split(b"\n", 1)[0])
        write_x(self.ev / "commands" / f"{self.n:03d}-reply.json",
                {"at_utc": utc(), "reply": reply, "peer_before": peer_before, "peer_after": peer_after})
        return reply


def gate(name, keys, shot, ev, owned_pid, budget, timeout, fg=foreground_pid, poll=0.25):
    if fg() != owned_pid:
        raise Abort(f"{name}: owned game is not foreground before gate")
    ready, done = Path(ev) / f"gate-{name}.ready", Path(ev) / f"gate-{name}.done"
    write_x(ready, {"gate": name, "expect_keys": keys, "screenshot_required": shot, "at_utc": utc(),
                    "note": "operator: supported CUA keypress only; no hold; App.getScreenshot of the owned window"})
    end = time.monotonic() + min(timeout, budget.need(name))
    while not done.exists():
        left = min(end - time.monotonic(), budget.left())
        if left <= 0:
            raise Abort(f"{name}: operator gate timed out")
        time.sleep(min(poll, left))
    d = json.loads(done.read_bytes())
    if d.get("gate") != name or d.get("keys") != keys:
        raise Abort(f"{name}: done receipt keys {d.get('keys')} != expected {keys}")
    shots = []
    for s in d.get("screenshots", []):
        if not inside(s["path"], ev) or not Path(s["path"]).is_file():
            raise Abort(f"{name}: screenshot missing or outside evidence")
        shots.append(dict(s, sha256=sha(s["path"])))
    if shot and not shots:
        raise Abort(f"{name}: required screenshot not recorded")
    after = None
    if name != "END":
        after = fg()
        if after != owned_pid:
            raise Abort(f"{name}: owned game lost foreground during gate")
    return {"gate": name, "done": d, "screenshots": shots, "done_sha256": sha(done), "fg_after": after}


def wait_ready(dbg, budget, limit_s, poll=1.0):
    """Bounded poll of skin_material until ready, opengl_ready and hd_ready are all true. Title is not proven."""
    end = time.monotonic() + min(limit_s, budget.need("ready"))
    tries = []
    while True:
        r = dbg("skin_material")
        out = r.get("out", r) if isinstance(r, dict) else {}
        flags = {k: out.get(k) for k in ("ready", "opengl_ready", "hd_ready")}
        tries.append(flags)
        if all(v is True for v in flags.values()):
            return {"attempts": len(tries), "flags": flags}
        left = min(end - time.monotonic(), budget.left())
        if left <= 0:
            raise Abort(f"skin_material never reported ready/opengl_ready/hd_ready: last {flags}")
        time.sleep(min(poll, left))


def audio_and_skin(dbg, tag, out):
    out[tag] = {"audio_stats": dbg("audio_stats"), "skin_material": dbg("skin_material"), "at_utc": utc()}


def fence_before_launch(guard, token, ev):
    """Existing coordinator fence (as run_stage1_unassisted_review uses it): current permission, then broker check.
    Private broker args are transient (guard cb767d1f TemporaryDirectory); the token is never recorded."""
    if not token:
        raise Abort(f"{TOKEN_ENV} absent: no current GPU grant for this driver")
    perm = guard.current_permission(token)
    if not isinstance(perm, dict) or perm.get("allowed") is not True:
        raise Abort(f"shared GPU permission not allowed: {(perm or {}).get('errors')}")
    check = guard.broker_action("check", token, ev)
    if check.get("action") != "check" or check.get("exit") != 0 or check.get("allowed") is not True:
        raise Abort("shared GPU broker check not allowed")
    return {"permission": {"allowed": True, "owner": perm.get("owner")}, "check": check}


def fence_register_game(guard, token, ev, pid, create_time, cmdline):
    """Register the ACTUAL game pid as soon as Popen exists, before any debug collection (same fields as the
    existing runner's start: pid, command, created_utc). A refusal aborts and the holder cleans up."""
    created = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(create_time)) + f".{int(create_time * 1e6) % 1000000:06d}+00:00"
    start = guard.broker_action("start", token, ev, pid=pid, command=" ".join(cmdline), created_utc=created)
    # real start schema: {action:"start", exit:0, allowed:None, committed:True, event_id:...} (no allowed field)
    if start.get("action") != "start" or start.get("exit") != 0 or start.get("committed") is not True:
        raise Abort("shared GPU broker start (game registration) not committed")
    return dict(start, registered_pid=pid, registered_create_time=create_time,
                note="grant never implicitly released; coordinator verifies absence before explicit release")


def run(staging, ev, budget_s, gate_timeout, ready_s=90.0):
    import psutil
    budget = Budget(budget_s)
    ev = Path(ev)
    ev.mkdir(parents=True, exist_ok=False)
    rec = {"schema": "s67-raw37c-evidence-r2", "verdict": "ABORTED", "not_run": NOT_RUN, "steps": {},
           "claims": "raw observations only; no acceptance, PCM, listening, pacing or performance claim; title not "
                     "proven", "started_utc": utc()}
    holder, logs = None, []
    try:
        rec["pins"] = verify_pins(["holder", "audited_r1", "ui_live_check_plan", "owner_build_receipt", "gpu_guard"])
        st = reverify(staging)
        rec["staging"] = {"path": str(staging), "sha256": sha(staging)}
        spec = st["spec"]
        conns = lambda: psutil.net_connections(kind="tcp")
        if listeners(PORT, conns):
            raise Abort(f"port {PORT} already has a listener before launch")
        hmod = load_module("owned_process_cleanup_r0", PINS["holder"][0], SUP)
        audited = hmod.audited
        if sha(audited.__file__) != PINS["audited_r1"][1]:
            raise Abort("holder imported a different audited module")
        env, dropped = build_env(spec["environment_overrides"])
        rec["env"] = {"inherited_dropped_names": dropped, "overrides_applied": sorted(spec["environment_overrides"]),
                      "deleted": list(DELETE_ENV)}
        guard = load_module("shared_gpu_guard", PINS["gpu_guard"][0])
        token = os.environ.get(TOKEN_ENV, "")
        rec["fence"] = {"before_launch": fence_before_launch(guard, token, ev)}
        out_f = open(ev / "game.stdout.log", "xb")
        err_f = open(ev / "game.stderr.log", "xb")
        logs = [out_f, err_f]
        t_launch = time.monotonic()
        holder = hmod.OwnedProcessHolder(subprocess.Popen(spec["arguments"], cwd=spec["cwd"], env=env,
                                                          stdout=out_f, stderr=err_f))
        p = psutil.Process(holder.pid)
        rec["fence"]["game_registration"] = fence_register_game(guard, token, ev, holder.pid, holder.create_time,
                                                                p.cmdline())
        token = None
        rec["steps"]["S0"] = {"pid": holder.pid, "create_time": holder.create_time, "exe": p.exe(),
                              "exe_sha256": sha(p.exe()), "cmdline": p.cmdline(), "cwd": p.cwd(), "nice": p.nice(),
                              "cpu_affinity": p.cpu_affinity(), "at_utc": utc()}
        if Path(p.exe()).resolve() != Path(spec["arguments"][0]).resolve() or rec["steps"]["S0"]["exe_sha256"] != EXE_SHA:
            raise Abort("launched image is not the staged 37c exe")
        while True:
            owners = listeners(PORT, conns)
            if owners and set(owners) != {holder.pid}:
                raise Abort(f"port {PORT} listener is not the owned game: {owners}")
            if owners:
                break
            if holder.process.poll() is not None:
                raise Abort("game exited before its debug listener appeared")
            time.sleep(min(0.25, max(0.0, budget.need("listener"))))
        rec["steps"]["S0"]["listener_seconds_cold_cache"] = round(time.monotonic() - t_launch, 3)
        dbg = Debug(ev, budget, holder.identity, conns, lambda pid: psutil.Process(pid).create_time(),
                    audited.select_owned_tcp_peer)
        rec["steps"]["ready"] = wait_ready(dbg, budget, ready_s)
        rec["steps"]["ready"]["seconds_from_launch"] = round(time.monotonic() - t_launch, 3)
        audio_and_skin(dbg, "A0", rec["steps"])
        for name, keys, shot in GATES:
            rec["steps"][name] = gate(name, keys, shot, ev, holder.pid, budget, gate_timeout)
            if name == "G2":
                audio_and_skin(dbg, "A1", rec["steps"])
                seq0 = dbg("present_shot_seq")
                rec["steps"]["A1"]["present_shot"] = dbg("present_shot", path=str(ev / "present-A1.png"))
                seqs = [seq0]
                for _ in range(40):
                    seqs.append(dbg("present_shot_seq"))
                    if seqs[-1].get("seq") != seq0.get("seq"):
                        break
                    time.sleep(min(0.05, max(0.0, budget.need("present_shot_seq"))))
                rec["steps"]["A1"]["present_shot_seq"] = seqs
            if name == "G3b":
                audio_and_skin(dbg, "A2", rec["steps"])
        try:
            rc = holder.process.wait(timeout=max(0.1, min(15.0, budget.need("exit"))))
        except subprocess.TimeoutExpired:
            raise Abort("game did not exit after operator Alt+F4")
        rec["steps"]["exit"] = {"returncode": rc, "at_utc": utc()}
        rec["verdict"] = "RAW-COLLECTED"
    except Abort as e:
        rec["abort"] = str(e)
    except Exception as e:  # noqa: BLE001 - recorded, verdict stays ABORTED
        rec["abort"] = f"{type(e).__name__}: {e}"
    finally:
        if holder is not None:
            try:
                rec["cleanup_holder"] = holder.cleanup(deadline_s=5.0)
            except Exception as e:  # noqa: BLE001 - cleanup FAIL recorded; evidence still written
                rec["cleanup_holder"] = {"verdict": "CLEANUP-FAIL", "error": f"{type(e).__name__}: {e}",
                                         "identity_absent": False, "tree_absent": False}
                rec["verdict"] = "ABORTED"
            rec["cleanup_holder_facts"] = getattr(holder, "facts", None)
        for f in logs:
            try:
                f.close()
            except Exception:  # noqa: BLE001
                pass
        rec["logs"] = {n: (sha(ev / n) if (ev / n).is_file() else None) for n in ("game.stdout.log", "game.stderr.log")}
        try:  # config marker: does any captured log line name the private staged dir? recorded, never assumed
            st_dir = json.loads(Path(rec["staging"]["path"]).read_bytes())["directory"] if "staging" in rec else None
            text = "".join((ev / n).read_text(encoding="utf-8", errors="replace") for n in rec["logs"] if rec["logs"][n])
            norm = text.replace("\\", "/").lower()
            rec["config_marker"] = {"private_dir_in_logs": bool(st_dir) and st_dir.replace("\\", "/").lower() in norm}
        except Exception as e:  # noqa: BLE001
            rec["config_marker"] = {"error": f"{type(e).__name__}"}
        try:
            st_path = Path(rec.get("staging", {}).get("path", ""))
            sp = Path(json.loads(st_path.read_bytes())["settings"]["path"]) if st_path.is_file() else None
            rec["settings_sha256_after"] = sha(sp) if sp and sp.is_file() else None
        except Exception as e:  # noqa: BLE001
            rec["settings_sha256_after"] = f"unreadable: {type(e).__name__}"
        try:
            rec["job_active_processes_self_inclusive"] = job_active_processes_self_inclusive()
        except Exception as e:  # noqa: BLE001
            rec["job_active_processes_self_inclusive"] = f"error: {type(e).__name__}"
        rec["cleanup_qualification"] = ("join required: holder identity_absent here AND the wrapper's Job-empty/"
                                        "tree-absent receipt for this pid/ctime; holder tree_absent is False inside "
                                        "the Job by design")
        rec["ended_utc"] = utc()
        write_x(ev / "raw37c-evidence.json", rec)
    return 0 if rec["verdict"] == "RAW-COLLECTED" else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument("--stage", metavar="BATCH")
    m.add_argument("--run", metavar="STAGING_JSON")
    ap.add_argument("--evidence")
    ap.add_argument("--budget", type=float, default=200.0)
    ap.add_argument("--gate-timeout", type=float, default=30.0)
    ap.add_argument("--ready-timeout", type=float, default=90.0)
    a = ap.parse_args(argv)
    if a.stage:
        print(json.dumps({"staging": str(stage(a.stage))}))
        return 0
    if not a.evidence or not math.isfinite(a.budget) or not (0 < a.budget <= 230):
        ap.error("--run needs --evidence and 0 < --budget <= 230 (inside the 240 s wrapper timeout)")
    return run(Path(a.run), Path(a.evidence), a.budget, a.gate_timeout, a.ready_timeout)


if __name__ == "__main__":
    sys.exit(main())
