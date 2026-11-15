#!/usr/bin/env python3
"""s67 R-A r0: REGION-SCOPED class measurement for the 95A3BCF8 distant-city page (plan 6780484c, root msg_ba5f6cd2).
SOURCE ONLY until a CPU grant. Read-only on every input. It writes ONLY a new exclusive run dir under
s67/runs/<UTC>-95a3-region-measure/.

Why: class-mip f6-v2 reports whole-page counts only (C, D and F report identical numbers), so "fails INSIDE region X" is
unmeasured. Per-pixel flags make that attribution exact. This tool runs the frozen proto-v2b cm_flags_ex ONCE on the whole
2048 page, at both bounds the s67 strict audit uses (0.5 = strict s/2 R2; 1e9 = connectivity-only). It then counts flagged
pixels and bad native cells (bits 2|4|16 = R2 displaced, R4 island, R1 centre) INSIDE every regions.json rectangle, plus the
remainder outside all rectangles. Whole-page cm_validate is also recorded so it can be compared with f6-v2. No crop
re-validation is done: that would change the edge context.

Inputs, all pinned and verified before any decode:
  * HD page = the STAGED file in the raw37c-r6 staging pack (sha must equal the staging png_pins entry); for K also the
    authored K-panel-v1 page2048 791c01a8 (a provenance comparison only; it is not staged);
  * native words/CLUT = w2-v2 frozen source/95A3BCF8-<pal>.words.bin (shared page words 29706a63) and .clut.bin
    (16 x u16, 4bpp);
  * class_mip.dll = the PREBUILT s67 r2b dll 509a2bb1, whose folder's class_mip.c/.h must be byte-identical to frozen
    proto-v2b. No compiler is started; subprocess is disabled in-process.
Usage: python -I -B s67_95a3_region_measure_r0.py [--dry-run] [--cpu=N] [--budget-s=50]
  --dry-run: verify pins and file sizes only (no PNG decode, no dll load)."""
import ctypes
import datetime
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path("C:/github/Einhander")
RA = ROOT / "remaster-audit"
S67 = RA / "parallel-stages-20261114/s67"
sys.path.insert(0, str(S67 / "tools"))
import s67_strict_audit as A  # noqa: E402  (native_class, cell_map, CmReport, PROTO)

PIN = {
    "audit_module": (S67 / "tools/s67_strict_audit.py", "9ba1ef4d92d693482f6c855e136950dfbe734df8e18c22767a955c7c3313faf0"),
    "staging": (RA / "dev-center-evidence/stage1-completion-20261112/raw37c-r6-20261114T2331Z/hd-on_rewind-off/raw37c-staging.json",
                "2710782ef5627a16f9c1528ac1f662d80bd03a1cb5985365c5ef1db04f809c79"),
    "regions": (RA / "comfy-authoring/t3-green-lights/regions.json",
                "52aa9d2509c14fd633b6fc373a2f6f12ca44d377fb44b9fa65c9a302cfbac075"),
    "dll": (S67 / "repairs/stage6-fx-classrepair-r2b-nativefill/class_mip.dll",
            "509a2bb1f4db2ee191c8509429d55c4bb5194ff04767ac0bfa8fa6da96c18420"),
    "proto_c": (A.PROTO / "class_mip.c", "c84efa609fde17b906e6755074fece074bced8d5c03a0f2c3ea2cb41d6f5193d"),
    "proto_h": (A.PROTO / "class_mip.h", "90e68bddd2004890654cc7b366ddc4980f8fce1c5f71313c6a60c4a3e2cf90e3"),
    "k_authored": (RA / "claude-backlog/95a3-k-panel/frozen/95A3BCF8-K-panel-v1/page2048/95A3BCF8-723E222C.png",
                   "791c01a86dbf12167dee22738de654043f4f548de59d0cb4dfa3a573423cc020"),
}
SRC = RA / "comfy-authoring/w2-polish/frozen/atlas-95A3BCF8-w2-v2/source"
PAGE_WORDS_SHA = "29706a6386158ab3f4b5f08de5c0ca6cf509c6d7436ed3bf5402d69f7b8658d2"
# key palette -> the region letter(s) the audit/census assigns it (attribution is reported for ALL regions regardless)
TARGETS = {"857DB48E": ["C"], "615C942A": ["D"], "D60B38CC": ["F"], "540CAA98": ["F"], "97445449": ["L"],
           "8A79B9D5": ["T"], "D9527F27": ["U"], "0DA946C5": ["X", "Y"], "723E222C": ["K"]}
BITS = 2 | 4 | 16
TW = TH = 256        # native texels of the page (4bpp, 64 words x 256 rows)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def verify_pins():
    for name, (p, want) in PIN.items():
        got = sha(p)
        assert got == want, f"pin {name} {p}: {got} != {want}"
    for n in ("class_mip.c", "class_mip.h"):
        assert sha(PIN["dll"][0].parent / n) == sha(A.PROTO / n), f"prebuilt dll folder {n} differs from proto-v2b"
    log = (PIN["dll"][0].parent / "compile.log").read_text(encoding="utf-8", errors="replace")
    assert log.startswith("exit 0"), "prebuilt dll compile.log does not start with 'exit 0'"


def jobs(staging):
    pins = staging["pack"]["png_pins"]
    root = Path(staging["pack"]["root"])
    out = []
    for pal, letters in TARGETS.items():
        key = f"95A3BCF8-{pal}"
        rel = f"einhander-texture-replacements/{key}.png"
        assert rel in pins, f"{key} not staged"
        words, clut = SRC / f"{key}.words.bin", SRC / f"{key}.clut.bin"
        assert sha(words) == PAGE_WORDS_SHA and words.stat().st_size == 32768, f"{key} page words not 29706a63/32768"
        assert clut.stat().st_size == 32, f"{key} clut not 32 B"
        files = {"staged": (root / rel, pins[rel])}
        if pal == "723E222C":
            files["k_authored_791c01a8"] = PIN["k_authored"]
        out.append(dict(key=key, letters=letters, words=words, clut=clut, clut_sha=sha(clut), files=files))
    return out


def region_counts(fl, s, regions):
    """flagged px / bad cells inside each region rectangle (bbox [u0,v0,u1,v1] in native texels) + outside-all remainder."""
    res, covered = {}, np.zeros((TH, TW), bool)
    cellbad = ((fl & BITS) != 0).reshape(TH, s, TW, s).sum(axis=(1, 3))
    for r in regions:
        u0, v0, u1, v1 = r["bbox"]
        sub = cellbad[v0:v1, u0:u1]
        res[r["id"]] = dict(bbox=r["bbox"], cells=int(sub.size), bad_cells=int((sub > 0).sum()), flagged_px=int(sub.sum()))
        covered[v0:v1, u0:u1] = True
    rest = cellbad[~covered]
    res["_outside_all_regions"] = dict(cells=int(rest.size), bad_cells=int((rest > 0).sum()), flagged_px=int(rest.sum()))
    res["_page_total"] = dict(cells=int(cellbad.size), bad_cells=int((cellbad > 0).sum()), flagged_px=int(cellbad.sum()))
    return res


def main():
    dry = "--dry-run" in sys.argv
    budget = float(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--budget-s=")), "50"))
    t0 = time.time()
    verify_pins()
    staging = json.loads(PIN["staging"][0].read_bytes())
    regions = json.loads(PIN["regions"][0].read_bytes())
    js = jobs(staging)
    for j in js:
        for tag, (p, want) in j["files"].items():
            assert sha(p) == want, f"{j['key']} {tag} {p} sha != pin {want}"
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S67 / "runs" / (stamp + "-95a3-region-measure" + ("-dry" if dry else ""))
    rd.mkdir(parents=True, exist_ok=False)
    rec = dict(tool=Path(__file__).name, tool_sha256=sha(Path(__file__)), started_utc=stamp, dry_run=dry,
               pins={k: dict(path=str(p), sha256=w) for k, (p, w) in PIN.items()}, bits="2|4|16 (R2 displaced, R4 island, "
               "R1 centre)", bounds=dict(s2=0.5, conn_only=1.0e9), rows=[],
               scope="region attribution of per-pixel flags on the WHOLE page; not a repair; not a look acceptance")
    if dry:
        rec["rows"] = [dict(key=j["key"], letters=j["letters"], files={t: v[1] for t, v in j["files"].items()},
                            clut_sha256=j["clut_sha"]) for j in js]
    else:
        try:
            import psutil
            me = psutil.Process()
            me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            cpu = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--cpu=")), None)
            if cpu is not None:
                me.cpu_affinity([cpu])
            rec["process"] = dict(pid=me.pid, affinity=me.cpu_affinity(), nice="below_normal")
        except Exception as e:  # recorded, never silently claimed
            rec["process"] = dict(error=repr(e))

        def _no_child(*a, **k):
            raise RuntimeError("child processes are disabled in this tool")
        subprocess.run = subprocess.Popen = _no_child
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        lib = ctypes.CDLL(str(PIN["dll"][0]))
        lib.cm_validate.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.POINTER(A.CmReport)]
        lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
        for j in js:
            clut_words = list(np.frombuffer(j["clut"].read_bytes(), "<u2"))
            ncls = A.native_class(j["words"].read_bytes(), 64, 256, clut_words)
            assert ncls.shape == (TH, TW), ncls.shape
            for tag, (p, want) in j["files"].items():
                if time.time() - t0 > budget:
                    rec["aborted"] = f"time budget {budget}s reached at {j['key']} {tag}"
                    break
                with Image.open(p) as im:
                    a = np.ascontiguousarray(np.asarray(im.convert("RGBA")))
                H, W = a.shape[:2]
                assert W % TW == 0 and H % TH == 0 and W // TW == H // TH, f"dims {W}x{H}"
                s = W // TW
                rep = A.CmReport()
                lib.cm_validate(a.ctypes.data, W, H, ncls.ctypes.data, TW, TH, s, ctypes.byref(rep))
                row = dict(key=j["key"], letters=j["letters"], file=tag, path=str(p), sha256=want, scale=s,
                           page_cm_validate={f: int(getattr(rep, f)) for f, _ in A.CmReport._fields_})
                for bname, bound in (("s2", 0.5), ("conn_only", 1.0e9)):
                    fl = np.zeros((H, W), np.uint8)
                    lib.cm_flags_ex(a.ctypes.data, W, H, ncls.ctypes.data, TW, TH, s, bound, 0, fl.ctypes.data)
                    row[f"regions_{bname}"] = region_counts(fl, s, regions)
                rec["rows"].append(row)
            if rec.get("aborted"):
                break
    rec["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rec["elapsed_s"] = round(time.time() - t0, 3)
    with open(rd / "result.json", "x", encoding="utf-8") as f:
        json.dump(rec, f, indent=1)
    print(json.dumps(dict(run=str(rd), rows=len(rec["rows"]), aborted=rec.get("aborted"), dry_run=dry)))
    return 0 if not rec.get("aborted") else 1


if __name__ == "__main__":
    sys.exit(main())
