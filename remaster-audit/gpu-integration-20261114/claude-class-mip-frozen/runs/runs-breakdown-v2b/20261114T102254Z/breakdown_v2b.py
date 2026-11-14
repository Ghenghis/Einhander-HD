#!/usr/bin/env python3
"""Whole-cell v2 violation BREAKDOWN + R2 policy sensitivity, v2b DRAW MAPPING (claude-einhander).
v2b fixes the draw-to-key mapping of run runs-breakdown/20261114T101011Z, which mapped every uv relative to the page
origin and so treated 608 exact-region/upload keys as fully drawn:
  * exact_region keys: key origin in page texels = ((vram_x - page_x) * tpw, vram_y - page_y) from the pack's
    ExactRegions.tsv (verified: all 113,239 such events land inside the key and source_word_xy ==
    floor(local uv min / tpw) for every one);
  * upload keys (no region row): source_word_xy is the word offset of the drawn rect inside the key, so the origin is
    uv_min_u - sx*tpw - [0, tpw-1], uv_min_v - sy; the per-key intersection over all events gives the candidate
    origins; every candidate that keeps all vertices inside the key is rasterised (union: conservative by < 1 word);
  * native_page keys: page origin (unchanged); anything still outside the key -> key treated as fully drawn.
 Read-only, CPU only, below normal, one
process, one image decoded at a time. Uses proto-v2b/cm_flags_ex (the v2 classifier with a selectable R2 bound; its
default policy is exactly cm_validate - cross-checked here against runs-f6-v2).

For every target of the f6 v2 audit (world pack replacements with a CRC-proven native dump, livepack-classfix-v2, the
95A3 K panel) it classifies each violating HD pixel (R1/R2/R4 under the v2 default policy) by KIND:
  hole     native class visible (127/255), HD pixel cutout (0)      -> a transparent hole/notch where the PS1 draws
  added    native class cutout (0), HD pixel visible                -> opaque pixels where the PS1 shows through
  stp      both visible, 127 <-> 255                                -> only the STP bit differs
and by DRAW EVIDENCE from every capture.jsonl under stage1-completion-20261112/*/hd-on_rewind-off/*/ (uv triangles of
source_draw_query_matched / replacement_gl_draw_submitted events, mapped to key-local native texels; a texel counts as
drawn when its square overlaps a drawn triangle, 3x3 sub-sample test):
  visible-transparency  hole/added on a drawn texel
  visible-blend         stp on a texel drawn with a semi-transparent primitive (HD_FS: stp selects the blend pass)
  mask-bit-only         stp on a texel drawn only by opaque primitives (colour identical; only the written mask bit
                        differs, which matters only if the game mask-tests later draws)
  not-drawn-in-capture  no captured draw covers the texel (captures are partial: this is NOT proof it is never drawn)
Keys whose draws could not be mapped into the key rectangle (texture windows / uploads) are treated as fully drawn
(conservative) and listed.
Policy sensitivity: R2 bound s/2 Euclidean (v2 default), s/2 Chebyshev, s Euclidean, s/4 Euclidean, and connectivity
only (no displacement bound): violating px, cells, pinhole cells and visible-transparency px per policy.
Writes ONLY runs-breakdown-v2b/<UTC>/ (exist_ok=False): result.json, run.log, input copies, the DLL, capture log hashes."""
import argparse
import collections
import ctypes
import datetime
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "class-audit"))
import audit_native_classes_v2 as A  # noqa: E402

CLANG = "C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang.exe"
E = Path("C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112")
V2FIX = Path("C:/github/Einhander/remaster-audit/comfy-authoring/w6-livepack-classfix/frozen/livepack-classfix-v2/einhander-texture-replacements")
KPANEL = HERE.parent / "95a3-k-panel/frozen/95A3BCF8-K-panel-v1/page2048/95A3BCF8-723E222C.png"
F6V2 = HERE / "runs-f6-v2/20261114T095517Z/result.json"
PROTO = HERE / "proto-v2b"
POLICIES = [("s/2 euclidean (v2 default)", 0.5, 0), ("s/2 chebyshev", 0.5, 1), ("s euclidean", 1.0, 0),
            ("s/4 euclidean", 0.25, 0), ("connectivity only", 1.0e9, 0)]
TPW = {0: 4, 1: 2, 2: 1}
VIOL = 2 | 4 | 16
OFFS = (0.02, 0.5, 0.98)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_draws(logs, stats, regions):
    ev = collections.defaultdict(list)
    for lp in logs:
        with open(lp, encoding="utf-8") as f:
            for line in f:
                if '"uv_vertices"' not in line:
                    continue
                d = json.loads(line)
                if d.get("event") not in ("source_draw_query_matched", "replacement_gl_draw_submitted"):
                    continue
                tpw = TPW.get(d.get("depth"))
                if tpw is None:
                    stats["bad_depth"] += 1
                    continue
                ww, hh = d["native_words"]
                ev[d["key"]].append((d["source_kind"], tpw, ww * tpw, hh, tuple(d["page_xy"]), tuple(d.get("source_word_xy", [0, 0])),
                                     tuple(d["uv_bounds"]), tuple(map(tuple, d["uv_vertices"])), d.get("semi", -1) >= 0))
                stats[f"verts_{len(d['uv_vertices'])}"] += 1
    draws = {}
    for key, es in ev.items():
        k = dict(tris=set(), unmapped=0, events=len(es), dims=None, method=collections.Counter(), origins=0)
        ups = [e for e in es if key not in regions and e[0] == "upload"]
        up_origins = None
        if ups:
            lo, hi = -10 ** 9, 10 ** 9
            ovs = {e[6][1] - e[5][1] for e in ups}
            for e in ups:
                lo = max(lo, e[6][0] - e[5][0] * e[1] - (e[1] - 1))
                hi = min(hi, e[6][0] - e[5][0] * e[1])
            up_origins = []
            if lo <= hi and len(ovs) == 1:
                ov = next(iter(ovs))
                for ou in range(lo, hi + 1):
                    if all(all(0 <= u - ou <= e[2] and 0 <= v - ov <= e[3] for u, v in e[7]) for e in ups):
                        up_origins.append((ou, ov))
            k["origins"] = len(up_origins)
        for kind, tpw, tw, th, (px, py), sw, ub, vs, semi in es:
            k["dims"] = (tw, th)
            if key in regions:
                vx, vy = regions[key][0], regions[key][1]
                origins, m = [((vx - px) * tpw, vy - py)], "exact-region"
            elif kind == "upload":
                origins, m = up_origins, "upload-origin"
            else:
                origins, m = [(0, 0)], "page-origin"
            if not origins:
                k["unmapped"] += 1
                k["method"][m + "-unresolved"] += 1
                continue
            ok = False
            for ou, ov in origins:
                lv = [(u - ou, v - ov) for u, v in vs]
                if any(not (0 <= u <= tw and 0 <= v <= th) for u, v in lv):
                    continue
                ok = True
                if len(lv) == 3:
                    k["tris"].add((tuple(lv), semi))
                elif len(lv) == 4:
                    k["tris"].add(((lv[0], lv[1], lv[2]), semi))
                    k["tris"].add(((lv[1], lv[2], lv[3]), semi))
            if ok:
                k["method"][m] += 1
            else:
                k["unmapped"] += 1
                k["method"][m + "-outside"] += 1
        draws[key] = k
    return draws


def raster(tris, tw, th):
    drawn = np.zeros((th, tw), bool)
    semi = np.zeros((th, tw), bool)
    for (p0, p1, p2), is_semi in tris:
        xs, ys = (p0[0], p1[0], p2[0]), (p0[1], p1[1], p2[1])
        u0, u1 = max(0, int(np.floor(min(xs)))), min(tw - 1, int(np.ceil(max(xs))))
        v0, v1 = max(0, int(np.floor(min(ys)))), min(th - 1, int(np.ceil(max(ys))))
        if u1 < u0 or v1 < v0:
            continue
        U, V = np.meshgrid(np.arange(u0, u1 + 1, dtype=np.float64), np.arange(v0, v1 + 1, dtype=np.float64))
        area = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p1[1] - p0[1]) * (p2[0] - p0[0])
        if area == 0:                                   # degenerate: conservative bounding box (never seen in practice)
            hit = np.ones_like(U, bool)
        else:
            hit = np.zeros_like(U, bool)
            sg = 1.0 if area > 0 else -1.0
            for fx in OFFS:
                for fy in OFFS:
                    x, y = U + fx, V + fy
                    e0 = ((p1[0] - p0[0]) * (y - p0[1]) - (p1[1] - p0[1]) * (x - p0[0])) * sg
                    e1 = ((p2[0] - p1[0]) * (y - p1[1]) - (p2[1] - p1[1]) * (x - p1[0])) * sg
                    e2 = ((p0[0] - p2[0]) * (y - p2[1]) - (p0[1] - p2[1]) * (x - p2[0])) * sg
                    hit |= (e0 >= 0) & (e1 >= 0) & (e2 >= 0)
        drawn[v0:v1 + 1, u0:u1 + 1] |= hit
        if is_semi:
            semi[v0:v1 + 1, u0:u1 + 1] |= hit
    return drawn, semi


def provenance(f):
    p = Path(f.get("input", {}).get("manifest", {}).get("path", "") or "")
    parts = p.parts
    if "comfy-authoring" in parts:
        i = parts.index("comfy-authoring")
        if len(parts) > i + 3:
            return f"{parts[i + 1]}/{parts[i + 3]}"
    return f.get("origin", "unknown")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, default=E / "world-integrated-crisp-v4")
    a = ap.parse_args()
    A.below()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = HERE / "runs-breakdown-v2b" / stamp
    rd.mkdir(parents=True, exist_ok=False)
    for p in (Path(__file__), PROTO / "class_mip.c", PROTO / "class_mip.h", HERE.parent / "class-audit/audit_native_classes_v2.py"):
        shutil.copy2(p, rd / p.name)
    log = []
    dll = rd / "class_mip.dll"
    c = subprocess.run([CLANG, "-shared", "-O2", "-std=c11", str(PROTO / "class_mip.c"), "-o", str(dll)],
                       capture_output=True, text=True, timeout=600)
    if c.returncode:
        (rd / "run.log").write_text(c.stderr, encoding="utf-8")
        raise SystemExit("dll build failed")
    lib = ctypes.CDLL(str(dll))
    lib.cm_flags_ex.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_double, ctypes.c_int, ctypes.c_void_p]
    lib.cm_flags_ex.restype = ctypes.c_int

    logs = sorted(E.glob("*/hd-on_rewind-off/*/capture.jsonl"))
    log_meta = [dict(path=str(p), bytes=p.stat().st_size, sha256=sha(p)) for p in logs]

    cand = json.loads((a.pack / "candidate.json").read_text(encoding="utf-8"))
    prov = {f["name"][:-4]: provenance(f) for f in cand["files"]}
    pack_dir = a.pack / "pack"
    repl = pack_dir / "einhander-texture-replacements"
    regions = {}
    for line in (pack_dir / "ExactRegions.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        p = line.split()
        if len(p) == 8:
            regions[p[0]] = tuple(int(x) for x in p[1:])
    emissive = {Path(f.get("name", f.get("composed_path", ""))).name for f in cand.get("emissive_files", [])}
    dstats = collections.Counter()
    draws = load_draws(logs, dstats, regions)
    mstat = collections.Counter()
    for k in draws.values():
        mstat.update(k["method"])
        mstat["keys_unmapped"] += k["unmapped"] > 0
    log.append(f"capture logs {len(logs)}; keys with draws {len(draws)}; {dict(dstats)}; mapping {dict(mstat)}")
    print(log[-1], flush=True)
    set_dirs = sorted(A.CA.glob("*/frozen/*/source"))
    cap_dirs = sorted(p for p in A.E.glob("*/hd-on_rewind-off/*") if p.is_dir())
    order = [A.STOCK, A.UHU] + set_dirs

    def source(key):
        for d in ([pack_dir] if key in regions else order):
            s, r = A.try_dump(d, key, regions)
            if s:
                return s, r
        if key not in regions:
            for d in cap_dirs:
                s, r = A.try_dump(d, key, regions)
                if s:
                    return s, r
        return None, None

    targets = [("pack", n[:-4], repl / n) for n in sorted(f["name"] for f in cand["files"]) if n not in emissive]
    targets += [("livepack-classfix-v2", p.stem, p) for p in sorted(V2FIX.glob("*.png"))]
    targets += [("k-panel-page2048", KPANEL.stem, KPANEL)]
    rows = collections.defaultdict(list)
    for n, (grp, key, png) in enumerate(targets):
        row = dict(group=grp, key=key, png=str(png), png_sha256=sha(png), provenance=prov.get(key) if grp == "pack" else grp)
        src, cls = source(key)
        if src is None:
            row.update(status="NOT CHECKED", reason="no CRC-proven native dump")
            rows[grp].append(row)
            continue
        with Image.open(png) as im:
            rgba = np.ascontiguousarray(np.asarray(im.convert("RGBA")), dtype=np.uint8)
        th, tw = cls.shape
        H, W = rgba.shape[:2]
        if W % tw or H % th or W // tw != H // th:
            row.update(status="NOT CHECKED", reason=f"scale {W / tw}x{H / th}")
            rows[grp].append(row)
            continue
        s = W // tw
        ncls = np.ascontiguousarray(cls, dtype=np.uint8)
        X = rgba[..., 3]
        C = np.repeat(np.repeat(ncls, s, 0), s, 1)
        flags = {}
        for name, bf, met in POLICIES:
            fl = np.zeros((H, W), np.uint8)
            rc = lib.cm_flags_ex(rgba.ctypes.data, W, H, ncls.ctypes.data, tw, th, s, bf, met, fl.ctypes.data)
            if rc:
                raise SystemExit(f"cm_flags_ex rc {rc} on {key}")
            flags[name] = fl
        dk = draws.get(key)
        if dk is None:
            draw_status = "no draws in captures"
            D = np.zeros((th, tw), bool)
            Ds = np.zeros((th, tw), bool)
        elif dk["unmapped"]:
            draw_status = "unmapped draws: treated as fully drawn"
            D = np.ones((th, tw), bool)
            Ds = np.ones((th, tw), bool)
        else:
            if dk["dims"] != (tw, th):
                draw_status = f"draw dims {dk['dims']} != native {(tw, th)}: treated as fully drawn"
                D = np.ones((th, tw), bool)
                Ds = np.ones((th, tw), bool)
            else:
                draw_status = "mapped"
                D, Ds = raster(dk["tris"], tw, th)
        Dp = np.repeat(np.repeat(D, s, 0), s, 1)
        Dsp = np.repeat(np.repeat(Ds, s, 0), s, 1)
        isc = (X == 0) | (X == 127) | (X == 255)

        def cell_any(m):
            return m.reshape(th, s, tw, s).any(axis=(1, 3))

        pol = {}
        for name, _, _ in POLICIES:
            fl = flags[name]
            v = (fl & VIOL) != 0
            hole = v & (C != 0) & (X == 0)
            added = v & (C == 0) & (X != 0)
            vt = (hole | added) & Dp
            centre_bad = cell_any((fl & 16) != 0)
            other = cell_any((fl & (2 | 4)) != 0)
            pin = other & ~centre_bad
            pol[name] = dict(viol_px=int(v.sum()), viol_cells=int(cell_any(v).sum()), pinhole_cells=int(pin.sum()),
                             visible_transparency_px=int(vt.sum()), visible_transparency_cells=int(cell_any(vt).sum()),
                             pinhole_cells_drawn=int((pin & D).sum()))
        f0 = flags[POLICIES[0][0]]
        v = (f0 & VIOL) != 0
        hole = v & (C != 0) & (X == 0)
        added = v & (C == 0) & (X != 0) & isc
        stp = v & (C != 0) & (X != 0) & (C != X) & isc
        nonclass = v & ~isc
        kinds = dict(hole=int(hole.sum()), added=int(added.sum()), stp=int(stp.sum()), nonclass=int(nonclass.sum()),
                     other=int((v & ~hole & ~added & ~stp & ~nonclass).sum()))
        vis = {"visible-transparency": int(((hole | added) & Dp).sum()), "visible-blend": int((stp & Dsp).sum()),
               "mask-bit-only": int((stp & Dp & ~Dsp).sum()), "nonclass-drawn": int((nonclass & Dp).sum()),
               "not-drawn-in-capture": int((v & ~Dp).sum())}
        crosscheck = dict(r2=int(((f0 & 2) != 0).sum()), r4=int(((f0 & 4) != 0).sum()), r1=int(((f0 & 16) != 0).sum()))
        row.update(status="VIOLATION" if v.any() else "PASS", scale=s, native=[tw, th], draw_status=draw_status,
                   draw_events=dk["events"] if dk else 0, draw_method=dict(dk["method"]) if dk else {},
                   upload_origin_candidates=dk["origins"] if dk else 0, drawn_texels=int(D.sum()), drawn_semi_texels=int(Ds.sum()),
                   kinds=kinds, visibility=vis, policies=pol, crosscheck=crosscheck)
        rows[grp].append(row)
        del rgba, X, C, flags, f0, v, Dp, Dsp
        if (n + 1) % 100 == 0:
            log.append(f"{n + 1}/{len(targets)}")
            print(log[-1], flush=True)

    def summ(rs):
        chk = [r for r in rs if "kinds" in r]
        out = dict(files=len(rs), checked=len(chk), not_checked=len(rs) - len(chk))
        kt, vt, ds, cc = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
        pt = {name: collections.Counter() for name, _, _ in POLICIES}
        pk = {name: collections.Counter() for name, _, _ in POLICIES}
        for r in chk:
            kt.update(r["kinds"]); vt.update(r["visibility"]); ds[r["draw_status"].split(":")[0]] += 1; cc.update(r["crosscheck"])
            for name in pt:
                pt[name].update(r["policies"][name])
                pk[name]["keys_violating"] += r["policies"][name]["viol_px"] > 0
                pk[name]["keys_with_pinholes"] += r["policies"][name]["pinhole_cells"] > 0
                pk[name]["keys_visible_transparency"] += r["policies"][name]["visible_transparency_px"] > 0
        out.update(kinds=dict(kt), visibility=dict(vt), draw_status=dict(ds), crosscheck_totals=dict(cc),
                   keys=dict(violating=sum(1 for r in chk if r["status"] == "VIOLATION"),
                             visible_transparency=sum(1 for r in chk if r["visibility"]["visible-transparency"]),
                             visible_blend=sum(1 for r in chk if r["visibility"]["visible-blend"]),
                             stp_only=sum(1 for r in chk if r["status"] == "VIOLATION" and not r["kinds"]["hole"]
                                          and not r["kinds"]["added"] and not r["kinds"]["nonclass"]),
                             only_not_drawn=sum(1 for r in chk if r["status"] == "VIOLATION" and
                                                r["visibility"]["not-drawn-in-capture"] == sum(r["kinds"].values()))),
                   policies={name: dict(pt[name]) | dict(pk[name]) for name in pt})
        return out

    summary = {g: summ(r) for g, r in rows.items()}
    f6 = json.loads(F6V2.read_text(encoding="utf-8"))
    xc = {}
    for g, sm in summary.items():
        t = f6["summary"].get(g, {}).get("totals", {})
        xc[g] = dict(f6_r2=t.get("r2_displaced_px"), here_r2=sm["crosscheck_totals"].get("r2"),
                     f6_r4=t.get("r4_island_px"), here_r4=sm["crosscheck_totals"].get("r4"),
                     f6_r1=t.get("r1_centre_bad"), here_r1=sm["crosscheck_totals"].get("r1"))
        xc[g]["equal"] = xc[g]["f6_r2"] == xc[g]["here_r2"] and xc[g]["f6_r4"] == xc[g]["here_r4"] and xc[g]["f6_r1"] == xc[g]["here_r1"]
    by_set = collections.defaultdict(collections.Counter)
    for r in rows.get("pack", []):
        if "kinds" not in r:
            continue
        b = by_set[r["provenance"]]
        b["keys"] += 1
        b["keys_violating"] += r["status"] == "VIOLATION"
        b["keys_visible_transparency"] += r["visibility"]["visible-transparency"] > 0
        b["visible_transparency_px"] += r["visibility"]["visible-transparency"]
        b["visible_blend_px"] += r["visibility"]["visible-blend"]
        b["pinhole_cells_drawn"] += r["policies"][POLICIES[0][0]]["pinhole_cells_drawn"]
    rank = sorted((r for g in rows.values() for r in g if "kinds" in r and r["visibility"]["visible-transparency"]),
                  key=lambda r: -r["visibility"]["visible-transparency"])
    out = dict(run=stamp, pack=str(a.pack), candidate_sha256=sha(a.pack / "candidate.json"), dll_sha256=sha(dll),
               validator_sha256=sha(PROTO / "class_mip.c"), f6_v2_result=str(F6V2), f6_v2_result_sha256=sha(F6V2),
               policies=[dict(name=n, bound_frac=b, metric=["euclidean", "chebyshev"][m]) for n, b, m in POLICIES],
               capture_logs=log_meta, draw_parse_stats=dict(dstats), draw_mapping_stats=dict(mstat), crosscheck_vs_f6_v2=xc, summary=summary,
               by_set={k: dict(v) for k, v in sorted(by_set.items(), key=lambda kv: -kv[1]["visible_transparency_px"])},
               rank_visible_transparency=[dict(group=r["group"], key=r["key"], provenance=r["provenance"],
                                               px=r["visibility"]["visible-transparency"], kinds=r["kinds"],
                                               draw_status=r["draw_status"],
                                               cells=r["policies"][POLICIES[0][0]]["visible_transparency_cells"])
                                          for r in rank[:80]],
               rows={g: r for g, r in rows.items()})
    (rd / "result.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    (rd / "run.log").write_text("\n".join(log) + "\n", encoding="utf-8")
    with open(HERE / "runs-breakdown-v2b" / "INDEX.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(run=stamp, result_sha256=sha(rd / "result.json"),
                                 crosscheck_equal=all(v["equal"] for v in xc.values()))) + "\n")
    print(json.dumps(dict(crosscheck=xc, summary=summary), indent=1))


if __name__ == "__main__":
    main()
