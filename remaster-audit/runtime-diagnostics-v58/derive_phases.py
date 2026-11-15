#!/usr/bin/env python3
"""Offline phase segments from v58 frame_phase_ring replies (claude-einhander). Read-only; no game, no server.

Input: one or more JSON files, each a single reply or a list of reply pages. Rows are merged by seq.
Output: per-row segments in ms (None = boundary absent) plus validity:
  precise  = CLOSED and none of UNCLOSED / MULTI_SWAP / MULTI_ALT (the newest open row is never precise)
  in_scope = precise and no ALT_PACE (offline, interpolation off, netplay off)
Segment definitions are in frame_phase_ring.h. No alternate-pacer subtraction: ALT_PACE rows are out of scope.
"""
import json
import sys

CLOSED, UNCLOSED, MULTI_SWAP, ALT_PACE, MULTI_ALT = 1, 2, 4, 8, 16


def rows_from(replies):
    by_seq, freq = {}, None
    for rep in replies:
        if not rep.get("ok"):
            raise ValueError(f"reply not ok: {rep.get('error')}")
        f = rep["qpc_frequency"]
        if freq not in (None, f):
            raise ValueError("pages disagree on qpc_frequency")
        freq = f
        for row in rep["rows"]:
            r = dict(zip(rep["fields"], row))
            by_seq[r["seq"]] = r
    return [by_seq[s] for s in sorted(by_seq)], freq


def derive(rows, freq):
    by_seq = {r["seq"]: r for r in rows}
    ms = 1e3 / freq
    out = []
    for r in rows:
        def d(a, b):
            return (r[b] - r[a]) * ms if r[a] and r[b] and r[b] >= r[a] else None
        prep_from = "pace_end" if r["pace_end"] else "debug_end"
        post_from = "swap_end" if r["swap_end"] else prep_from
        p = by_seq.get(r["seq"] - 1)
        outside = None
        if p and p["flags"] & CLOSED and not p["flags"] & UNCLOSED and p["exit"] and r["enter"] >= p["exit"]:
            outside = (r["enter"] - p["exit"]) * ms
        precise = bool(r["flags"] & CLOSED) and not r["flags"] & (UNCLOSED | MULTI_SWAP | MULTI_ALT)
        out.append(dict(seq=r["seq"], frame=r["frame"], flags=r["flags"], swaps=r["swaps"], precise=precise,
                        in_scope=precise and not r["flags"] & ALT_PACE, outside_ms=outside,
                        housekeeping_ms=d("enter", "debug_end"), pre_pace_ms=d("debug_end", "pace_begin"),
                        pace_ms=d("pace_begin", "pace_end"), present_prep_ms=d(prep_from, "swap_begin"),
                        swap_ms=d("swap_begin", "swap_end"), post_ms=d(post_from, "exit"),
                        alt_pace_ms=d("alt_pace_begin", "alt_pace_end"), cycle_ms=d("enter", "exit")))
    return out


def main(paths):
    replies = []
    for p in paths:
        j = json.load(open(p, encoding="utf-8"))
        replies += j if isinstance(j, list) else [j]
    rows, freq = rows_from(replies)
    seg = derive(rows, freq)
    keys = ["outside_ms", "housekeeping_ms", "pre_pace_ms", "pace_ms", "present_prep_ms", "swap_ms", "post_ms"]
    worst = sorted((s for s in seg if s["in_scope"]),
                   key=lambda s: -max((s[k] or 0) for k in keys))[:12]
    print(json.dumps(dict(rows=len(seg), precise=sum(s["precise"] for s in seg), in_scope=sum(s["in_scope"] for s in seg),
                          worst=worst), indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
