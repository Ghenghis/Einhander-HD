#!/usr/bin/env python3
"""Which texture keys draw inside a native-screen rectangle (claude-einhander). Read-only, below normal.
Scans retained ein-research-v1 capture.jsonl draw logs (source_draw_query_matched / replacement_gl_draw_submitted).
A draw's native screen bbox comes from its 'xy' vertices (y taken modulo 240 for the double-buffered display).
Reports per key: draws overlapping the rectangle, frames seen, source kind, whether an HD replacement was used
(replacement_size != [0,0]) and the replacement size. Usage:
  locate_screen_region.py --rect x0 y0 x1 y1 [--frames F0 F1] --out result.json LOG [LOG ...]"""
import argparse
import collections
import ctypes
import json
from pathlib import Path


def below():
    try:
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)
    except Exception:  # noqa: BLE001
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rect", type=int, nargs=4, required=True)
    ap.add_argument("--frames", type=int, nargs=2, default=None)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("logs", nargs="+", type=Path)
    a = ap.parse_args()
    below()
    x0, y0, x1, y1 = a.rect
    res = {}
    for log in a.logs:
        keys = collections.defaultdict(lambda: dict(draws=0, frames=set(), kinds=set(), replaced=0, native=0, sizes=set(), area=0))
        with open(log, encoding="utf-8") as f:
            for line in f:
                if '"xy"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                fr = r.get("frame", 0)
                if a.frames and not (a.frames[0] <= fr <= a.frames[1]):
                    continue
                xs = [v[0] for v in r["xy"]]
                ys = [v[1] % 240 for v in r["xy"]]
                bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
                if bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1:
                    continue
                k = keys[r["key"]]
                k["draws"] += 1
                k["frames"].add(fr)
                k["kinds"].add(r.get("source_kind"))
                rs = tuple(r.get("replacement_size") or (0, 0))
                k["sizes"].add(rs)
                k["replaced" if rs != (0, 0) else "native"] += 1
                k["area"] = max(k["area"], (bx1 - bx0) * (by1 - by0))
        res[str(log)] = {key: dict(draws=v["draws"], frame_range=[min(v["frames"]), max(v["frames"])], kinds=sorted(map(str, v["kinds"])),
                                   replaced=v["replaced"], native=v["native"], replacement_sizes=sorted(map(list, v["sizes"])),
                                   max_bbox_area=v["area"])
                         for key, v in sorted(keys.items(), key=lambda kv: -kv[1]["draws"])}
    a.out.write_text(json.dumps(dict(rect=a.rect, frames=a.frames, logs=res), indent=1) + "\n", encoding="utf-8")
    for log, keys in res.items():
        print("==", Path(log).parts[-4], len(keys), "keys")
        for key, v in list(keys.items())[:14]:
            print(f"   {key} draws {v['draws']} frames {v['frame_range']} kinds {v['kinds']} replaced {v['replaced']} native {v['native']} sizes {v['replacement_sizes']} area {v['max_bbox_area']}")


if __name__ == "__main__":
    main()
