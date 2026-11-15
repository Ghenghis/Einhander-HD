"""J10 preview r2 (claude-einhander-s23): corner guard on TWO keys (S2 28127931-7C2D834A, S3 wall 59B55BC8-89C297ED)
+ synthetic fixtures. PIXEL JOB (small): one fresh CPU grant, one attempt, outer hard cap 120 s (run_granted --cap 120).

  python -I j10_preview_r2.py <new_out_dir> <budget_seconds>

New revision of tools/j10_preview.py (v1 9ba10f17..., preserved unchanged) after codex-einhander's source review
msg_339c5fb1ec6b471f:
  1. refuses python -O (base tools use assert for pins) and non-isolated python (-I required); every critical pin and
     native identity check in THIS file is an explicit check, never an assert;
  2. <new_out_dir> must not exist: created with os.mkdir (exclusive); every file THIS tool writes is opened exclusively
     ('x'); the S2 and S3 sub-folders are new inside it (J9's own writes inside the new S2 sub-folder use its usual
     append/replace, which cannot touch existing data because that sub-folder is checked absent first);
  3. exit status: 0 only if the selftest passed, both keys finished, every file is strict-pass and R5-zero, every corner
     check shows 0 differing quadrants, compare and the 2-entry plan were written; 2 for any failure, stop or partial
     result; 3 for a refusal before any work. PREVIEW.json (partial results included) is always written once the
     output folder exists;
  4. one monotonic deadline = start + budget, checked before every step; J9 receives the remaining time; the outer
     whole-tree hard cap is run_granted's --cap. Estimates are not promises;
  5. the full local import closure (below) is hash-checked BEFORE any import, and each module is executed from the
     exact bytes that were hashed (no .pyc, no path search); third-party versions are recorded. Every data input
     (words, CLUT words, cells, manifests, previous PNGs, J9 queue inputs) is pinned here by path + sha256 and checked
     before use; manifest-provided paths are only used where they equal a pinned path.
Scope: preview only (no batch, no pack). Identities stay as before: the S2 key is live-drawn with a 'likely' TEX (live
key + CLUT confirm required); the S3 key is predicted-static (S3 has no draw records). Not admission, not frozen.
Steps: pins -> exclusive mkdir -> pinned imports -> selftest -> fixtures -> S3 key (J5 per-key steps on the guarded
index field) -> S2 key (J9 method, queue limited to this key) -> compare (native | previous | J10) -> review-only
composer plan (parent and cutout_rgb_fill null for codex-einhander).
"""
import hashlib
import json
import os
import sys
import time
import types
import zlib
from datetime import datetime, timezone

EXIT_OK, EXIT_FAIL, EXIT_REFUSED = 0, 2, 3
RA = "C:/github/Einhander/remaster-audit"
S23 = RA + "/parallel-stages-20261114/s23"
T = S23 + "/tools"
CODE = [  # (module name, path, reviewed sha256) in load order; each module's local imports are earlier in this list
    ("s23lib", T + "/s23lib.py", "e26b2fbe0f5632c121e254e284be68eace8b54f5425cb785b9f53d9504a972b7"),
    ("scale2x_cg", T + "/scale2x_cg.py", "0c0517d37b033f469330c65d1bd533cd69bf210a4fbb2688fafae0d2954cd7ee"),
    ("j2_s3_dither_hybrid", T + "/j2_s3_dither_hybrid.py", "ba450150580c96c24973ecf632917a04074ac1928d1bfa80edb69eecbf5f33ab"),
    ("j5_s3_scale2x", T + "/j5_s3_scale2x.py", "143a95af12f9c3adbf093f2dd4dd18629e59a6c65de82e74d0baad11cf442a90"),
    ("j7_s3_hybrid", T + "/j7_s3_hybrid.py", "cdf9ff185917971e80b95839f3a7e584002edb383b0bf59d2ac16b77692d8b05"),
    ("j9_s2_drawn_authoring", T + "/j9_s2_drawn_authoring.py", "374af13cbf252cf0db4294afdf500ca91fcd09a1d7125c2a12bef82b592a6021"),
    ("j10_corner_guard", T + "/j10_corner_guard.py", "e392a84335434ac9073670bce31d9fa50d8acf5986a3c7eecaa9c8ed7518210d"),
    ("build_stage1_frozen_candidate", RA + "/build_stage1_frozen_candidate.py", "c8c3cca561ef01a662b5ae8c43fe79e3830b4550136b7e8ef7dda677bc0df699"),
]
S2 = dict(key="28127931-7C2D834A", window=[128, 136, 176, 168],
          words=dict(path=RA + "/fullgame-prep/static-extraction/stages/stage2/textures/28127931.words.bin",
                     sha256="0e110d9503fb351bd5848129120cb20af1b405fa7afc17726d579fdacdbf4358", rect=[896, 0, 64, 256]),
          clut_hex="ffffe4a4a39c8294618c418c408c208820840084008400000000000000000000",
          prev_png=dict(path=S23 + "/proposals/s2-drawn-j9-20261114T171215Z/keys/page2048/28127931-7C2D834A.png",
                        sha256="a6801c466ebe0f3ba4b22cb617d481c146b0a05656bd96a20a1b81ba58f422b2"))
S3 = dict(key="59B55BC8-89C297ED", window=[103, 111, 151, 143],
          set_manifest=dict(path=RA + "/comfy-authoring/w7-stage3/frozen/stage3-machinery-walls-v1/manifest.json",
                            sha256="184e8ad8558826ca75177d3e05293d279d4aa6b28eb4eab2a6c6050ba58cd1e0"),
          words=dict(path=RA + "/fullgame-prep/static-extraction/stages-v4/stage3/textures/59B55BC8.words.bin",
                     sha256="4562f9978b4c551dc7fbb476374df24c8564c9086ebb3b56fef09c247f04306a", rect=[704, 0, 64, 256]),
          cells=dict(path=RA + "/comfy-authoring/w7-stage3/frozen/stage3-machinery-walls-v1/master/59B55BC8-cells-32grid.npy",
                     sha256="f78debb18b14da791f6bc4c38bb642ef2e3c7bc0073f1f4f0d59694b2ae00679"),
          clut_hex="ce3dad396b314a2d29290825e720c61ca51884146310ee16e7150025c01c8014",
          prev_png=dict(path=S23 + "/proposals/s3-scale2x-20261114T154534Z/keys/page2048/59B55BC8-89C297ED.png",
                        sha256="68326064de4fde1150c2bb26af4417653a6df299cc7d938111813bc397ce42ae"))
DATA = {  # every other input read by this run (J9 queue inputs as pinned by J9 itself / its 17:12Z session)
    S23 + "/proposals/s2-drawn-j9-20261114T171215Z/manifest.json": "5b2f15b5894efe593176d89bece4a3ab69c218a0f1e6f31dcf27fe2b3b2f0b9c",
    S23 + "/proposals/s3-scale2x-20261114T154534Z/manifest.json": "22370974abccc6d5868d021c48d1ccee27fa5e0eaafdce1ae9cb4eb372f9128e",
    S23 + "/proposals/s3-hybrid-20261114T155630Z/manifest.json": "b71851546ff48e41a02449abb833aa5712d1e4a8e2fa0c10a1e0e1842008875f",
    S23 + "/proposals/s2-trains-scale2x-20261114T160110Z/manifest.json": "46c26204d95de0d85182074528121afa9789f9df5801e7706d9c4478dd0c0871",
    S23 + "/runs/fullstage-20261114T171029Z/fullstage-coverage.json": "2e93fba0b817eb5b94aa0886b3ab627432c46c11c0bfa5bf32fc811401801692",
    RA + "/fullgame-prep/stage-review/stage2/keys-live.json": "a227087745ba3859d7c1032cc1b7970860b4a0877ec08aee41eefd83fc953928",
    RA + "/fullgame-prep/static-extraction/stages/stage2/textures.json": "fd2ec38057af96c69b3f7924faca1898d1c86672d8c2902ce1ec2b77ce6d7eeb",
    RA + "/fullgame-prep/static-extraction/stages/stage2/cluts.json": "4f861e86ec603c88410790c4f64b632e7c092d83aeb216302319d4fc3a25dfa4",
    RA + "/comfy-authoring/w7-stage2/work/draws-s2.json": "6a693c707c6c08444dff96c133198198d152a2f8579d67b7a4f5e2eafc2684d7",
}
for _d in (S2["words"], S2["prev_png"], S3["set_manifest"], S3["words"], S3["cells"], S3["prev_png"]):
    DATA[_d["path"]] = _d["sha256"]


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    with open(p, "rb") as f:
        return sha_bytes(f.read())


def refuse(reason):
    print(json.dumps(dict(status="REFUSED", reason=reason, utc=datetime.now(timezone.utc).isoformat())), flush=True)
    sys.exit(EXIT_REFUSED)


def precheck(out):
    if sys.flags.optimize:
        refuse("python -O/-OO strips the base tools' assert-based pin checks; run without -O")
    if not sys.flags.isolated:
        refuse("run with python -I")
    bad = []
    for _, p, h in CODE:
        if not os.path.isfile(p) or sha_file(p) != h:
            bad.append(p)
    for p, h in DATA.items():
        if not os.path.isfile(p) or sha_file(p) != h:
            bad.append(p)
    if bad:
        refuse(f"pinned code/data missing or changed: {bad}")
    for k in (S2, S3):
        cb = bytes.fromhex(k["clut_hex"])
        if len(cb) != 32 or "%08X" % (zlib.crc32(cb) & 0xFFFFFFFF) != k["key"][9:]:
            refuse(f"CLUT words do not hash to {k['key'][9:]}")
        with open(k["words"]["path"], "rb") as f:
            if "%08X" % (zlib.crc32(f.read()) & 0xFFFFFFFF) != k["key"][:8]:
                refuse(f"words file does not hash to TEX {k['key'][:8]}")
    parent = os.path.dirname(os.path.abspath(out))
    if not os.path.isdir(parent):
        refuse(f"parent folder missing: {parent}")
    if os.path.lexists(out):
        refuse(f"output folder already exists: {out}")


def load_pinned():
    """Execute each closure module from the exact bytes that were hashed (no .pyc, no sys.path search)."""
    mods = {}
    for name, p, h in CODE:
        with open(p, "rb") as f:
            b = f.read()
        if sha_bytes(b) != h:
            raise RuntimeError(f"code changed between check and load: {p}")
        m = types.ModuleType(name)
        m.__file__ = p
        sys.modules[name] = m
        exec(compile(b, p, "exec"), m.__dict__)
        mods[name] = m
    return mods


class _Stop(Exception):
    """A recorded stop (selftest failure, both keys failed): partial results are kept and the exit code is nonzero."""


def xjson(p, obj):
    with open(p, "x", encoding="utf-8") as f:
        json.dump(obj, f, indent=1)
    return sha_file(p)


def main(out, budget):
    t0 = time.monotonic()
    deadline = t0 + float(budget)
    left = lambda: deadline - time.monotonic()
    precheck(out)
    try:
        os.mkdir(out)                                              # exclusive: fails if it appeared meanwhile
    except OSError as e:
        refuse(f"exclusive mkdir failed: {type(e).__name__}: {e}")
    rec = dict(owner="claude-einhander-s23", name=os.path.basename(out), revision="j10_preview_r2", started_utc=datetime.now(timezone.utc).isoformat(),
               pid=os.getpid(), affinity=os.environ.get("S23_CPU"), budget_s=float(budget), status="PREVIEW (private; not frozen; not for import)",
               keys=[S2["key"], S3["key"]], code_pins={n: h for n, _, h in CODE}, data_pins=DATA, steps={}, key_errors={},
               self=dict(path=os.path.abspath(__file__).replace("\\", "/"), sha256=sha_file(os.path.abspath(__file__))))
    ok = False
    try:
        M = load_pinned()
        L, CG, J5, J9, J10, C = (M[n] for n in ("s23lib", "scale2x_cg", "j5_s3_scale2x", "j9_s2_drawn_authoring", "j10_corner_guard",
                                                  "build_stage1_frozen_candidate"))
        import numpy as np
        import PIL
        import scipy
        from PIL import Image
        rec["third_party"] = dict(python=sys.version.split()[0], numpy=np.__version__, pillow=PIL.__version__, scipy=scipy.__version__)
        L.below_normal()

        def step(name, need):
            if left() < need:
                raise TimeoutError(f"deadline: {round(left(), 1)} s left before step {name} (needs ~{need} s)")
            rec["steps"][name] = dict(started_s=round(time.monotonic() - t0, 2))

        def done(name, **kw):
            rec["steps"][name].update(kw, finished_s=round(time.monotonic() - t0, 2))

        def xpng(p, arr):                                          # s23lib.save_png settings, but exclusive create
            with open(p, "xb") as f:
                Image.fromarray(arr, "RGBA" if arr.ndim == 3 and arr.shape[2] == 4 else None).save(f, format="PNG", optimize=False, compress_level=6)
            return sha_file(p)

        step("selftest", 5)
        st = J10.selftest()
        rec["selftest"] = dict(path="selftest.json", sha256=xjson(out + "/selftest.json", st), passed=bool(st["passed"]))
        done("selftest", passed=bool(st["passed"]))
        if not st["passed"]:
            rec["stopped"] = "selftest failed; no pixel work started"
            raise _Stop

        step("fixtures", 5)
        yy, xx = np.mgrid[0:24, 0:24]
        fx = {}
        a = np.zeros((16, 16), np.uint8); a[4:12, 4:12] = 1; fx["block"] = a
        a = np.zeros((16, 16), np.uint8); a[2:14, 8:14] = 1; a[8:14, 2:14] = 1; fx["step_L"] = a
        a = np.zeros((12, 12), np.uint8); a[5, 5] = 1; fx["single_texel"] = a
        fx["edge45"] = (xx + yy >= 24).astype(np.uint8)
        fx["edge2to1"] = (xx + 2 * yy >= 34).astype(np.uint8)
        fx["checker"] = ((xx[:12, :12] + yy[:12, :12]) % 2).astype(np.uint8)
        arrays, rows, fstats = {}, [], {}
        pal = np.array([[30, 30, 34], [214, 208, 190]], np.uint8)
        for name, a in fx.items():
            n, o, c = J10.nn(a, 8), J10.old_cascade(a), CG.cascade(a, 3)
            arrays[name + "_in"], arrays[name + "_j5"], arrays[name + "_j10"] = a, o, c
            fstats[name] = dict(j5_vs_nearest_px=int((o != n).sum()), j10_vs_nearest_px=int((c != n).sum()), j10_vs_j5_px=int((c != o).sum()))
            gap = np.full((n.shape[0], 8, 3), (255, 0, 255), np.uint8)
            rows.append(np.concatenate([pal[n], gap, pal[o], gap, pal[c]], 1))
        with open(out + "/fixtures.npz", "xb") as f:
            np.savez_compressed(f, **arrays)
        wmax = max(r.shape[1] for r in rows)
        canvas = np.concatenate([np.pad(r, ((6, 6), (0, wmax - r.shape[1]), (0, 0)), constant_values=255) for r in rows], 0)
        rec["fixtures"] = dict(npz=dict(path="fixtures.npz", sha256=sha_file(out + "/fixtures.npz")),
                               sheet=dict(path="fixtures.png", sha256=xpng(out + "/fixtures.png", canvas),
                                          layout="rows " + ", ".join(fx) + "; columns nearest | J5 cascade | J10 cascade at 8x"), stats=fstats)
        done("fixtures")

        J5.up_isolated = J10.up_isolated_checked                   # J10's guarded cascade from here on
        J5.scale2x = J10.unguarded_called
        for mod in (J5, J9):
            if not (mod.__doc__ or "").startswith("J10 REVISION"):
                mod.__doc__ = J10.NOTE + mod.__doc__

        def native(k):
            with open(k["words"]["path"], "rb") as f:
                b = f.read()
            if sha_bytes(b) != k["words"]["sha256"]:
                raise RuntimeError(f"words changed before decode: {k['key']}")
            idx, wsha, crc_ok = L.load_words(k["words"]["path"], k["words"]["rect"], k["key"][:8])
            if not crc_ok or wsha != k["words"]["sha256"]:
                raise RuntimeError(f"words identity check failed: {k['key']}")
            c = L.clut_words(k["clut_hex"])
            return idx, L.clut_rgb(c), L.clut_classes(c)

        res = {}
        # ---- S3 wall key: J5 per-key steps (j5_s3_scale2x.main lines 206-218) on the guarded index field
        try:
            step("s3_key", 20)
            k = S3
            sub = out + f"/s3-{k['key']}"
            os.mkdir(sub)
            os.makedirs(sub + "/keys/page2048")
            os.makedirs(sub + "/keys/page1024")
            wm_bytes = open(k["set_manifest"]["path"], "rb").read()
            if sha_bytes(wm_bytes) != k["set_manifest"]["sha256"]:
                raise RuntimeError("walls manifest changed")
            wm = json.loads(wm_bytes.decode("utf-8"))
            pg, ke = wm["pages"][k["key"][:8]], wm["keys"][k["key"]]
            if (pg["words"]["path"] != k["words"]["path"] or pg["words"]["sha256"] != k["words"]["sha256"] or list(pg["vram_rect_words"]) != k["words"]["rect"]
                    or os.path.normpath(os.path.join(os.path.dirname(k["set_manifest"]["path"]), pg["cells"]["file"])) != os.path.normpath(k["cells"]["path"])
                    or pg["cells"]["sha256"] != k["cells"]["sha256"] or ke["clut"]["words_hex"] != k["clut_hex"] or ke["tex"] != k["key"][:8]):
                raise RuntimeError("walls manifest entry differs from the pinned words/cells/CLUT")
            del J10.STATS[:]
            idx, wsha, labels, label_meta = J5.page_source("s3", os.path.dirname(k["set_manifest"]["path"]), wm, k["key"][:8], {})
            idx_n, rgb, cls = native(k)
            if not np.array_equal(idx, idx_n):
                raise RuntimeError("page_source index differs from the pinned words")
            up8, up4 = J5.up_isolated(idx, labels, 3), J5.up_isolated(idx, labels, 2)
            ncls, nrgb = cls[idx], rgb[idx]
            files = {}
            for fk, up, s in (("page2048", up8, 8), ("page1024", up4, 4)):
                a = np.dstack([rgb[up], cls[up]])
                a, rep = J5.repair(a, up, ncls, nrgb, s)
                a, written = L.bleed_fill(a)
                v = L.validate(a, ncls, s)
                files[fk] = dict(path=f"keys/{fk}/{k['key']}.png", sha256=xpng(f"{sub}/keys/{fk}/{k['key']}.png", a), scale=s, repair=rep,
                                 cutout_rgb_written=written, strict=v, r5_zero=v["r5_fringe_px"] == 0,
                                 strict_pass=all(v[q] == 0 for q in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "nonclass_px")))
            man = dict(name=os.path.basename(sub), owner="claude-einhander-s23", status="PROPOSAL PREVIEW (private; not frozen; not for import)",
                       method=J5.__doc__.strip(), source_set=k["set_manifest"], corner_check=list(J10.STATS), cells=label_meta,
                       keys={k["key"]: dict(tex=k["key"][:8], words=dict(k["words"], kind="page"),
                                            clut=dict(crc32=k["key"][9:], words_hex=k["clut_hex"], kind="frozen set"), files=files)})
            res[k["key"]] = dict(dir=sub, manifest=dict(path=sub + "/manifest.json", sha256=xjson(sub + "/manifest.json", man)), files=files,
                                 corner_check=man["corner_check"], native=(nrgb, ncls))
            done("s3_key")
        except Exception as e:
            import traceback
            rec["key_errors"][S3["key"]] = dict(error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc()[-1500:])
        # ---- S2 key: J9 method, queue limited to this key
        try:
            step("s2_key", 30)
            k = S2
            sub = out + f"/s2-{k['key']}"
            if os.path.lexists(sub):
                raise RuntimeError("S2 sub-folder exists")
            orig = J9.queue
            J9.queue = lambda: [q for q in orig() if q["key"] == k["key"]]
            del J10.STATS[:]
            try:
                J9.main(sub, max(25.0, left() - 20))                 # J9 starts the key only while >= 20 s of its budget remain
            finally:
                J9.queue = orig
            mp = sub + "/manifest.json"
            if not os.path.isfile(mp):
                raise RuntimeError("J9 wrote no manifest.json (budget stop or failure; see PARTIAL.json)")
            m = json.load(open(mp, encoding="utf-8"))
            ke = m["keys"][k["key"]]
            if (ke["words"]["path"] != k["words"]["path"] or ke["words"]["sha256"] != k["words"]["sha256"] or list(ke["words"]["rect"]) != k["words"]["rect"]
                    or ke["clut"]["words_hex"] != k["clut_hex"] or set(m["keys"]) != {k["key"]}):
                raise RuntimeError("J9 key entry differs from the pinned words/CLUT")
            res[k["key"]] = dict(dir=sub, manifest=dict(path=mp, sha256=sha_file(mp)), files=ke["files"], corner_check=list(J10.STATS))
            done("s2_key")
        except Exception as e:
            import traceback
            rec["key_errors"][S2["key"]] = dict(error=f"{type(e).__name__}: {e}", traceback=traceback.format_exc()[-1500:])
        rec["keys_result"] = {key: dict(manifest=r["manifest"], files={fk: {q: f.get(q) for q in ("path", "sha256", "strict_pass", "r5_zero")} for fk, f in r["files"].items()},
                                        corner_check=[{q: c[q] for q in ("times", "corners_total", "corner_quadrant_differs_total")} for c in r["corner_check"]])
                              for key, r in res.items()}
        if not res:
            rec["stopped"] = "both keys failed"
            raise _Stop

        step("compare", 6)
        rows, diffs = [], {}
        for k in (S2, S3):
            if k["key"] not in res:
                continue
            r = res[k["key"]]
            pb = open(k["prev_png"]["path"], "rb").read()
            if sha_bytes(pb) != k["prev_png"]["sha256"]:
                raise RuntimeError(f"previous PNG changed before decode: {k['key']}")
            o = L.load_rgba(k["prev_png"]["path"])
            a = L.load_rgba(f"{r['dir']}/{r['files']['page2048']['path']}")
            if "native" in r:
                nrgb, ncls = r["native"]
            else:
                idx_n, rgb, cls = native(k)
                nrgb, ncls = rgb[idx_n], cls[idx_n]
            nat = L.up(np.dstack([nrgb, ncls]), 8)
            vis = (a[..., 3] != 0) & (o[..., 3] != 0)
            diffs[k["key"]] = dict(alpha_px=int((a[..., 3] != o[..., 3]).sum()), visible_rgb_px=int(((a[..., :3] != o[..., :3]).any(-1) & vis).sum()),
                                   previous=k["prev_png"])
            rows.append((f"{k['key']} uv{k['window']}: native 8x | previous | J10",
                         np.concatenate([J10.crop(nat, k["window"]), J10.crop(o, k["window"]), J10.crop(a, k["window"])], 1)))
        wmax = max(x.shape[1] for _, x in rows)
        canvas = np.concatenate([np.pad(x, ((4, 4), (0, wmax - x.shape[1]), (0, 0))) for _, x in rows], 0)
        rec["compare"] = dict(path="compare.png", sha256=xpng(out + "/compare.png", canvas), rows=[t for t, _ in rows])
        rec["diff_vs_previous"] = diffs
        done("compare")

        step("plan", 3)
        os.mkdir(out + "/native-cluts")
        entries = []
        for k in (S2, S3):
            if k["key"] not in res:
                continue
            r = res[k["key"]]
            cp = f"{out}/native-cluts/{k['key']}.clut.bin"
            with open(cp, "xb") as f:
                f.write(bytes.fromhex(k["clut_hex"]))
            ns = dict(source_words=dict(path=k["words"]["path"], sha256=k["words"]["sha256"]), source_clut=dict(path=cp.replace("\\", "/"), sha256=sha_file(cp)),
                      source_shape_words=[k["words"]["rect"][2], k["words"]["rect"][3]], depth=0)
            C.verified_native_source(ns, k["key"])                  # composer's own check; raises on mismatch
            img = f"{r['dir']}/{r['files']['page2048']['path']}"
            entries.append(dict(manifest=r["manifest"], key=k["key"], image=dict(path=img, sha256=sha_file(img)), native_source=ns))
        plan = dict(parent=None, cutout_rgb_fill=None,
                    purpose="REVIEW-ONLY two-key preview of the J10 corner guard (S2 28127931-7C2D834A world: live-drawn, TEX likely, live key+CLUT "
                            "confirm required; S3 59B55BC8-89C297ED wall: predicted-static); not admission",
                    drafted_by="claude-einhander-s23", drafted_utc=datetime.now(timezone.utc).isoformat(),
                    todo_for_codex=["set parent={path,sha256} of the candidate to extend", "set cutout_rgb_fill policy (opt-in)",
                                    "compare against the same keys from the previous proposals before any J10 batch"],
                    composer=dict(path=CODE[-1][1], sha256=CODE[-1][2]), entries=entries)
        rec["plan"] = dict(path="plan-preview-2keys.json", sha256=xjson(out + "/plan-preview-2keys.json", plan), entries=len(entries))
        done("plan")

        fs = [f for r in res.values() for f in r["files"].values()]
        cc = [c for r in res.values() for c in r["corner_check"]]
        rec["checks"] = dict(both_keys=len(res) == 2, files=len(fs), strict_pass=all(bool(f.get("strict_pass")) for f in fs),
                             r5_zero=all(bool(f.get("r5_zero")) for f in fs), corner_calls=len(cc),
                             corner_quadrant_differs_total=sum(c["corner_quadrant_differs_total"] for c in cc),
                             corners_total=sum(c["corners_total"] for c in cc), plan_entries=len(entries))
        ch = rec["checks"]
        ok = (ch["both_keys"] and ch["files"] == 4 and ch["strict_pass"] and ch["r5_zero"] and ch["corner_calls"] >= 4
              and ch["corner_quadrant_differs_total"] == 0 and ch["plan_entries"] == 2 and not rec["key_errors"])
    except _Stop:
        pass
    except Exception as e:
        import traceback
        rec["error"] = f"{type(e).__name__}: {e}"
        rec["traceback"] = traceback.format_exc()[-2000:]
    finally:
        rec["ok"] = bool(ok)
        rec["exit_code"] = EXIT_OK if ok else EXIT_FAIL
        rec["seconds"] = round(time.monotonic() - t0, 2)
        rec["finished_utc"] = datetime.now(timezone.utc).isoformat()
        with open(out + "/PREVIEW.json", "x", encoding="utf-8") as f:
            json.dump(rec, f, indent=1)
        print(json.dumps({q: rec.get(q) for q in ("ok", "exit_code", "selftest", "stopped", "error", "key_errors", "checks", "diff_vs_previous", "plan", "seconds")})[:4000])
        print("PREVIEW.json", sha_file(out + "/PREVIEW.json"), flush=True)
    return rec["exit_code"]


if __name__ == "__main__":
    if len(sys.argv) != 3:
        refuse("usage: j10_preview_r2.py <new_out_dir> <budget_seconds>")
    try:
        b = float(sys.argv[2])
    except ValueError:
        refuse("budget must be a number of seconds")
    if not 20 <= b <= 115:
        refuse("budget must be 20..115 s (outer hard cap is run_granted --cap 120)")
    sys.exit(main(sys.argv[1], b))
