#!/usr/bin/env python3
"""Join v58 exact-swap durations with HD upload-ledger events (claude-einhander). Read-only, below normal.
For every frame with an HD upload >= 32 MiB, report the exact SDL_GL_SwapWindow duration at frames f+0..f+8, and for
the largest swaps report the HD bytes uploaded in f-8..f. CPU wall timestamps locate time only: a blocked swap means
the driver/compositor/GPU made the swap wait; it does not by itself prove which of them.
Usage: correlate_swap_uploads.py <world-flypast-proof.json> --out result.json
"""
import argparse
import ctypes
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_frame_phases as A  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proof", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--lag", type=int, default=8)
    a = ap.parse_args()
    try:
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)
    except Exception:  # noqa: BLE001
        pass
    d = json.loads(a.proof.read_text(encoding="utf-8"))
    rows, freq = A.merge_pages(d["frame_phase_pages"])
    ms = 1e3 / freq
    swap = {r["frame"]: (r["swap_end"] - r["swap_begin"]) * ms for r in rows.values()
            if r["flags"] & A.CLOSED and r["swaps"] == 1 and r["swap_begin"] and r["swap_end"]}
    hd = [e for pg in d["hd_upload_ledger_pages"] for e in pg["events"]]
    mib = {}
    for e in hd:
        mib[e[1]] = mib.get(e[1], 0) + e[5] / 2**20
    big = [e for e in hd if e[5] >= 32 * 2**20]
    rows_out = []
    for e in big:
        f = e[1]
        s = [swap.get(f + i) for i in range(a.lag + 1)]
        vals = [x if x is not None else -1 for x in s]
        m = max(range(len(vals)), key=lambda i: vals[i])
        rows_out.append(dict(upload_frame=f, key=e[2], w=e[3], h=e[4], mib=e[5] / 2**20,
                             upload_call_ms=e[9] / freq * 1e3, swap_ms_after=[None if x is None else round(x, 3) for x in s],
                             max_swap_ms=round(vals[m], 3), max_at_lag=m))
    top = sorted(((v, f) for f, v in swap.items()), reverse=True)[:12]
    res = dict(proof=str(a.proof), qpc_frequency=freq, swaps_measured=len(swap),
               median_swap_ms=sorted(swap.values())[len(swap) // 2],
               swaps_over_50ms=sum(1 for v in swap.values() if v > 50),
               big_uploads=len(big), big_uploads_followed_by_swap_over_50ms=sum(1 for r in rows_out if r["max_swap_ms"] > 50),
               lag_histogram_of_those={str(lag): sum(1 for r in rows_out if r["max_swap_ms"] > 50 and r["max_at_lag"] == lag)
                                       for lag in range(a.lag + 1)},
               big_upload_rows=rows_out,
               top_swaps=[dict(frame=f, swap_ms=round(v, 3), hd_mib_in_prev_8_frames=round(sum(mib.get(g, 0) for g in range(f - 8, f + 1)), 1))
                          for v, f in top],
               scope="CPU QPC locates the wait inside SDL_GL_SwapWindow; it does not prove GPU backlog vs driver residency/paging vs "
                     "compositor. Correlation, not causation.")
    a.out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("big_upload_rows",)}, indent=1))


if __name__ == "__main__":
    main()
