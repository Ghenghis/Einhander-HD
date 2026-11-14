#!/usr/bin/env python3
"""s45: build the merged W7 tool copy `tools/w7m/` (claude-einhander-s45, 2026-11-14) from the two READ-ONLY lane copies.

Base = lane-s5 tools (w7-stage5/tools: FX contract boxes, 8bpp pass-through, glyph de-stair, material exclude boxes, shared
pages). Ported verbatim from lane-s4 tools (w7-stage4/tools): stage-4 swatch keys, 1-texel line strokes (thin_line_runs,
stroke_lines, soft_labels_toned strokes=), glow break weight (glow_break_pairs/_weight, float glow_mask in render),
energy_gate_smooth (job energy_smooth), job glow_break_T and page label_rects. Every new option is opt-in, so a job without
them must build byte-identically to lane-s5, and a lane-s4 job (its options, no lane-s5 keys) byte-identically to lane-s4;
that equivalence is a separate CPU check (one page each), not assumed. Each patch anchor must match exactly once."""
import hashlib
import re
import shutil
import sys
from pathlib import Path

CA = Path("C:/github/Einhander/remaster-audit/comfy-authoring")
S4, S5 = CA / "w7-stage4/tools", CA / "w7-stage5/tools"
OUT = Path("C:/github/Einhander/remaster-audit/parallel-stages-20261114/s45/tools/w7m")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def once(text, old, new, what):
    n = text.count(old)
    if n != 1:
        sys.exit(f"anchor for {what}: {n} matches")
    return text.replace(old, new)


def block(src, start, end):
    """verbatim text from the line starting with `start` up to (not including) the line starting with `end`."""
    i = src.index(start)
    j = src.index(end, i + len(start))
    return src[i:j]


def main():
    if OUT.exists():
        sys.exit(f"{OUT} exists; tools/w7m is write-once (make a w7m2 instead)")
    OUT.mkdir(parents=True)
    rec = {"inputs": {}, "outputs": {}}
    for f in ("w7lib.py", "build_w7.py"):
        rec["inputs"][f"s4/{f}"] = sha(S4 / f)
        rec["inputs"][f"s5/{f}"] = sha(S5 / f)
    for f in ("freeze_w7.py", "glyph_check.py", "verify_frozen.py", "twinkle_sim.py", "lowprio.py"):
        shutil.copy2(S5 / f, OUT / f)
        rec["inputs"][f"s5/{f}"] = sha(S5 / f)
    s4l, s5l = (S4 / "w7lib.py").read_text(encoding="utf-8"), (S5 / "w7lib.py").read_text(encoding="utf-8")
    s4b, s5b = (S4 / "build_w7.py").read_text(encoding="utf-8"), (S5 / "build_w7.py").read_text(encoding="utf-8")

    # ---------------- w7lib.py
    L = s5l
    sw4 = block(s4l, "    # stage-4 sea-base swatches", "}\n")
    L = once(L, "    'sandworn_steel_b': CA / 'w7-stage5/frozen/s5-swatches-v2/sandworn_steel_b-tileable-1024.png',\n",
             "    'sandworn_steel_b': CA / 'w7-stage5/frozen/s5-swatches-v2/sandworn_steel_b-tileable-1024.png',\n" + sw4,
             "swatches")
    L = once(L, "band=16, margin=4, cores=True, force_centres=True):",
             "band=16, margin=4, cores=True, force_centres=True, strokes=False, stroke_min_len=3):", "soft_labels_toned signature")
    L = once(L, "    cores = core_lost_texels(L, Wt, idx, np.argwhere(before)) if cores else 0   # lane-s5: FX regions skip cores\n",
             "    cores = core_lost_texels(L, Wt, idx, np.argwhere(before)) if cores else 0   # lane-s5: FX regions skip cores\n"
             "    sk = None\n"
             "    if strokes:   # s45 merge: lane-s4 world v3 1-texel line strokes (opt-in; after the cores, before the centres)\n"
             "        runs = thin_line_runs(idx, stroke_min_len)\n"
             "        sk = stroke_lines(L, Wt, idx, runs)\n"
             "        sk.update(min_len=stroke_min_len, multi_tone_only=True, bg_change_max=0.25)\n", "strokes block")
    L = once(L, "                 near_pairs=int(N.sum() - 16) // 2)\n    return L, Wt, stats\n",
             "                 near_pairs=int(N.sum() - 16) // 2)\n"
             "    if sk is not None:\n"
             "        stats.update(version='toned-v3-strokes', strokes=sk)\n"
             "    return L, Wt, stats\n", "strokes stats")
    # lane-s4 order: thin_line_runs, BG_HALF, STROKE_* constants, stroke_lines, then glow_field (shared, not ported);
    # glow_break_pairs, glow_break_weight, then swatch_source (shared, not ported)
    strokes_fns = block(s4l, "def thin_line_runs(", "def glow_field(")
    gb = block(s4l, "def glow_break_pairs(", "def swatch_source(")
    for need in ("def thin_line_runs(", "BG_HALF = 3", "STROKE_R_IN", "def stroke_lines("):
        assert need in strokes_fns, need
    assert "def glow_break_weight(" in gb
    # insert the ported functions before lane-s5's fx helpers (_crop is the first lane-s5-only function)
    L = once(L, "def _crop(box, H, W, m):", "# ---- s45 merge: ported verbatim from lane-s4 w7lib.py (opt-in features)\n" + strokes_fns + gb +
             "# ---- end of lane-s4 port\n\n\ndef _crop(box, H, W, m):", "port insertion")
    L = once(L, "        gm = (glow_mask & (c != 0))[..., None]\n        out = np.where(gm, g, out)\n",
             "        if glow_mask.dtype == bool:\n"
             "            gm = (glow_mask & (c != 0))[..., None]\n"
             "            out = np.where(gm, g, out)\n"
             "        else:   # float glow weight (glow_break_weight): blend glow and categorical labels (lane-s4 port)\n"
             "            gw = (np.clip(glow_mask, 0, 1) * (c != 0))[..., None]\n"
             "            out = out * (1 - gw) + g * gw\n", "render float glow mask")
    L = L.replace('"""W7 stage 4/5 art (claude-einhander):', '"""W7 stage 4/5 art (claude-einhander; s45 merged copy tools/w7m, see make_w7m.py):', 1)

    # ---------------- build_w7.py
    B = s5b
    B = once(B, "listed in build-record.json), never built here. Run with  python -I -B.\n",
             "listed in build-record.json), never built here. Run with  python -I -B.\n\n"
             "s45 merged copy (parallel-stages-20261114/s45/tools/w7m, make_w7m.py): lane-s5 base + lane-s4 opt-in job keys\n"
             "energy_smooth, glow_break_T, soft.strokes / soft.stroke_min_len and page label_rects (ported verbatim).\n", "doc")
    egs = s4b[s4b.index("def energy_gate_smooth("):re.compile(r"^def (?!energy_gate_smooth)", re.M).search(s4b, s4b.index("def energy_gate_smooth(") + 1).start()]
    nxt = re.compile(r"^def (?!energy_gate)", re.M).search(B, B.index("def energy_gate(") + 1).start()
    B = B[:nxt] + egs + B[nxt:]
    B = once(B, "        Lb, Wt, sstats = L7.soft_labels_toned(idx, N, crisp=tuple(soft.get('crisp', (0.42, 4.0))),\n"
                "                                             blend_sigma=soft.get('blend_sigma', 0.9), no_busy=soft.get('no_busy', False))\n",
             "        xtra = dict(strokes=True, stroke_min_len=soft.get('stroke_min_len', 3)) if soft.get('strokes') else {}  # opt-in (lane-s4 v3)\n"
             "        Lb, Wt, sstats = L7.soft_labels_toned(idx, N, crisp=tuple(soft.get('crisp', (0.42, 4.0))),\n"
             "                                             blend_sigma=soft.get('blend_sigma', 0.9), no_busy=soft.get('no_busy', False),\n"
             "                                             **xtra)\n", "strokes call")
    gbr = block(s4b, "                gbT = pg.get('glow_break_T', job.get('glow_break_T'))\n", "            else:\n                glow_info['used'] = 'shape")
    B = once(B, "                glow_info['used'] = 'glow (continuous index, RGB free of class thresholds)'\n            else:\n",
             "                glow_info['used'] = 'glow (continuous index, RGB free of class thresholds)'\n" + gbr + "            else:\n",
             "glow break + label rects")
    B = once(B, "            np.save(mdir / f'{tex}-glow16-f16.npy', glow.astype(np.float16))\n",
             "            np.save(mdir / f'{tex}-glow16-f16.npy', glow.astype(np.float16))\n"
             "            if glow_mask is not None and glow_mask.dtype != bool:\n"
             "                np.save(mdir / f'{tex}-glowweight16-u8.npy', np.rint(glow_mask * 255).astype(np.uint8))\n", "glow weight save")
    B = once(B, "                    ent.setdefault('energy', {})[str(size)] = L7_energy = energy_gate(a, idx, rgb, cls, size)\n",
             "                    ent.setdefault('energy', {})[str(size)] = L7_energy = (\n"
             "                        energy_gate_smooth if job.get('energy_smooth') else energy_gate)(a, idx, rgb, cls, size)\n", "energy select")
    (OUT / "w7lib.py").write_text(L, encoding="utf-8")
    (OUT / "build_w7.py").write_text(B, encoding="utf-8")
    shutil.copy2(Path(__file__), OUT / "make_w7m.py")
    for f in sorted(OUT.glob("*.py")):
        rec["outputs"][f.name] = sha(f)
    import json
    (OUT / "MERGE-RECORD.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(rec, indent=1))


if __name__ == "__main__":
    main()
