#!/usr/bin/env python3
"""Native-word/CLUT class audit of a private HD pack (claude-einhander). Read-only on every input: frozen files are
opened for reading only. CPU only, below-normal priority, ONE process, ONE image decoded at a time. No GPU.

For every replacement PNG in the pack (emissive masks excluded: they are not class textures):
  1. Native source:
     * exact-region keys (pack ExactRegions.tsv): the pack-bound words/valid/CLUT dumps (the loader's own proof);
     * page/strip keys: the first dump found, in order, in REMASTER_STAGING stock, root's derived Uhu sources, frozen-set
       source/ folders, and retained capture folders (dev-center-evidence/.../hd-on_rewind-off/*/), that PASSES:
         CRC32(words LE) == key[:8], CRC32(CLUT) == key[9:] (depth 0/1) or key[9:] == 00000000 (depth 2),
         every word known (valid.bin all 1, or source.json known_words == total_words),
         byte sizes consistent with width_words x height (x depth) and the CLUT size.
     A key with no passing dump is NOT CHECKED (reason recorded). Stock PNG alpha is never used as the reference.
  2. Native class per texel: 4bpp/8bpp index -> CLUT word, 15bpp -> the word; class 0 if the word is 0x0000,
     255 if bit 15 is set, else 127 (the HD_FS categorical convention).
  3. Pack PNG alpha at pixel floor((i+0.5)*scale) for every native texel, scale = PNG size / native texel size
     (integer and equal on both axes, else NOT CHECKED: scale).
  4. Mismatch counts by (native, png) pair over {0,127,255}; first examples.
Writes class-audit.json (+ prints a summary)."""
import argparse
import collections
import ctypes
import hashlib
import json
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
E = Path("C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112")
STOCK = Path("C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements")
UHU = Path("C:/github/Einhander/remaster-audit/runtime-review/project-completion-20261114/derived-uhu-source")
CA = Path("C:/github/Einhander/remaster-audit/comfy-authoring")
HERE = Path(__file__).resolve().parent


def below():
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = ctypes.c_void_p
    k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    return bool(k.SetPriorityClass(k.GetCurrentProcess(), 0x4000))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def crc(b):
    return f"{zlib.crc32(b) & 0xFFFFFFFF:08X}"


def classes_of_words(words):
    w = words.astype(np.uint32)
    return np.where(w == 0, 0, np.where(w & 0x8000, 255, 127)).astype(np.uint8)


def native_classes(words_b, clut_b, width_words, height, depth):
    words = np.frombuffer(words_b, dtype="<u2").reshape(height, width_words)
    if depth == 2:
        return classes_of_words(words)
    pal_cls = classes_of_words(np.frombuffer(clut_b, dtype="<u2"))
    if depth == 0:
        idx = np.zeros((height, width_words * 4), dtype=np.uint8)
        for k in range(4):
            idx[:, k::4] = (words >> (4 * k)) & 15
    else:
        idx = np.zeros((height, width_words * 2), dtype=np.uint8)
        for k in range(2):
            idx[:, k::2] = (words >> (8 * k)) & 255
    return pal_cls[idx]


def try_dump(d, key, regions):
    """Return (source dict, classes) if the dump in folder d proves key, else (None, reason)."""
    w, c, v, sj = (d / f"{key}.words.bin", d / f"{key}.clut.bin", d / f"{key}.valid.bin", d / f"{key}.source.json")
    if not w.exists():
        return None, "absent"
    if key in regions:
        x, y, ww, h, depth, cx, cy = regions[key]
    else:
        if not sj.exists():
            return None, "no source.json"
        meta = json.loads(sj.read_text(encoding="utf-8"))
        ww, h, depth = meta.get("width_words"), meta.get("height"), meta.get("depth")
        if ww is None or h is None or depth is None:
            return None, "source.json lacks shape"
        if meta.get("known_words") is not None and meta.get("known_words") != meta.get("total_words"):
            return None, "incomplete words (known < total)"
    wb = w.read_bytes()
    if len(wb) != ww * h * 2:
        return None, f"words size {len(wb)} != {ww}x{h}x2"
    colors = 16 if depth == 0 else (256 if depth == 1 else 0)
    cb = c.read_bytes() if c.exists() else b""
    if colors and len(cb) < colors * 2:
        return None, f"clut size {len(cb)} < {colors * 2}"
    cb = cb[:colors * 2]
    if v.exists():
        vb = v.read_bytes()
        if len(vb) == ww * h and any(b != 1 for b in vb):
            return None, "valid.bin has unknown words"
    if crc(wb) != key[:8]:
        return None, f"words CRC {crc(wb)} != {key[:8]}"
    if colors and crc(cb) != key[9:]:
        return None, f"clut CRC {crc(cb)} != {key[9:]}"
    if not colors and key[9:] != "00000000":
        return None, "15bpp key with non-zero palette hash"
    return dict(dir=str(d), words_sha256=hashlib.sha256(wb).hexdigest(),
                clut_sha256=hashlib.sha256(cb).hexdigest() if colors else None,
                width_words=ww, height=h, depth=depth), native_classes(wb, cb, ww, h, depth)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, default=E / "world-integrated-crisp-v3")
    ap.add_argument("--out", type=Path, default=HERE / "class-audit-world-integrated-crisp-v3.json")
    a = ap.parse_args()
    pri = below()
    cand = json.loads((a.pack / "candidate.json").read_text(encoding="utf-8"))
    pack_dir = a.pack / "pack"
    repl = pack_dir / "einhander-texture-replacements"
    regions = {}
    for line in (pack_dir / "ExactRegions.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        p = line.split()
        if len(p) == 8:
            regions[p[0]] = tuple(int(x) for x in p[1:])
    emissive = {Path(f.get("name", f.get("composed_path", ""))).name for f in cand.get("emissive_files", [])}
    files = sorted(f["name"] for f in cand["files"])

    set_dirs = sorted(CA.glob("*/frozen/*/source"))
    cap_dirs = sorted(p for p in E.glob("*/hd-on_rewind-off/*") if p.is_dir())
    order = [STOCK, UHU] + set_dirs

    rows, summary = [], collections.Counter()
    pairs_total = collections.Counter()
    for n, name in enumerate(files):
        key = name[:-4]
        rec = dict(key=key, region=key in regions)
        png = repl / name
        if name in emissive:
            rec.update(status="EXCLUDED", reason="emissive mask")
            rows.append(rec); summary["excluded"] += 1
            continue
        src, cls, reasons = None, None, []
        search = [pack_dir] if key in regions else order
        for d in search:
            s, r = try_dump(d, key, regions)
            if s:
                src, cls = s, r
                break
            if r != "absent":
                reasons.append(f"{d.name}: {r}")
        if src is None and key not in regions:
            for d in cap_dirs:
                s, r = try_dump(d, key, regions)
                if s:
                    src, cls = s, r
                    break
                if r != "absent":
                    reasons.append(f"{d.parent.parent.name}/{d.name}: {r}")
        if src is None:
            rec.update(status="NOT CHECKED", reason="no passing native dump" + (f" ({'; '.join(reasons[:3])})" if reasons else " (none found)"))
            rows.append(rec); summary["not_checked_no_source"] += 1
            continue
        with Image.open(png) as im:
            W, H = im.size
            has_alpha = im.mode in ("RGBA", "LA") or "transparency" in im.info
            alpha = np.asarray(im.convert("RGBA"))[..., 3]
        th, tw = cls.shape
        sx, sy = W / tw, H / th
        rec.update(png_sha256=sha(png), png_size=[W, H], native_texels=[tw, th], source=src, png_has_alpha=has_alpha)
        if sx != sy or sx != int(sx):
            rec.update(status="NOT CHECKED", reason=f"scale {sx}x{sy} not integer/equal")
            rows.append(rec); summary["not_checked_scale"] += 1
            del alpha
            continue
        s = int(sx)
        cx = (np.arange(tw) * s + s // 2)
        cy = (np.arange(th) * s + s // 2)
        got = alpha[np.ix_(cy, cx)]
        del alpha
        bad = got != cls
        pairs = collections.Counter(zip(cls[bad].tolist(), got[bad].tolist()))
        ys, xs = np.nonzero(bad)
        rec.update(status="MISMATCH" if bad.any() else "PASS", scale=s, texels=int(cls.size), mismatches=int(bad.sum()),
                   pairs={f"{k[0]}->{k[1]}": v for k, v in sorted(pairs.items())},
                   examples=[[int(x), int(y), int(cls[y, x]), int(got[y, x])] for x, y in zip(xs[:6], ys[:6])])
        pairs_total.update(pairs)
        summary["pass" if not bad.any() else "mismatch_keys"] += 1
        summary["texels_checked"] += int(cls.size)
        summary["texel_mismatches"] += int(bad.sum())
        rows.append(rec)
        if (n + 1) % 200 == 0:
            print(f"{n + 1}/{len(files)}", dict(summary), flush=True)

    origin = {f["name"][:-4]: f.get("origin") for f in cand["files"]}
    bad_rows = [r for r in rows if r.get("status") == "MISMATCH"]
    out = dict(
        pack=str(a.pack), candidate_sha256=sha(a.pack / "candidate.json"), checker=dict(path=str(Path(__file__)), sha256=sha(Path(__file__))),
        below_normal=pri, one_process=True, convention="alpha at pixel floor((i+0.5)*scale) vs native class from CRC-proven words/CLUT",
        summary=dict(files=len(files), **summary, mismatch_pairs_total={f"{k[0]}->{k[1]}": v for k, v in sorted(pairs_total.items())},
                     mismatch_keys_by_origin=dict(collections.Counter(origin[r["key"]] for r in bad_rows)),
                     transparency_errors_keys=sum(1 for r in bad_rows if any(k.startswith("0->") or k.endswith("->0") for k in r["pairs"])),
                     source_dirs=dict(collections.Counter(Path(r["source"]["dir"]).name if Path(r["source"]["dir"]).name != "einhander-texture-replacements" else "stock"
                                                          for r in rows if r.get("source")))),
        rows=rows)
    a.out.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=1))


if __name__ == "__main__":
    main()
