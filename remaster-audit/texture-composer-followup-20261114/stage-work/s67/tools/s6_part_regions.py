#!/usr/bin/env python3
"""s67: candidate PART regions of the Stage 6 hull/sprite pages from native words only (LIGHT CPU, read-only).

For each Stage 6 page TEX named by CR-S6-3 (GP0 part masks) a texel is 'visible' when its 4bpp index maps to a non-zero
CLUT word under EVERY selected CLUT of that TEX that has a transparent (0x0000) entry (from the s67 selection map). 8-connected visible components >= MIN texels
give candidate part rects (u0, v0, u1, v1 inclusive, texel units). These are what a GP0 textured-polygon dump must resolve:
which components are drawn as separate polygons, which are welded sheets, their draw order and on-screen size.
Known effect-sprite rects of the fx-v2 manifests are tagged so hull parts and gas plumes stay separate.
Not a part mask: native texels cannot tell a hull plate seam from a painted line. This only sizes and anchors CR-S6-3.
Writes ONLY C:/github/Einhander/remaster-audit/parallel-stages-20261114/s67/stage6/part-regions-<UTC>.json."""
import datetime
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path("C:/github/Einhander")
S67 = ROOT / "remaster-audit/parallel-stages-20261114/s67"
S6 = ROOT / "remaster-audit/comfy-authoring/w7-stage6"
TEX = ["CB07BBCB", "43C26C42", "61A869E5", "8F498326", "F07625EE", "03F5CF11", "A5969BC9", "20961255", "E0849F81"]
MIN = 12


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def components(vis):
    h, w = vis.shape
    lab = np.zeros((h, w), np.int32)
    comps, n = [], 0
    for y in range(h):
        for x in range(w):
            if not vis[y, x] or lab[y, x]:
                continue
            n += 1
            stack, cnt, u0, v0, u1, v1 = [(y, x)], 0, x, y, x, y
            lab[y, x] = n
            while stack:
                cy, cx = stack.pop()
                cnt += 1
                u0, u1, v0, v1 = min(u0, cx), max(u1, cx), min(v0, cy), max(v1, cy)
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and vis[ny, nx] and not lab[ny, nx]:
                            lab[ny, nx] = n
                            stack.append((ny, nx))
            comps.append(dict(id=n, texels=cnt, rect=[u0, v0, u1, v1]))
    return comps


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    smap_p = sorted((S67 / "stage6").glob("selection-map-*.json"))[-1]
    smap = json.loads(smap_p.read_text(encoding="utf-8"))
    fx = {}
    for d in ("stage6-vram704-0-20961255-fx-v2", "stage6-vram384-0-8F498326-fx-v2", "stage6-vram320-0-43C26C42-fx-v2"):
        base = S6 / ("failed" if "43C26C42" in d else "frozen") / d / "manifest.json"
        if base.exists():
            m = json.loads(base.read_text(encoding="utf-8"))
            fx[m.get("texture_crc") or d.split("-")[3]] = dict(rects=(m.get("effect_sprites") or {}).get("rects"), source=str(base.relative_to(ROOT)))
    out = {}
    for tex in TEX:
        rows = [r for r in smap["rows"] if r["tex"] == tex]
        w = np.frombuffer((ROOT / rows[0]["words"]).read_bytes(), "<u2").reshape(256, 64)
        idx = np.zeros((256, 256), np.uint8)
        for k in range(4):
            idx[:, k::4] = (w >> (4 * k)) & 0xF
        per_clut, masks = {}, []
        for r in rows:
            cw = np.frombuffer((ROOT / r["clut_file"]).read_bytes(), "<u2")
            v = (cw != 0)[idx]
            per_clut[r["clut"]] = dict(zero_entries=int((cw == 0).sum()), cutout_texels=int((~v).sum()))
            if (cw == 0).any():
                masks.append(v)
        # intersection over CLUTs that have a transparent entry (all-opaque palettes cannot separate parts)
        vis = np.logical_and.reduce(masks) if masks else np.ones_like(idx, bool)
        comps = [c for c in components(vis) if c["texels"] >= MIN]
        frs = (fx.get(tex) or {}).get("rects") or []
        for c in comps:
            u0, v0, u1, v1 = c["rect"]
            c["in_effect_rect"] = any(u0 >= a and v0 >= b and u1 <= cc and v1 <= dd for a, b, cc, dd in frs)
        comps.sort(key=lambda c: -c["texels"])
        out[tex] = dict(keys=[r["key"] for r in rows], per_clut=per_clut, cluts_used_for_mask=len(masks),
                        visible_texels=int(vis.sum()), components_ge_min=len(comps),
                        effect_rects=frs, effect_rect_source=(fx.get(tex) or {}).get("source"),
                        largest=comps[:40], words=rows[0]["words"], words_sha256=rows[0]["words_sha256"])
    res = dict(run=stamp, owner="claude-einhander-s67", task="EIN-S6-WHOLE-CELL-20261114",
               selection_map=dict(path=str(smap_p.relative_to(ROOT)).replace("\\", "/"), sha256=sha(smap_p)),
               rule=(f"visible = index maps to a non-zero CLUT word under EVERY selected CLUT that has a transparent entry; "
                     f"8-connected components >= {MIN} texels (run 134358Z with the union rule was INVALID: all-opaque CLUTs)"),
               pages=out, status="DATA ONLY; candidate part regions for CR-S6-3 sizing, NOT part masks")
    dst = S67 / "stage6" / f"part-regions-{stamp}.json"
    dst.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for t, p in out.items():
        print(t, "keys", len(p["keys"]), "vis", p["visible_texels"], "comps", p["components_ge_min"],
              "fx_rects", p["effect_rects"], "top", [(c["texels"], c["rect"], c["in_effect_rect"]) for c in p["largest"][:4]])
    print("out", dst, sha(dst))


if __name__ == "__main__":
    main()
