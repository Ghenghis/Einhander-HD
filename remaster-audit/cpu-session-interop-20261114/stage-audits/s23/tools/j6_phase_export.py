"""J6 (claude-einhander-s23): Stage 2 cycling-phase exporter, ready for the S2-2 capture. PIXEL JOB: grant required.

  python -I j6_phase_export.py <out_dir> <budget_seconds> selftest
  python -I j6_phase_export.py <out_dir> <budget_seconds> <phase-words.json>     {"<TEX>-<PAL>": "<32-byte CLUT hex>", ...}

Method = the frozen stage2-prep-v2 method, reproduced with the lane's own code imported READ-ONLY from
comfy-authoring/w7-stage2/tools (s2master.render, render_isolated, export; build_s2.merge_rects semantics):
  * masters: frozen stage2-prep-v1/master/<TEX>-index-master-8x.npz (sha256 checked against the prep-v1 manifest);
  * cells: every drawn uv rect of the key in w7-stage2/work/draws-s2.json, merged (prep2 rule); no lum field, no energy;
  * CLUT words: given per key; crc32(words) must equal the key's PAL (refused otherwise);
  * export: s2master.export (page2048 + page1024, forced centres, centre validation).
s23 additions, written alongside, never replacing: strict whole-cell R1-R4 (s23lib) on every export and an R5
bleed-filled copy under keys-r5/ (alpha and visible RGB byte-identical).
selftest: re-exports the 8 frozen prep-v2 keys with their manifest words and compares every exported file
pixel-for-pixel (and by sha256) with the frozen prep-v2 files. Only a byte-identical selftest makes the method claim.
Outputs only under <out_dir>; frozen inputs read only. Resumable per key (rows.jsonl).
"""
import json
import os
import sys
import zlib
from datetime import datetime, timezone

os.environ.setdefault("OMP_NUM_THREADS", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s23lib as SL  # noqa: E402

W7 = SL.ROOT + "/remaster-audit/comfy-authoring/w7-stage2"
sys.path.insert(0, W7 + "/tools")
sys.dont_write_bytecode = True
import s2lib as L  # noqa: E402  (read-only use)
import s2master as M  # noqa: E402  (read-only use)
import numpy as np  # noqa: E402

PREP1 = W7 + "/frozen/stage2-prep-v1"
PREP2 = W7 + "/frozen/stage2-prep-v2"
PREP1_SHA = "9e4a8270e988791efdc8fb37573447b5c89389014dc30a562eb093da4e5c83a0"
PREP2_SHA = "4d3c33969637c393d2bd2cfda81969633bd66f62d53ebed2302cffa029a84db9"


def merge_rects(rects):
    rs = [list(r) for r in rects]
    changed = True
    while changed:
        changed = False
        for i in range(len(rs)):
            for j in range(i + 1, len(rs)):
                a, b = rs[i], rs[j]
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    rs[i] = [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]
                    rs.pop(j)
                    changed = True
                    break
            if changed:
                break
    return [tuple(r) for r in rs]


def main(out, budget, mode):
    SL.below_normal()
    b = SL.Budget(float(budget))
    os.makedirs(out, exist_ok=True)
    assert SL.sha256_file(PREP1 + "/manifest.json") == PREP1_SHA
    p1 = json.load(open(PREP1 + "/manifest.json", encoding="utf-8"))
    draws = json.load(open(W7 + "/work/draws-s2.json", encoding="utf-8"))
    if mode == "selftest":
        assert SL.sha256_file(PREP2 + "/manifest.json") == PREP2_SHA
        p2 = json.load(open(PREP2 + "/manifest.json", encoding="utf-8"))
        words = {k: v["clut"]["words_hex"] for k, v in p2["keys"].items()}
    else:
        words = json.load(open(mode, encoding="utf-8"))
        p2 = None
    rows_p = out + "/rows.jsonl"
    done = {r["key"] for r in SL.read_jsonl(rows_p)}
    SL.append_jsonl(out + "/sessions.jsonl", dict(start_utc=datetime.now(timezone.utc).isoformat(), pid=os.getpid(), mode=mode,
                                                  todo=len([k for k in words if k not in done]),
                                                  tool_sha256=SL.sha256_file(os.path.abspath(__file__)),
                                                  lane_code={q: SL.sha256_file(f"{W7}/tools/{q}") for q in ("s2master.py", "s2lib.py", "build_s2.py")}))
    masters = {}
    for key in sorted(words):
        if key in done:
            continue
        if b.left() < 30:
            break
        tex, pal = key[:8], key[9:]
        wb = bytes.fromhex(words[key])
        if len(wb) != 32 or "%08X" % (zlib.crc32(wb) & 0xFFFFFFFF) != pal:
            SL.append_jsonl(rows_p, dict(key=key, refused="CLUT words crc32 != PAL or length != 32"))
            continue
        if key not in draws:
            SL.append_jsonl(rows_p, dict(key=key, refused="no draw record in draws-s2.json (cells unknown)"))
            continue
        if tex not in masters:
            mp = f"{PREP1}/master/{tex}-index-master-8x.npz"
            assert SL.sha256_file(mp) == p1["pages"][tex]["master"]["sha256"], ("prep master hash", tex)
            Mx = M.load_master(mp)
            Mx["src"] = L.load_tex(tex)
            assert np.array_equal(Mx["idx"], Mx["src"]["idx"])
            masters[tex] = Mx
        Mx = masters[tex]
        idx = Mx["idx"]
        prm = p1["pages"][tex]["params"]
        c = np.frombuffer(wb, "<u2").copy()
        img = M.render(Mx, c)
        rects = []
        for u, n in draws[key]["uv_top"]:
            r = (u[0], u[1], u[2] + 1, u[3] + 1)
            if r not in rects:
                rects.append(r)
        cells = merge_rects(rects)
        iso = M.render_isolated(img, Mx, idx, c, cells, prm["sigma_cat_texel"], prm["power_cat"], prm["sigma_t_texel"], lum=False)
        files = M.export(img, idx, c, out, key)
        ncls = SL.clut_classes(c.astype(np.int64))[idx]
        rec = dict(key=key, tex=tex, pal=pal, words_hex=words[key], cells=[list(x) for x in cells], cells_isolated=iso, files={})
        for fk, f in files.items():
            pth = f"{out}/{f['path']}"
            a = SL.load_rgba(pth)
            s = a.shape[1] // idx.shape[1]
            v = SL.validate(a, ncls, s)
            filled, written = SL.bleed_fill(a)
            r5p = f"{out}/keys-r5/{fk}/{key}.png"
            h5 = SL.save_png(r5p, filled)
            v5 = SL.validate(SL.load_rgba(r5p), ncls, s)
            fr = dict(f, strict=v, strict_pass=all(v[k] == 0 for k in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "nonclass_px")),
                      r5_copy=dict(path=f"keys-r5/{fk}/{key}.png", sha256=h5, cutout_rgb_written=written, r5_after=v5["r5_fringe_px"],
                                   strict_unchanged=all(v5[k] == v[k] for k in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px"))))
            if p2 is not None:
                ref = f"{PREP2}/{p2['keys'][key]['files'][fk]['path']}"
                rb = SL.load_rgba(ref)
                fr["selftest"] = dict(ref=ref, ref_sha256=SL.sha256_file(ref), sha_equal=SL.sha256_file(ref) == f["sha256"],
                                      pixels_equal=bool(rb.shape == a.shape and (rb == a).all()),
                                      differing_px=int((rb != a).any(-1).sum()) if rb.shape == a.shape else None)
            rec["files"][fk] = fr
        SL.append_jsonl(rows_p, rec)
        print(key, {fk: (x["strict_pass"], x.get("selftest", {}).get("pixels_equal")) for fk, x in rec["files"].items()}, flush=True)
    rows = [r for r in SL.read_jsonl(rows_p) if "files" in r]
    s = dict(updated_utc=datetime.now(timezone.utc).isoformat(), mode=mode, exported=len(rows), requested=len(words),
             refused=[r for r in SL.read_jsonl(rows_p) if "refused" in r],
             strict_pass_files=sum(f["strict_pass"] for r in rows for f in r["files"].values()),
             files=sum(len(r["files"]) for r in rows))
    if p2 is not None:
        s["selftest_pixels_equal"] = sum(f["selftest"]["pixels_equal"] for r in rows for f in r["files"].values())
        s["selftest_sha_equal"] = sum(f["selftest"]["sha_equal"] for r in rows for f in r["files"].values())
    json.dump(s, open(out + "/summary.json.tmp", "w", encoding="utf-8"), indent=1)
    os.replace(out + "/summary.json.tmp", out + "/summary.json")
    SL.append_jsonl(out + "/sessions.jsonl", dict(end_utc=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(s))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
