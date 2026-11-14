#!/usr/bin/env python3
"""claude-einhander-ui (EIN-MENU-HUD-20261114), job J-C1: comparison sheets for the cross-folder conflicts that main must
choose between (same texture key + scale authored separately in two frozen folders; both repaired candidates class-valid).

v3: v2 e15b1ab2 + crash-check review (msg_24164756): crop window chosen by combined class + visible-RGB disagreement
(RGB-only differences now count), crop basis labelled, plus one full-key overview sheet per conflict (2 px/texel).
v2: v1 6b315762 + reviewer D4 fix (sheet names carry both folders; exclusive writes; duplicate destinations refused
before any work). Its v1 input summary b0421159 is INVALID (output-path collision), so v2 takes the summary path and
sha256 as required arguments; it must be a summary rebuilt from re-verified v5 outputs.
Input: --summary / --summary-sha256. For every conflict at
--dir (default runtime-2048) it loads, read-only and sha256-checked against the summary: each folder's authored frozen
input and its snap-native candidate. It measures the two folders' difference (alpha-class pixels that differ, visible RGB
mean abs difference on pixels visible in both) and writes one sheet per key: folder A authored | folder A snap-native |
folder B authored | folder B snap-native (both conflict textures are 256 texels wide), cropped to the 64x16-texel window where A and B differ
most, 9 px/texel ATLAS SIMULATION (not a screen capture; no look acceptance; the choice is main's).
Writes ONLY <--out-root>/<UTC>/ inside the registered claude-einhander-ui output. Proposal material only."""
import argparse
import datetime
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

sys.dont_write_bytecode = True
Image.MAX_IMAGE_PIXELS = 64_000_000
RA = Path("C:/github/Einhander/remaster-audit")
CA = RA / "comfy-authoring"
UI_OUT = Path("C:/github/Einhander/.claude/worktrees/xenodochial-snyder-093665/remaster-audit/claude-einhander-ui")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-root", default=str(UI_OUT / "conflicts"))
    ap.add_argument("--dir", default="runtime-2048")
    ap.add_argument("--summary", required=True, help="v2: a re-verified integration summary inside the UI output")
    ap.add_argument("--summary-sha256", required=True)
    a = ap.parse_args()
    SUMMARY, SUMMARY_SHA256 = Path(a.summary).resolve(), a.summary_sha256
    out_root = Path(a.out_root).resolve()
    if os.path.commonpath([str(out_root).lower(), str(UI_OUT.resolve()).lower()]) != str(UI_OUT.resolve()).lower():
        raise SystemExit(f"--out-root {out_root} is outside the registered output {UI_OUT}")
    t0 = time.time()
    assert sha(SUMMARY) == SUMMARY_SHA256, "integration summary changed"
    summ = json.loads(SUMMARY.read_text(encoding="utf-8"))
    items = [c for c in summ["cross_folder_conflicts"]["items"] if c["dir"] == a.dir]
    for c in items:
        assert len(c["folders"]) == 2, ("v2 compares exactly two folders", c)

    def sheet_name(c):
        return (f"{c['dir']}__{c['key'][:-4]}__{c['folders'][0].replace('/', '_')}__vs__"
                f"{c['folders'][1].replace('/', '_')}.png")
    planned = [sheet_name(c).lower() for c in items]
    planned += ["overview__" + n for n in planned]
    assert len(planned) == len(set(planned)), "duplicate sheet destinations"   # refused before the run folder exists
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = out_root / stamp
    rd.mkdir(parents=True, exist_ok=False)
    (rd / "pid.txt").write_text(f"{os.getpid()} {stamp}\n", encoding="utf-8")
    members = {}
    for u in summ["units_detail"]:
        for m in u["members"]:
            if not m.get("built", True):
                continue
            members[(u["folder"], u["dir"], m["file"].split("/")[-1])] = (u, m)
    rows = []
    for c in items:
        side = []
        for folder in c["folders"]:
            u, m = members[(folder, c["dir"], c["key"])]
            lane, fold = folder.split("/", 1)
            src = CA / lane / "frozen" / fold / m["file"]
            cand = UI_OUT / m["candidate"]
            assert sha(src) == m["input_sha256"] and sha(cand) == m["candidate_sha256"], (folder, c["key"])
            with Image.open(src) as im:
                au = np.asarray(im.convert("RGBA"))
            with Image.open(cand) as im:
                ca = np.asarray(im.convert("RGBA"))
            side.append(dict(folder=folder, src=src, cand=cand, authored=au, candidate=ca, u=u, m=m))
        A, B = side
        assert A["candidate"].shape == B["candidate"].shape
        ca, cb = A["candidate"], B["candidate"]
        both = (ca[..., 3] != 0) & (cb[..., 3] != 0)
        cls_diff = ca[..., 3] != cb[..., 3]
        rgb_diff = np.abs(ca[..., :3].astype(np.int16) - cb[..., :3].astype(np.int16)).mean(-1)[both]
        H, W = ca.shape[:2]
        # native class/colour from the folder-A native authority recorded in the summary (same words for both folders)
        wsha = A["m"]["words_sha256"]   # verified summary (builder 109218cf) records words per member
        assert wsha == B["m"]["words_sha256"], (c["key"], "folders disagree on native words")
        s = W // 256
        assert s >= 1 and W == 256 * s and H % s == 0, (c["key"], W, H)
        TW, TH = W // s, H // s
        ch, cw = min(16, TH), min(64, TW)
        # v3: combined per-cell disagreement score = fraction of the cell's pixels whose class differs
        #     + mean |RGB difference| / 255 over the cell's pixels visible in BOTH candidates (RGB-only differences count)
        rgbmap = np.where(both, np.abs(ca[..., :3].astype(np.int16) - cb[..., :3].astype(np.int16)).mean(-1), 0.0)
        cls_cell = cls_diff.reshape(TH, s, TW, s).mean(axis=(1, 3))
        nboth = both.reshape(TH, s, TW, s).sum(axis=(1, 3))
        rgb_cell = rgbmap.reshape(TH, s, TW, s).sum(axis=(1, 3)) / np.maximum(nboth, 1) / 255.0
        diffcell = (cls_cell + rgb_cell).astype(np.float32)
        del rgbmap
        cs = ndi.uniform_filter(diffcell, size=(ch, cw), mode="constant")
        cy0, cx0 = np.unravel_index(int(np.argmax(cs)), cs.shape)
        y0 = int(min(max(cy0 - ch // 2, 0), TH - ch)); x0 = int(min(max(cx0 - cw // 2, 0), TW - cw))

        def sim(arr):
            crop = arr[y0 * s:(y0 + ch) * s, x0 * s:(x0 + cw) * s].astype(np.float32)
            v = np.where(crop[..., 3:4] > 0, crop[..., :3], 24.0)
            return Image.fromarray(v.astype(np.uint8)).resize((cw * 9, ch * 9), Image.BOX)
        tiles = [(f"{A['folder']} authored", A["authored"]), (f"{A['folder']} snap-native", ca),
                 (f"{B['folder']} authored", B["authored"]), (f"{B['folder']} snap-native", cb)]
        sheet = Image.new("RGB", (cw * 9, len(tiles) * (ch * 9 + 16) + 14), (0, 0, 0))
        dr = ImageDraw.Draw(sheet)
        for i, (lab, arr) in enumerate(tiles):
            sheet.paste(sim(arr), (0, i * (ch * 9 + 16) + 16))
            dr.text((4, i * (ch * 9 + 16) + 2), f"{lab} | {c['key']} texels {[x0, y0, x0 + cw, y0 + ch]}", fill=(255, 255, 0))
        dr.text((4, sheet.height - 12), "ATLAS SIMULATION, 9 px/texel, crop = max class+visible-RGB disagreement "
                "(not a screen capture; main chooses)", fill=(160, 160, 160))
        fn = rd / sheet_name(c)
        with open(fn, "xb") as fh:   # exclusive create; never overwrite
            sheet.save(fh, format="PNG")
        # v3: full-key overview (whole texture, 2 px/texel, all four tiles stacked) so main can judge RGB everywhere
        ov_w, ov_h = TW * 2, TH * 2

        def whole(arr):
            v = np.where(arr[..., 3:4] > 0, arr[..., :3], 24).astype(np.uint8)
            return Image.fromarray(v).resize((ov_w, ov_h), Image.BOX)
        ovs = Image.new("RGB", (ov_w, len(tiles) * (ov_h + 14) + 14), (0, 0, 0))
        dro = ImageDraw.Draw(ovs)
        for i, (lab, arr) in enumerate(tiles):
            ovs.paste(whole(arr), (0, i * (ov_h + 14) + 14))
            dro.text((2, i * (ov_h + 14) + 1), f"{lab} | {c['key']} FULL", fill=(255, 255, 0))
        dro.text((2, ovs.height - 12), "FULL-KEY OVERVIEW, 2 px/texel ATLAS SIMULATION", fill=(160, 160, 160))
        fno = rd / ("overview__" + sheet_name(c))
        with open(fno, "xb") as fh:
            ovs.save(fh, format="PNG")
        rows.append(dict(key=c["key"], dir=c["dir"], folders=c["folders"],
                         candidates={x["folder"]: dict(path=x["m"]["candidate"], sha256=x["m"]["candidate_sha256"],
                                                      input=str(x["src"]), input_sha256=x["m"]["input_sha256"]) for x in side},
                         class_pixels_differing=int(cls_diff.sum()), pixels=int(H * W),
                         visible_both_rgb_mean_abs_diff=round(float(rgb_diff.mean()), 3) if rgb_diff.size else None,
                         crop_texels=[x0, y0, x0 + cw, y0 + ch], crop_basis="max(class-diff fraction + visible-RGB diff/255) per cell",
                         sheet=dict(path=fn.name, sha256=sha(fn)), overview=dict(path=fno.name, sha256=sha(fno))))
        print(c["key"], c["dir"], "class px differing", rows[-1]["class_pixels_differing"], flush=True)
        del side, A, B, ca, cb, both, cls_diff, rgb_diff
    out = dict(run=stamp, owner="claude-einhander-ui", task="EIN-MENU-HUD-20261114", job="J-C1 v3 conflict sheets (v2 e15b1ab2 + combined class/visible-RGB crop score + full-key overview)",
               status="COMPARISON MATERIAL ONLY: main chooses one folder per key; atlas simulations; nothing installed",
               tool_sha256=sha(Path(__file__)), summary_sha256=SUMMARY_SHA256, dir=a.dir, rows=rows,
               seconds=round(time.time() - t0, 1))
    (rd / "result.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print("done", out["seconds"], "s result", sha(rd / "result.json"), flush=True)


if __name__ == "__main__":
    main()
