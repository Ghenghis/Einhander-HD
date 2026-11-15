#!/usr/bin/env python3
"""Crop the UV rectangles a key used inside a native-screen rect from the current pack PNG (claude-einhander).
Read-only on inputs; writes one review sheet. Usage: crop_uv_sheet.py --rect x0 y0 x1 y1 --frames F0 F1 --keys K.. --out sheet.png LOG"""
import argparse, ctypes, json
from pathlib import Path
from PIL import Image, ImageDraw
PACK = Path("C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112/frozen-w3-lit-v1/pack/einhander-texture-replacements")
try:
    k = ctypes.windll.kernel32; k.GetCurrentProcess.restype = ctypes.c_void_p
    k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]; k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)
except Exception: pass
ap = argparse.ArgumentParser(); ap.add_argument("--rect", type=int, nargs=4); ap.add_argument("--frames", type=int, nargs=2)
ap.add_argument("--keys", nargs="+"); ap.add_argument("--out", type=Path); ap.add_argument("log", type=Path); a = ap.parse_args()
x0, y0, x1, y1 = a.rect; want = set(a.keys); uvs = {k: set() for k in want}
with open(a.log, encoding="utf-8") as f:
    for line in f:
        if '"source_draw_query_matched"' not in line: continue
        r = json.loads(line)
        if r["key"] not in want or not (a.frames[0] <= r["frame"] <= a.frames[1]): continue
        xs = [v[0] for v in r["xy"]]; ys = [v[1] % 240 for v in r["xy"]]
        if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1: continue
        uvs[r["key"]].add(tuple(r["uv_bounds"]))
tiles = []
for key in a.keys:
    p = PACK / f"{key}.png"
    if not p.exists(): continue
    im = Image.open(p).convert("RGBA"); s = im.width // 256 if im.width >= 256 else 1
    for (u0, v0, u1, v1) in sorted(uvs[key])[:6]:
        c = im.crop((u0 * s, v0 * s, (u1 + 1) * s, (v1 + 1) * s)); c.putalpha(255)
        c.thumbnail((256, 256), Image.NEAREST); tiles.append((f"{key} uv{[u0,v0,u1,v1]} {im.width}", c))
    im.close()
W = 280; sheet = Image.new("RGB", (W * 4, 300 * ((len(tiles) + 3) // 4) or 300), (40, 40, 40)); d = ImageDraw.Draw(sheet)
for i, (lab, c) in enumerate(tiles):
    x, y = (i % 4) * W, (i // 4) * 300; sheet.paste(c, (x + 10, y + 30)); d.text((x + 4, y + 4), lab, fill=(255, 255, 0))
sheet.save(a.out); print(a.out, len(tiles), {k: sorted(v) for k, v in uvs.items()})
