#!/usr/bin/env python3
"""Light, read-only v58 analysis (claude-einhander), following root's analysis-contract.json.

For each pair of neighbouring cycles (prev, cur), the exact swap-begin period is
    period = cur.swap_begin - prev.swap_begin
and it is partitioned, in order, as
    prev_swap    = prev.swap_end   - prev.swap_begin
    prev_post    = prev.exit       - prev.swap_end
    outside      = cur.enter       - prev.exit        (guest + other work between vblank callbacks)
    housekeeping = cur.debug_end   - cur.enter
    pre_pace     = cur.pace_begin  - cur.debug_end
    pace         = cur.pace_end    - cur.pace_begin
    present_prep = cur.swap_begin  - cur.pace_end
A pair is VALID only if both rows are closed, neither is UNCLOSED/MULTI_SWAP/MULTI_ALT/ALT_PACE, each has exactly one
swap, seqs and frame ids are neighbours (cur.frame == prev.frame + 1), every needed stamp is present, every component
is >= 0, and the components sum exactly to the period. Invalid pairs are counted by reason, never guessed.
Scope: CPU wall timestamps locate time; they do not prove busy CPU versus OS scheduling or GPU backlog.
Usage: analyze_frame_phases.py <world-flypast-proof.json> [--top N] [--out result.json]
"""
import argparse
import ctypes
import json
from collections import Counter
from pathlib import Path

CLOSED, UNCLOSED, MULTI_SWAP, ALT_PACE, MULTI_ALT = 1, 2, 4, 8, 16
PARTS = ["prev_swap", "prev_post", "outside", "housekeeping", "pre_pace", "pace", "present_prep"]


def below_normal():
    try:
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        return bool(k.SetPriorityClass(k.GetCurrentProcess(), 0x4000))
    except Exception:  # noqa: BLE001
        return False


def merge_pages(pages):
    rows, freq = {}, None
    for pg in pages:
        if not pg.get("ok") or pg.get("enabled") != 1:
            raise ValueError("phase page not ok/enabled")
        if freq not in (None, pg["qpc_frequency"]):
            raise ValueError("pages disagree on qpc_frequency")
        freq = pg["qpc_frequency"]
        for r in pg["rows"]:
            d = dict(zip(pg["fields"], r))
            rows[d["seq"]] = d
    return rows, freq


def pair(prev, cur):
    """Return (parts dict in ticks, None) or (None, reason)."""
    for name, r in (("prev", prev), ("cur", cur)):
        f = r["flags"]
        if not f & CLOSED:
            return None, f"{name}_open"
        if f & UNCLOSED:
            return None, f"{name}_unclosed"
        if f & (MULTI_SWAP | MULTI_ALT):
            return None, f"{name}_multi"
        if f & ALT_PACE:
            return None, f"{name}_alt_pace"
        if r["swaps"] != 1:
            return None, f"{name}_swaps_{r['swaps']}"
    if cur["seq"] != prev["seq"] + 1:
        return None, "seq_gap"
    if cur["frame"] != prev["frame"] + 1:
        return None, "frame_not_neighbour"
    need = [prev["swap_begin"], prev["swap_end"], prev["exit"], cur["enter"], cur["debug_end"], cur["pace_begin"],
            cur["pace_end"], cur["swap_begin"]]
    if not all(need):
        return None, "stamp_absent"
    parts = dict(prev_swap=prev["swap_end"] - prev["swap_begin"], prev_post=prev["exit"] - prev["swap_end"],
                 outside=cur["enter"] - prev["exit"], housekeeping=cur["debug_end"] - cur["enter"],
                 pre_pace=cur["pace_begin"] - cur["debug_end"], pace=cur["pace_end"] - cur["pace_begin"],
                 present_prep=cur["swap_begin"] - cur["pace_end"])
    if any(v < 0 for v in parts.values()):
        return None, "negative_component"
    period = cur["swap_begin"] - prev["swap_begin"]
    if sum(parts.values()) != period:
        return None, "partition_sum_mismatch"
    parts["period"] = period
    return parts, None


def pct(sorted_vals, q):
    if not sorted_vals:
        return None
    i = min(len(sorted_vals) - 1, max(0, round(q * (len(sorted_vals) - 1))))
    return sorted_vals[i]


def analyse(proof, top=20):
    rows, freq = merge_pages(proof["frame_phase_pages"])
    ms = 1e3 / freq
    obs = proof.get("observations") or []
    lo = obs[0]["registers"]["frame"] if obs else None
    hi = obs[-1]["registers"]["frame"] if obs else None
    seqs = sorted(rows)
    valid, reasons = [], Counter()
    for s in seqs:
        cur, prev = rows[s], rows.get(s - 1)
        if prev is None:
            reasons["no_prev_row_in_pages"] += 1
            continue
        if lo is not None and not (lo <= cur["frame"] <= hi):
            reasons["outside_measured_bracket"] += 1
            continue
        parts, why = pair(prev, cur)
        if why:
            reasons[why] += 1
            continue
        valid.append(dict(frame=cur["frame"], seq=cur["seq"], **{k: v * ms for k, v in parts.items()}))
    periods = sorted(v["period"] for v in valid)
    in_bracket = sum(1 for s in seqs if lo is None or lo <= rows[s]["frame"] <= hi)
    dist = {q: pct(periods, q) for q in (0.5, 0.9, 0.99, 0.999, 1.0)}
    worst = sorted(valid, key=lambda v: -v["period"])[:top]
    for w in worst:
        comp = {k: w[k] for k in PARTS}
        w["dominant"] = max(comp, key=comp.get)
        w["dominant_ms"] = comp[w["dominant"]]
    over = {thr: sum(1 for p in periods if p > thr) for thr in (20, 25, 33.4, 50, 100)}
    sums = {k: sum(v[k] for v in valid) for k in PARTS + ["period"]}
    out = dict(rows=len(rows), rows_in_measured_bracket=in_bracket, measured_frames=[lo, hi], valid_pairs=len(valid),
               valid_coverage=(len(valid) / in_bracket if in_bracket else None), invalid_reasons=dict(reasons),
               qpc_frequency=freq, period_ms_quantiles={str(k): v for k, v in dist.items()},
               periods_over_ms={str(k): v for k, v in over.items()},
               share_of_total_time={k: (sums[k] / sums["period"] if sums["period"] else None) for k in PARTS},
               worst=worst,
               scope="CPU wall timestamps locate time; they do not prove busy CPU vs OS scheduling or GPU backlog. "
                     "outside = guest plus other work between vblank callbacks, not pure emulation.")
    ring = proof.get("passive_present_ring_before_postshot") or {}
    ev = ring.get("events") or []
    if ev:
        by_frame = {}
        evs = sorted(ev, key=lambda e: e[0])
        for a, b in zip(evs, evs[1:]):
            by_frame[b[1]] = b[3] - a[3]
        out["present_ring_dt_for_worst"] = [dict(frame=w["frame"], phase_period_ms=round(w["period"], 3),
                                                 present_ring_dt_ms=by_frame.get(w["frame"])) for w in worst]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proof", type=Path)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    below_normal()
    res = analyse(json.loads(a.proof.read_text(encoding="utf-8")), a.top)
    text = json.dumps(res, indent=1)
    if a.out:
        a.out.write_text(text + "\n", encoding="utf-8")
    print(text[:6000])


if __name__ == "__main__":
    main()
