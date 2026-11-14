#!/usr/bin/env python3
"""Per-second join of host-audio starvation with v58 exact frame periods (claude-einhander). Read-only, below normal.
For each 1 Hz observation interval (frames prev..cur], report the increase in starved output sample frames (underruns),
overflow drops, fill_ms, pump calls/skips, and the largest swap-begin period plus its dominant phase inside the interval.
Correlation only: audio callbacks run on another thread; a long main-thread period starves the bridge-pull buffer when the
fill drains below what the device consumes. Usage: correlate_audio_stalls.py <proof.json> --out result.json
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
    a = ap.parse_args()
    try:
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)
    except Exception:  # noqa: BLE001
        pass
    d = json.loads(a.proof.read_text(encoding="utf-8"))
    res = A.analyse(d, top=0)
    rows, freq = A.merge_pages(d["frame_phase_pages"])
    period = {}
    for s in sorted(rows):
        p = rows.get(s - 1)
        if p is None:
            continue
        parts, why = A.pair(p, rows[s])
        if not why:
            comp = {k: parts[k] * 1e3 / freq for k in A.PARTS}
            period[rows[s]["frame"]] = (parts["period"] * 1e3 / freq, max(comp, key=comp.get))
    obs = d["observations"]
    out = []
    for prev, cur in zip(obs, obs[1:]):
        f0, f1 = prev["registers"]["frame"], cur["registers"]["frame"]
        ap_, ac = prev["audio"], cur["audio"]
        pr = [period[f] for f in range(f0 + 1, f1 + 1) if f in period]
        mx = max(pr, default=(None, None))
        out.append(dict(t=round(cur["elapsed_seconds"], 2), frames=f1 - f0,
                        starved=ac["out"]["underruns"] - ap_["out"]["underruns"],
                        overflow_drops=ac["out"]["overflow_drops"] - ap_["out"]["overflow_drops"],
                        fill_ms=ac["out"]["fill_ms"], pump_skips=ac["pump_skips"] - ap_["pump_skips"],
                        periods_over_25ms=sum(1 for x in pr if x[0] > 25),
                        max_period_ms=None if mx[0] is None else round(mx[0], 1), max_period_phase=mx[1]))
    starving = [r for r in out if r["starved"] > 0]
    stall = [r for r in out if (r["max_period_ms"] or 0) > 50]
    both = [r for r in out if r["starved"] > 0 and (r["max_period_ms"] or 0) > 50]
    summary = dict(intervals=len(out), starved_total=sum(r["starved"] for r in out),
                   overflow_drops_total=sum(r["overflow_drops"] for r in out),
                   intervals_with_starvation=len(starving), intervals_with_period_over_50ms=len(stall),
                   intervals_with_both=len(both),
                   starved_in_intervals_with_period_over_50ms=sum(r["starved"] for r in stall),
                   starved_in_intervals_without_period_over_25ms=sum(r["starved"] for r in out if r["periods_over_25ms"] == 0),
                   fill_ms_min=min(r["fill_ms"] for r in out), fill_ms_max=max(r["fill_ms"] for r in out))
    focused = sum(o.get('hd_cpu_profile', {}).get('keyboard_focus') == 1 and
                  o.get('hd_cpu_profile', {}).get('window_input_focus') == 1 for o in obs)
    a.out.write_text(json.dumps(dict(summary=summary, intervals=out,
                                     scope=f"1 Hz frame-bracket join; correlation only; focus active in {focused}/{len(obs)} samples; open-cycle alignment can cross bins."), indent=1) + "\n",
                     encoding="utf-8")
    print(json.dumps(summary, indent=1))
    print("top starvation seconds:", sorted(out, key=lambda r: -r["starved"])[:10])


if __name__ == "__main__":
    main()
