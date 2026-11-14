#!/usr/bin/env python3
"""s45 (claude-einhander-s45, EIN-S4/S5-WHOLE-CELL-20261114): READ-ONLY class coverage of every static key on the selected
Stage 4 / Stage 5 pages. For each page's rendered + renderable_later + palette-hold keys: CLUT entry classes and the share of
page texels that become cutout (word 0) / STP / opaque under that CLUT (index histogram of the 32 KiB page words only; no
PNG, no render). Tells which keys would exercise real whole-cell class edges once rendered, and flags pages whose review
CLUT has no transparency although other candidate CLUTs do. Writes ONLY s45/clut-coverage/<UTC>/coverage.json."""
import datetime
import hashlib
import json
import os
import zlib
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np  # noqa: E402

RA = Path("C:/github/Einhander/remaster-audit")
OUT = RA / "parallel-stages-20261114/s45/clut-coverage"
READINESS = RA / "runtime-review/seven-stage-status-20261114/lane-readiness-20261114T131712Z.json"
STATIC = RA / "fullgame-prep/static-extraction/stages"


def crc(b):
    return "%08X" % (zlib.crc32(b) & 0xFFFFFFFF)


def main():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([me.cpu_affinity()[-1]])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = OUT / stamp
    rd.mkdir(parents=True, exist_ok=False)
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    res = dict(run=stamp, owner="claude-einhander-s45", pages={}, status="DATA ONLY; static CLUT/index statistics")
    for lane in readiness["stages"]:
        st = lane["stage"]
        if st not in (4, 5):
            continue
        sd = STATIC / f"stage{st}"
        static_keys = {e["key"]: e for e in json.loads((sd / "keys.json").read_text(encoding="utf-8"))}
        clut_words = {(e["x"], e["y"], e["pal"]): e["words_hex"] for e in json.loads((sd / "cluts.json").read_text(encoding="utf-8"))}
        for f in lane["candidate_folders"]:
            m = json.loads(Path(f["manifest"]).read_text(encoding="utf-8"))
            for tex, pg in m["pages"].items():
                pid = f"S{st}:{tex}"
                if pid in res["pages"]:
                    res["pages"][pid]["sets"].append(Path(f["path"]).name)
                    continue
                w = np.frombuffer(Path(pg["source"]["path"]).read_bytes(), "<u2").reshape(256, 64)
                idx = np.stack([(w >> (4 * k)) & 0xF for k in range(4)], -1).reshape(-1)
                hist = np.bincount(idx, minlength=16)
                rendered = [r["key"] for r in pg.get("rendered_keys") or []]
                later = [r["key"] for r in pg.get("renderable_later") or []]
                hold = list(pg.get("palette_hold_keys") or [])
                rows = []
                for key in rendered + [k for k in later if k not in rendered] + [k for k in hold if k not in rendered and k not in later]:
                    cp = sd / "keys" / f"{key}.clut.bin"
                    se = static_keys.get(key) or {}
                    xy = se.get("clut_xy")
                    hexw = clut_words.get((xy[0], xy[1], key[9:])) if xy else None
                    if cp.is_file():
                        cb, src = cp.read_bytes(), "keys/*.clut.bin"
                    elif hexw:
                        cb, src = bytes.fromhex(hexw), "cluts.json"
                    else:
                        rows.append(dict(key=key, clut_xy=xy, error="no static CLUT words (runtime-written or not a static key)"))
                        continue
                    cl = np.frombuffer(cb, "<u2")
                    cut_e, stp_e = cl == 0, (cl & 0x8000) != 0
                    n = hist.sum()
                    rows.append(dict(key=key, role="rendered" if key in rendered else ("later" if key in later else "hold-only"),
                                     palette_hold=key in hold, clut_xy=xy, clut_source=src,
                                     pair_count=se.get("pair_count"), crc_ok=crc(cb) == key[9:],
                                     all_zero=bool(cut_e.all()), cutout_entries=int(cut_e.sum()), stp_entries=int(stp_e.sum()),
                                     cutout_share=round(float(hist[cut_e].sum() / n), 4), stp_share=round(float(hist[stp_e].sum() / n), 4),
                                     classes_present=int(hist[cut_e].sum() > 0) + int(hist[stp_e & ~cut_e].sum() > 0) +
                                     int(hist[~cut_e & ~stp_e].sum() > 0)))
                ok = [r for r in rows if "error" not in r and not r["all_zero"]]
                res["pages"][pid] = dict(stage=st, tex=tex, sets=[Path(f["path"]).name], mode=pg.get("mode"),
                                         index_histogram=hist.tolist(), keys=rows,
                                         n_keys=len(rows), n_nonzero=len(ok),
                                         n_with_cutout_texels=sum(r["cutout_share"] > 0 for r in ok),
                                         n_with_stp_texels=sum(r["stp_share"] > 0 for r in ok),
                                         n_multi_class=sum(r["classes_present"] > 1 for r in ok),
                                         review_has_cutout=any(r["cutout_share"] > 0 for r in ok if r["role"] == "rendered"),
                                         max_cutout_share=max([r["cutout_share"] for r in ok], default=0.0))
    out = rd / "coverage.json"
    out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for pid, p in res["pages"].items():
        print(f"{pid:12s} {p['mode']:7s} keys {p['n_keys']:3d} nonzero {p['n_nonzero']:3d} cutout {p['n_with_cutout_texels']:3d} "
              f"stp {p['n_with_stp_texels']:3d} multi {p['n_multi_class']:3d} review_cut {p['review_has_cutout']} max_cut {p['max_cutout_share']}")
    print("run", stamp, "coverage.json", hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
