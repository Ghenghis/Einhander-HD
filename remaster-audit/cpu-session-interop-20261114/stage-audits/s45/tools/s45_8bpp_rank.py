#!/usr/bin/env python3
"""s45 step 3 (claude-einhander-s45, EIN-S5-WHOLE-CELL-20261114): READ-ONLY ranking of the static 8bpp interpretations of the
three Duerer 4bpp-page sub-images (1F11EE57 v80-255, BFC445B0 v144-223, 3D108041 v176-255; lane-s5 alt8_mask blocks).

Evidence only, no new identity art. For each static depth-1 page key of member 3/16 / 3/17 whose half-page holds one of those
4bpp pages (from source-map 20261114T133831Z: E6BFD1DB@448 L=1F11EE57, 269AFAAD@384 R=1F11EE57, 87FCFE63@512 R=BFC445B0,
AEC51081@640 R=3D108041, A3D0E675@704 L=3D108041) and every non-zero static 256-entry CLUT paired with it:
  * decode the 8bpp indices over the sub-image (the alt8 blocks mapped into 8bpp u: two 8bpp texels per word);
  * coherence metrics: mean |grad| of RGB along u and v, share of texels whose CLUT word is 0 (cutout) / STP,
    distinct indices used, and the same metrics for the 4bpp reading of the same words through the page's review CLUT;
  * REFERENCE-ONLY review crops (nearest x4) per candidate, labelled, under review/.
Writes ONLY remaster-audit/parallel-stages-20261114/s45/duerer-8bpp/<UTC>/. Below normal, one CPU, numpy only."""
import datetime
import hashlib
import json
import os
import shutil
import zlib
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

RA = Path("C:/github/Einhander/remaster-audit")
OUT = RA / "parallel-stages-20261114/s45/duerer-8bpp"
SD = RA / "fullgame-prep/static-extraction/stages/stage5"
DM = RA / "comfy-authoring/w7-stage5/frozen/s5-duerer-armour-v2/manifest.json"
DM_SHA = "4d25b6210835ea27537e0f5a075a3787bbb8e5ef10eca08172d1f04dec889ed8"
CAND = {  # 8bpp page TEX -> (texpage x, which half holds the Duerer 4bpp page, 4bpp TEX)
    "E6BFD1DB": (448, "L", "1F11EE57"), "269AFAAD": (384, "R", "1F11EE57"),
    "87FCFE63": (512, "R", "BFC445B0"),
    "AEC51081": (640, "R", "3D108041"), "A3D0E675": (704, "L", "3D108041"),
}


def crc(b):
    return "%08X" % (zlib.crc32(b) & 0xFFFFFFFF)


def sha_f(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rgb_of(words):
    w = np.asarray(words, np.uint32)
    return np.stack([(w & 31) * 255 // 31, ((w >> 5) & 31) * 255 // 31, ((w >> 10) & 31) * 255 // 31], -1).astype(np.float32)


def metrics(idx, clut, mask):
    """idx: HxW indices, clut: entries (u16), mask: HxW bool (texels in the sub-image)."""
    cw = clut[idx]
    rgb = rgb_of(cw)
    vis = (cw != 0) & mask
    gu = np.abs(np.diff(rgb, axis=1)).mean(-1)
    gv = np.abs(np.diff(rgb, axis=0)).mean(-1)
    mu = vis[:, 1:] & vis[:, :-1]
    mv = vis[1:, :] & vis[:-1, :]
    return dict(texels=int(mask.sum()), cutout_share=round(float(((cw == 0) & mask).sum() / max(mask.sum(), 1)), 4),
                stp_share=round(float((((cw & 0x8000) != 0) & mask).sum() / max(mask.sum(), 1)), 4),
                distinct_indices=int(len(np.unique(idx[mask]))),
                index_range=[int(idx[mask].min()), int(idx[mask].max())] if mask.any() else None,
                mean_grad_u=round(float(gu[mu].mean()), 2) if mu.any() else None,
                mean_grad_v=round(float(gv[mv].mean()), 2) if mv.any() else None)


def main():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([me.cpu_affinity()[-1]])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = OUT / stamp
    (rd / "review").mkdir(parents=True, exist_ok=False)
    (rd / "pid.txt").write_text(f"{os.getpid()} {stamp}\n", encoding="utf-8")
    print("PID", os.getpid(), "run", rd, flush=True)
    shutil.copy2(Path(__file__), rd / Path(__file__).name)
    assert sha_f(DM) == DM_SHA, "Duerer v2 manifest changed"
    dm = json.loads(DM.read_text(encoding="utf-8"))
    keys = json.loads((SD / "keys.json").read_text(encoding="utf-8"))
    res = dict(run=stamp, owner="claude-einhander-s45", duerer_manifest_sha256=DM_SHA, pages={},
               status="EVIDENCE ONLY; static predictions; reference crops are not HD art and not identity; no live data")
    for tex4 in ("1F11EE57", "BFC445B0", "3D108041"):
        page = dm["pages"][tex4]
        reg = next(r for r in page["regions"] if r.get("kind") == "native-8bpp-pending")
        m4 = np.zeros((256, 256), bool)
        for bx, by in reg["blocks8"]:
            m4[by * 8:by * 8 + 8, bx * 8:bx * 8 + 8] = True
        words4 = np.frombuffer(Path(page["source"]["path"]).read_bytes(), "<u2").reshape(256, 64)
        rk = page["rendered_keys"][0]
        clut4 = np.frombuffer((SD / "keys" / f"{rk['key']}.clut.bin").read_bytes(), "<u2")
        idx4 = np.stack([(words4 >> (4 * k)) & 0xF for k in range(4)], -1).reshape(256, 256)
        P = dict(region_texels_4bpp=int(m4.sum()), review_4bpp=dict(key=rk["key"], **metrics(idx4, clut4, m4)), candidates=[])
        wordmask = m4.reshape(256, 64, 4).any(-1)  # words touched by the sub-image
        for tex8, (tx, half, t4) in CAND.items():
            if t4 != tex4:
                continue
            for e in keys:
                if not e["key"].startswith(tex8 + "-") or e.get("depth") != 1:
                    continue
                kw = (SD / "keys" / f"{e['key']}.words.bin").read_bytes()
                kc = (SD / "keys" / f"{e['key']}.clut.bin").read_bytes()
                assert crc(kw) == tex8 and crc(kc) == e["key"][9:]
                w8 = np.frombuffer(kw, "<u2").reshape(256, 128)
                clut8 = np.frombuffer(kc, "<u2")
                idx8 = np.stack([w8 & 0xFF, w8 >> 8], -1).reshape(256, 256)
                m8 = np.zeros((256, 256), bool)
                off = 0 if half == "L" else 64
                m8[:, off * 2:(off + 64) * 2] = np.repeat(wordmask, 2, axis=1)
                rec = dict(key=e["key"], texpage_x=tx, half=half, clut_xy=e.get("clut_xy"), pair_count=e.get("pair_count"),
                           pal_all_zero=e.get("pal_all_zero"), u8_range=[off * 2 + int(np.where(wordmask.any(0))[0].min()) * 2,
                                                                         off * 2 + int(np.where(wordmask.any(0))[0].max()) * 2 + 1],
                           v_range=[int(np.where(wordmask.any(1))[0].min()), int(np.where(wordmask.any(1))[0].max())])
                if not e.get("pal_all_zero"):
                    rec.update(metrics(idx8, clut8, m8))
                    ys, xs = np.where(m8)
                    crop = rgb_of(clut8[idx8[ys.min():ys.max() + 1, xs.min():xs.max() + 1]]).astype(np.uint8)
                    im = Image.fromarray(crop).resize((crop.shape[1] * 4, crop.shape[0] * 4), Image.NEAREST)
                    canvas = Image.new("RGB", (im.width, im.height + 14), (0, 0, 0))
                    canvas.paste(im, (0, 14))
                    ImageDraw.Draw(canvas).text((2, 1), f"REFERENCE ONLY {e['key']} @{tx} {half} clut{e.get('clut_xy')}", fill=(255, 255, 0))
                    fn = rd / "review" / f"{tex4}-as-{e['key']}.png"
                    canvas.save(fn)
                    rec["review_png"] = fn.name
                P["candidates"].append(rec)
        ys, xs = np.where(m4)
        crop4 = rgb_of(clut4[idx4[ys.min():ys.max() + 1, xs.min():xs.max() + 1]]).astype(np.uint8)
        Image.fromarray(crop4).resize((crop4.shape[1] * 4, crop4.shape[0] * 4), Image.NEAREST).save(rd / "review" / f"{tex4}-as-4bpp-{rk['key']}.png")
        res["pages"][tex4] = P
    (rd / "result.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for t, P in res["pages"].items():
        r4 = P["review_4bpp"]
        print(t, "4bpp", r4["mean_grad_u"], r4["mean_grad_v"], "cut", r4["cutout_share"])
        for c in P["candidates"]:
            print("   ", c["key"], c["texpage_x"], c["half"], c["clut_xy"], "pairs", c["pair_count"], "zero" if c["pal_all_zero"] else "",
                  c.get("mean_grad_u"), c.get("mean_grad_v"), "cut", c.get("cutout_share"), "idx", c.get("index_range"), "u8", c["u8_range"], "v", c["v_range"])
    print("run", stamp, "result", sha_f(rd / "result.json"))


if __name__ == "__main__":
    main()
