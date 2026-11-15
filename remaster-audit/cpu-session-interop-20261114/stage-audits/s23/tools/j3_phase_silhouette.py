"""J3 (claude-einhander-s23): class-silhouette consistency across the selected CLUT phases of shared Stage 2 pages.
PIXEL JOB: run only inside a granted CPU slot.

  python -I j3_phase_silhouette.py <run_dir>

For every pair of selected keys on the same TEX page (3DD37B6B, AD934A7E, 4915FBCF; different methods/folders):
  * native class maps under both CLUTs; E = texels whose clamped 3x3 native class neighbourhood is identical under both
    CLUTs (there the whole-cell rules allow the same sub-native contour, so a phase change should not move it);
  * HD alpha planes of both files at the same resolution; disagreement = pixels in E-cells where alpha differs;
  * reported over the whole page and inside the union of both keys' recorded drawn uv rects.
A nonzero count inside drawn rects means the silhouette jumps when the game switches between those palettes on the
same texels. Read only on frozen inputs; output only in <run_dir>.
"""
import itertools
import json
import os
import sys
from datetime import datetime, timezone

os.environ.setdefault("OMP_NUM_THREADS", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402
import s23lib as L  # noqa: E402

SEL = L.S23 + "/runs/selection-20261114T133254Z/selection-map.json"
SEL_SHA = "f29ff130d3f2d087e95a90cfebe7892415cf480af3cc3718723f4594b7256250"
BASE = L.ROOT + "/remaster-audit/comfy-authoring/w7-stage2/frozen"
PAGES = ("3DD37B6B", "AD934A7E", "4915FBCF")


def nb_sig(ncls):
    """clamped 3x3 neighbourhood signature per texel (9 classes packed)."""
    th, tw = ncls.shape
    pad = np.pad(ncls, 1, mode="edge")
    code = {0: 0, 127: 1, 255: 2}
    c = np.vectorize(code.get)(pad).astype(np.int64)
    sig = np.zeros((th, tw), np.int64)
    for dy in range(3):
        for dx in range(3):
            sig = sig * 3 + c[dy:dy + th, dx:dx + tw]
    return sig


def main(run_dir):
    L.below_normal()
    os.makedirs(run_dir, exist_ok=True)
    assert L.sha256_file(SEL) == SEL_SHA
    sel = json.load(open(SEL, encoding="utf-8"))["stages"]["2"]["keys"]
    src = {}
    for name in sorted(os.listdir(BASE)):
        mp = f"{BASE}/{name}/manifest.json"
        if os.path.exists(mp):
            for tex, pg in (json.load(open(mp, encoding="utf-8")).get("pages") or {}).items():
                w = pg.get("words") if isinstance(pg, dict) else None
                if isinstance(w, dict) and tex not in src:
                    src[tex] = (w["path"], pg["vram_rect_words"], w.get("sha256"))
    out = dict(owner="claude-einhander-s23", created_utc=datetime.now(timezone.utc).isoformat(), selection_map=SEL_SHA,
               tool_sha256=L.sha256_file(os.path.abspath(__file__)), pairs=[])
    for tex in PAGES:
        keys = sorted(k for k, v in sel.items() if v["tex"] == tex)
        idx, wsha, ok = L.load_words(src[tex][0], src[tex][1], tex)
        assert ok and wsha == src[tex][2]
        info = {}
        for k in keys:
            kr = sel[k]
            m = json.load(open(f"{BASE}/{kr['selected_folder']}/manifest.json", encoding="utf-8"))["keys"][k]
            c = L.clut_words(m["clut"]["words_hex"])
            rects = [r[0] for r in ((m.get("live") or {}).get("uv_top") or []) if isinstance(r, list) and r]
            info[k] = dict(folder=kr["selected_folder"], ncls=L.clut_classes(c)[idx], lut=L.clut_classes(c).tolist(), rects=rects,
                           files={fk: f"{BASE}/{kr['selected_folder']}/{f['path']}" for fk, f in kr["files"].items()})
        for a, b in itertools.combinations(keys, 2):
            A, B = info[a], info[b]
            E = nb_sig(A["ncls"]) == nb_sig(B["ncls"])
            D = np.zeros(idx.shape, bool)
            for x0, y0, x1, y1 in A["rects"] + B["rects"]:
                D[max(y0, 0):y1 + 1, max(x0, 0):x1 + 1] = True
            rec = dict(page=tex, a=a, b=b, a_folder=A["folder"], b_folder=B["folder"], same_class_lut=A["lut"] == B["lut"],
                       equal_nbhd_texels=int(E.sum()), drawn_texels=int(D.sum()), files={})
            for fk in ("page2048", "page1024"):
                pa, pb = L.load_rgba(A["files"][fk])[..., 3], L.load_rgba(B["files"][fk])[..., 3]
                s = pa.shape[1] // idx.shape[1]
                Eh, Dh = L.up(E, s), L.up(D, s)
                diff = pa != pb
                rec["files"][fk] = dict(scale=s, alpha_diff_in_equal_cells=int((diff & Eh).sum()),
                                        alpha_diff_in_equal_cells_drawn=int((diff & Eh & Dh).sum()),
                                        alpha_diff_total=int(diff.sum()))
            out["pairs"].append(rec)
            print(tex, a, b, {fk: (v["alpha_diff_in_equal_cells"], v["alpha_diff_in_equal_cells_drawn"]) for fk, v in rec["files"].items()}, flush=True)
    out["finished_utc"] = datetime.now(timezone.utc).isoformat()
    json.dump(out, open(run_dir + "/phase-silhouette.json.tmp", "w", encoding="utf-8"), indent=1)
    os.replace(run_dir + "/phase-silhouette.json.tmp", run_dir + "/phase-silhouette.json")
    print("sha256", L.sha256_file(run_dir + "/phase-silhouette.json"))


if __name__ == "__main__":
    main(sys.argv[1])
