#!/usr/bin/env python3
"""s45 menu/HUD (claude-einhander-s45, EIN-MENU-HUD-20261114): exact recovery of the 157 historical HUD fade palette keys.

Problem: hud-label-font-BDAE4156-v1 lists 157 keys (6 TEX x 68 PAL) drawn 1-2x each during palette fades in
research-20261112-153406-11eebc24 (frames 39570-40353, CLUT xy (304,492) / (288,500) / (288,499)); no .clut.bin was kept,
so they cannot be rendered. No palette may be invented.

Method (evidence, not synthesis):
  1. The same run kept 17 consecutive fade phases at (288,500) (frames 39552-39568). They show a per-channel rule:
     phase n: channel = min(n, T_channel) for R, G, B (5-bit), STP bit as in the final palette T, word 0 stays 0.
  2. Candidate final palettes T = every real 16-entry palette available: all static CLUTs of every stage export, every
     .clut.bin kept by this run, and the CLUTs the font manifest already proves. Rule variants are tried (rise
     min(n, T), fall max(T - n, 0)), n = 0..31.
  3. A rule/T pair is ACCEPTED only if it reproduces every kept phase at that position byte-for-byte (where kept phases
     exist), and a generated phase is a RECOVERED palette only if CRC32(16 words) equals a missing key's PAL exactly.
     A 32-bit CRC match on 32 bytes generated from real disc palettes by a rule proven on 17 real phases is the proof;
     nothing unmatched is written.
Writes ONLY s45/menu-hud/fade-recovery/<UTC>/ (recovered .clut.bin per key + recovery.json). JSON + small files only."""
import collections
import datetime
import glob
import hashlib
import json
import zlib
from pathlib import Path

import numpy as np

RA = Path("C:/github/Einhander/remaster-audit")
RUN = Path("C:/github/Einhander/windows-x64/tools/research-runs/research-20261112-153406-11eebc24/native")
FONT = RA / "comfy-authoring/w3-hud/frozen/hud-label-font-BDAE4156-v1/manifest.json"
STATIC = RA / "fullgame-prep/static-extraction/stages"
OUT = RA / "parallel-stages-20261114/s45/menu-hud/fade-recovery"


def crc(b):
    return "%08X" % (zlib.crc32(b) & 0xFFFFFFFF)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def channels(w):
    w = w.astype(np.int32)
    return w & 31, (w >> 5) & 31, (w >> 10) & 31, w & 0x8000


def make(r, g, b, stp, zero):
    out = (r | (g << 5) | (b << 10) | stp).astype(np.uint16)
    out[zero] = 0
    return out


def phases(T, rule, tmpl=None):
    """all phases of final palette T (16 uint16) under a rule -> list of (n, words). tmpl: optional observed palette whose
    STP bits and all-zero entries replace T's (a real VRAM state at the same position, e.g. the post-fade snapshot)."""
    r, g, b, stp = channels(T)
    zero = T == 0
    if tmpl is not None:
        stp = tmpl.astype(np.int32) & 0x8000
        zero = (np.arange(16) == 15) & (tmpl == 0)
    res = []
    kind, k = rule.split(":") if ":" in rule else (rule, "1")
    k = int(k)
    top = {"rise": 32, "fall": 32, "scale": k + 1, "scaler": k + 1, "white": 32}[kind]
    for n in range(top):
        if kind == "rise":      # channel rises by k per phase, clamped at the final value
            rr, gg, bb = np.minimum(r, n * k), np.minimum(g, n * k), np.minimum(b, n * k)
        elif kind == "fall":    # channel falls by k per phase from the final value
            rr, gg, bb = np.maximum(r - n * k, 0), np.maximum(g - n * k, 0), np.maximum(b - n * k, 0)
        elif kind == "scale":   # floor(c * n / k)
            rr, gg, bb = (r * n) // k, (g * n) // k, (b * n) // k
        elif kind == "scaler":  # round(c * n / k)
            rr, gg, bb = (r * n + k // 2) // k, (g * n + k // 2) // k, (b * n + k // 2) // k
        elif kind == "white":   # channel rises from the final value toward 31 by k per phase
            rr, gg, bb = np.minimum(r + n * k, 31), np.minimum(g + n * k, 31), np.minimum(b + n * k, 31)
        res.append((n, make(rr, gg, bb, stp, zero)))
    return res





def phases_all(C, rule, tmpl):
    """C: (N, 16) uint16 candidate final palettes. Returns, per candidate, {crc: (n, words)} of every phase (cached per
    template + rule; identical maths to phases())."""
    Ci = C.astype(np.int32)
    r, g, b = Ci & 31, (Ci >> 5) & 31, (Ci >> 10) & 31
    if tmpl is None:
        stp, zero = Ci & 0x8000, C == 0
    else:
        stp = np.broadcast_to(tmpl.astype(np.int32) & 0x8000, Ci.shape)
        zero = np.broadcast_to((np.arange(16) == 15) & (tmpl == 0), Ci.shape)
    kind, k = rule.split(":") if ":" in rule else (rule, "1")
    k = int(k)
    top = {"rise": 32, "fall": 32, "scale": k + 1, "scaler": k + 1, "white": 32}[kind]
    out = [dict() for _ in range(len(C))]
    for n in range(top):
        if kind == "rise":
            rr, gg, bb = np.minimum(r, n * k), np.minimum(g, n * k), np.minimum(b, n * k)
        elif kind == "fall":
            rr, gg, bb = np.maximum(r - n * k, 0), np.maximum(g - n * k, 0), np.maximum(b - n * k, 0)
        elif kind == "scale":
            rr, gg, bb = (r * n) // k, (g * n) // k, (b * n) // k
        elif kind == "scaler":
            rr, gg, bb = (r * n + k // 2) // k, (g * n + k // 2) // k, (b * n + k // 2) // k
        else:
            rr, gg, bb = np.minimum(r + n * k, 31), np.minimum(g + n * k, 31), np.minimum(b + n * k, 31)
        w = (rr | (gg << 5) | (bb << 10) | stp).astype(np.uint16)
        w[zero] = 0
        rows = w.view(np.uint8).reshape(len(C), 32)
        for i in range(len(C)):
            out[i].setdefault("%08X" % (zlib.crc32(rows[i].tobytes()) & 0xFFFFFFFF), n)
    return out


RULES = ["rise", "fall", "rise:2", "fall:2", "rise:4", "fall:4", "white", "white:2",
         "scale:16", "scale:31", "scale:32", "scaler:16", "scaler:31", "scaler:32", "scale:8", "scale:64"]


def main():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([c for c in me.cpu_affinity() if c not in (13, 15)][:1])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = OUT / stamp
    rd.mkdir(parents=True, exist_ok=False)
    font = json.loads(FONT.read_text(encoding="utf-8"))
    targets = font["logged_but_no_clut_sidecar"]["keys"]
    tpals = {k[9:] for k in targets}
    # draw rows of the run: position and frame of every key
    rows = [json.loads(l) for l in open(RUN / "capture.jsonl", encoding="utf-8") if "source_draw_query_matched" in l]
    first, pos_of = {}, collections.defaultdict(set)
    for r in rows:
        first.setdefault(r["key"][9:], r["frame"])
        pos_of[r["key"][9:]].add(tuple(r["clut_xy"]))
    kept = {}
    for f in glob.glob(str(RUN / "*.clut.bin")):
        b = Path(f).read_bytes()
        pal = Path(f).name.split("-")[1].split(".")[0]
        if len(b) == 32 and crc(b) == pal:
            kept[pal] = np.frombuffer(b, "<u2").copy()
    # candidate final palettes T
    cands = {}
    for p in sorted(STATIC.glob("*/cluts.json")):
        for e in json.loads(p.read_text(encoding="utf-8")):
            b = bytes.fromhex(e["words_hex"])
            if len(b) == 32:
                cands.setdefault(b, f"{p.parent.name}:{e['x']},{e['y']}:{e['pal']}")
    for pal, w in kept.items():
        cands.setdefault(w.tobytes(), f"run-kept:{pal}")
    for k in font["keys"]:
        cp = Path(str((k.get("clut") or {}).get("path", "")).replace("\\", "/"))
        if cp.is_file() and cp.stat().st_size == 32:
            cands.setdefault(cp.read_bytes(), f"font-manifest:{k['key']}")
    # positions with kept phases -> rule proof requirement
    kept_at = collections.defaultdict(dict)
    for pal, w in kept.items():
        for xy in pos_of.get(pal, ()):
            kept_at[xy][pal] = w
    target_pos = collections.defaultdict(set)
    for pal in tpals:
        for xy in pos_of.get(pal, ()):
            target_pos[xy].add(pal)
    # observed VRAM states at each target position (marked CPU-VRAM snapshots of the same run): STP/zero templates
    snaps = {}
    for ev in sorted(RUN.glob("event-*.bin")):
        vr = np.frombuffer(ev.read_bytes()[160 + 2 * 1024 * 1024:], "<u2").reshape(512, 1024)
        for xy in target_pos:
            w = vr[xy[1], xy[0]:xy[0] + 16].copy()
            if len(set(int(v) & 0x8000 for v in w[:15])) > 1:     # informative STP pattern only
                snaps.setdefault(xy, {})[crc(w.tobytes())] = dict(words=w, event=ev.name)
    cand_items = list(cands.items())
    cand_arr = np.stack([np.frombuffer(tb, "<u2") for tb, _ in cand_items])
    recovered, proofs = {}, []
    gens = collections.Counter()
    trials = 0
    for xy, tset in sorted(target_pos.items()):
        need = kept_at.get(xy, {})
        tmpls = [(None, "final palette's own STP")] + [(s["words"], f"observed {s['event']} {c}") for c, s in snaps.get(xy, {}).items()]
        for (tw, tname), rule in ((t, r_) for t in tmpls for r_ in RULES):
            # vectorised: every candidate palette's phases for this template + rule; per candidate a {crc: (n, words)}
            per_cand = phases_all(cand_arr, rule, tw)
            trials += sum(len(g) for g in per_cand)
            for (tb, origin), gen in zip(cand_items, per_cand):
                if need and not all(p in gen for p in need):
                    continue          # rule/T does not reproduce the kept phases at this position
                hn = {p: gen[p] for p in tset if p in gen}
                if not hn:
                    continue
                ph = dict(phases(np.frombuffer(tb, "<u2"), rule, tw))
                hits = {p: (n, ph[n]) for p, n in hn.items()}
                for p, (n, w) in hits.items():
                    assert crc(w.tobytes()) == p, "vectorised and scalar phase generators disagree"
                order = sorted(hits, key=lambda p: first.get(p, 0))
                ns = [hits[p][0] for p in order]
                monotone = all(a <= b_ for a, b_ in zip(ns, ns[1:])) or all(a >= b_ for a, b_ in zip(ns, ns[1:]))
                evidence = ("A: rule reproduces every kept phase at this position" if need else
                            ("B: STP/zero from an observed VRAM snapshot at this position; several hits from one generator"
                             if tw is not None and len(hits) >= 3 else
                             ("B: several CRC hits from one palette+rule, frame order consistent" if len(hits) >= 3 and monotone
                              else "C: single or isolated CRC hit")))
                rank = evidence[0]
                for p, (n, w) in hits.items():
                    gens[p] += 1
                    cur = recovered.get(p)
                    if cur is None or rank < cur["evidence"][0]:
                        recovered[p] = dict(words=w, n=n, rule=rule, origin=origin, clut_xy=list(xy), kept_proof=len(need),
                                            template=tname, evidence=evidence)
                        proofs.append(dict(clut_xy=list(xy), pal=p, rule=rule, template=tname, final_palette_origin=origin,
                                           final_palette_hex=tb.hex(), phase_n=n, kept_phases_reproduced=sorted(need),
                                           hits_from_this_generator=len(hits), hits_in_frame_order_n=ns,
                                           phase_order_consistent_with_frames=monotone, evidence=evidence))
    files = {}
    for k in targets:
        pal = k[9:]
        if pal in recovered:
            fn = rd / f"{k}.clut.bin"
            fn.write_bytes(recovered[pal]["words"].tobytes())
            assert crc(fn.read_bytes()) == pal
            files[k] = dict(path=fn.name, sha256=sha(fn), phase_n=recovered[pal]["n"], rule=recovered[pal]["rule"],
                            final_palette_origin=recovered[pal]["origin"], clut_xy=recovered[pal]["clut_xy"],
                            kept_phases_reproduced=recovered[pal]["kept_proof"], evidence=recovered[pal]["evidence"],
                            stp_template=recovered[pal]["template"], independent_generators=gens[pal])
    res = dict(run=stamp, owner="claude-einhander-s45", task="EIN-MENU-HUD-20261114",
               inputs=dict(font_manifest=dict(path=str(FONT), sha256=sha(FONT)), capture=dict(path=str(RUN / "capture.jsonl"), sha256=sha(RUN / "capture.jsonl")),
                           kept_palettes=len(kept), candidate_final_palettes=len(cands)),
               targets=dict(keys=len(targets), pals=len(tpals), positions={f"{x},{y}": len(s) for (x, y), s in target_pos.items()}),
               recovered_pals=len(recovered), recovered_keys=len(files), unrecovered_pals=sorted(tpals - set(recovered)),
               unrecovered_keys=sorted(k for k in targets if k[9:] not in recovered),
               crc_trials=trials, expected_false_matches=round(trials * len(tpals) / 2 ** 32, 4),
               observed_templates={f"{x},{y}": sorted(v) for (x, y), v in snaps.items()},
               files=files, proofs=proofs,
               rule="exact CRC32 match of a phase generated from a real palette by a rule that reproduces every kept phase at that position",
               status="RECOVERED PALETTE WORDS ONLY (no art yet); each file's CRC32 equals its key's PAL")
    (rd / "recovery.json").write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8")
    print("targets", len(targets), "pals", len(tpals), "candidates", len(cands), "kept", len(kept))
    print("recovered pals", len(recovered), "keys", len(files), "unrecovered pals", len(tpals) - len(recovered))
    print("crc trials", trials, "expected false matches", res["expected_false_matches"], "templates", res["observed_templates"])
    print("unrecovered", res["unrecovered_pals"])
    ev = collections.Counter(f["evidence"] for f in files.values())
    print("keys by evidence", dict(ev))
    print("run", stamp, "recovery.json", sha(rd / "recovery.json"))


if __name__ == "__main__":
    main()
