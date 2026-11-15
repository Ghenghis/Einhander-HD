#!/usr/bin/env python3
"""Synthetic checks for analyze_frame_phases.py (claude-einhander). CPU only, no game."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_frame_phases as A  # noqa: E402

FIELDS = ["seq", "frame", "frame_at_enter", "frame_at_swap", "flags", "swaps", "enter", "debug_end", "pace_begin",
          "pace_end", "swap_begin", "swap_end", "alt_pace_begin", "alt_pace_end", "exit"]


def row(seq, frame, t, flags=1, swaps=1, stall=0, alt=False):
    """Cycle starting at tick t (10 MHz): 1 ms housekeeping, 0.5 pre-pace, 10 pace, 1 prep (+stall), 0.2 swap, 0.3 post."""
    e = t
    d = e + 10000
    pb = d + 5000
    pe = pb + 100000
    sb = pe + 10000 + stall
    se = sb + 2000
    x = se + 3000
    ab, ae = (x - 1000, x - 500) if alt else (0, 0)
    return [seq, frame, frame - 1, frame, flags | (8 if alt else 0), swaps, e, d, pb, pe, sb, se, ab, ae, x]


def build(stall_at=None, unclosed_at=None, multi_at=None, alt_at=None, gap_frame_at=None):
    rows, t = [], 1_000_000
    for i in range(40):
        stall = 1_000_000 if i == stall_at else 0     # 100 ms in prep
        flags = 0 if i == unclosed_at else 1
        r = row(i, 100 + i + (1 if gap_frame_at is not None and i >= gap_frame_at else 0), t, flags=flags,
                swaps=2 if i == multi_at else 1, stall=stall, alt=(i == alt_at))
        rows.append(r)
        t = r[14] + 30000                             # 3 ms outside
    page = dict(ok=True, enabled=1, capacity=16384, qpc_frequency=10_000_000, fields=FIELDS, rows=rows, truncated=0)
    return dict(frame_phase_pages=[page], observations=[dict(registers=dict(frame=101)), dict(registers=dict(frame=139))])


def main():
    fails = []

    def need(c, m):
        if not c:
            fails.append(m)
    r = A.analyse(build(), top=3)
    need(r["valid_pairs"] == 39 and not r["invalid_reasons"].get("negative_component"), f"clean pairs {r['valid_pairs']} {r['invalid_reasons']}")
    w = r["worst"][0]
    need(abs(w["period"] - 16.0) < 1e-6, f"period {w['period']}")   # 1+0.5+10+1+0.2+0.3+3 ms
    need(abs(sum(w[k] for k in A.PARTS) - w["period"]) < 1e-9, "partition sums to period")
    r = A.analyse(build(stall_at=20), top=3)
    w = r["worst"][0]
    need(w["frame"] == 120 and w["dominant"] == "present_prep" and abs(w["present_prep"] - 101.0) < 1e-6, f"stall {w}")
    r = A.analyse(build(unclosed_at=10))
    need(r["invalid_reasons"].get("prev_open") == 1 and r["invalid_reasons"].get("cur_open") == 1, f"unclosed {r['invalid_reasons']}")
    r = A.analyse(build(multi_at=5))
    need(r["invalid_reasons"].get("prev_swaps_2", 0) + r["invalid_reasons"].get("cur_swaps_2", 0) == 2, f"multi {r['invalid_reasons']}")
    r = A.analyse(build(alt_at=7))
    need(r["invalid_reasons"].get("prev_alt_pace") == 1 and r["invalid_reasons"].get("cur_alt_pace") == 1, f"alt {r['invalid_reasons']}")
    r = A.analyse(build(gap_frame_at=15))
    need(r["invalid_reasons"].get("frame_not_neighbour") == 1, f"frame gap {r['invalid_reasons']}")
    print("FAILS", fails if fails else "none")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
