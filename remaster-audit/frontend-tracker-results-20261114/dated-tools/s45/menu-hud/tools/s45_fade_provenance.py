#!/usr/bin/env python3
"""s45 menu/HUD: PROVENANCE ADDENDUM for fade-recovery/20261114T150008Z (that run's files stay byte-unchanged).

Labels every recovered CLUT as DERIVED (reconstructed by a generator from real palettes + a phase rule, accepted on a
CRC32 match) versus the DIRECT byte-captured .clut.bin sidecars the research run kept, and measures:
  * candidate palettes (distinct 32-byte sequences) and generated phase sequences (distinct) per position/template/rule;
  * uniqueness: for every target PAL, the number of DISTINCT 16-word sequences among all generated phases whose CRC32
    equals it (must be exactly 1; >1 would be a real CRC collision between different words);
  * agreement: the recovered file's words equal that unique sequence;
  * the expected-false-match bound (distinct sequences x targets / 2^32);
  * equivalence evidence: the kept fade phases at (288,500) reproduced by the rule (byte-for-byte);
  * negative evidence: the 2 unmatched PALs / 5 keys and every rule x template tried for them.
A CRC match is NOT source, draw or live admission: these are candidates for rendering and review only.
Writes ONLY s45/menu-hud/fade-recovery/<UTC>-provenance/. One CPU (not 13/15), below normal."""
import collections
import datetime
import hashlib
import importlib.util
import json
import zlib
from pathlib import Path

import numpy as np

S45 = Path("C:/github/Einhander/remaster-audit/parallel-stages-20261114/s45")
REC = S45 / "menu-hud/fade-recovery/20261114T150008Z"
TOOL = S45 / "menu-hud/tools/s45_fade_recover.py"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([c for c in me.cpu_affinity() if c not in (13, 15)][:1])
    spec = importlib.util.spec_from_file_location("fr", TOOL)
    fr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fr)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "menu-hud/fade-recovery" / f"{stamp}-provenance"
    rd.mkdir(parents=True, exist_ok=False)
    rec = json.loads((REC / "recovery.json").read_text(encoding="utf-8"))
    font = json.loads(fr.FONT.read_text(encoding="utf-8"))
    targets = font["logged_but_no_clut_sidecar"]["keys"]
    tpals = {k[9:] for k in targets}
    rows = [json.loads(line) for line in open(fr.RUN / "capture.jsonl", encoding="utf-8") if "source_draw_query_matched" in line]
    pos_of = collections.defaultdict(set)
    for r in rows:
        pos_of[r["key"][9:]].add(tuple(r["clut_xy"]))
    kept = {}
    for f in sorted(fr.RUN.glob("*.clut.bin")):
        b = f.read_bytes()
        pal = f.name.split("-")[1].split(".")[0]
        if len(b) == 32 and fr.crc(b) == pal:
            kept[pal] = b
    cands = {}
    for p in sorted(fr.STATIC.glob("*/cluts.json")):
        for e in json.loads(p.read_text(encoding="utf-8")):
            b = bytes.fromhex(e["words_hex"])
            if len(b) == 32:
                cands.setdefault(b, 1)
    for b in kept.values():
        cands.setdefault(b, 1)
    for k in font["keys"]:
        cp = Path(str((k.get("clut") or {}).get("path", "")).replace("\\", "/"))
        if cp.is_file() and cp.stat().st_size == 32:
            cands.setdefault(cp.read_bytes(), 1)
    cand_arr = np.stack([np.frombuffer(b, "<u2") for b in cands])
    # templates exactly as the recovery run: None + informative snapshot states at each target position
    target_pos = collections.defaultdict(set)
    for pal in tpals:
        for xy in pos_of.get(pal, ()):
            target_pos[xy].add(pal)
    tmpls = {None: None}
    for ev in sorted(fr.RUN.glob("event-*.bin")):
        vr = np.frombuffer(ev.read_bytes()[160 + 2 * 1024 * 1024:], "<u2").reshape(512, 1024)
        for xy in target_pos:
            w = vr[xy[1], xy[0]:xy[0] + 16].copy()
            if len(set(int(v) & 0x8000 for v in w[:15])) > 1:
                tmpls.setdefault(w.tobytes(), w)
    # every distinct generated sequence (all templates x rules x candidates x phases)
    seqs_by_crc = collections.defaultdict(set)
    distinct = set()
    tried = collections.Counter()
    for tk, tw in tmpls.items():
        for rule in fr.RULES:
            Ci = cand_arr.astype(np.int32)
            r, g, b = Ci & 31, (Ci >> 5) & 31, (Ci >> 10) & 31
            if tw is None:
                stp, zero = Ci & 0x8000, cand_arr == 0
            else:
                stp = np.broadcast_to(tw.astype(np.int32) & 0x8000, Ci.shape)
                zero = np.broadcast_to((np.arange(16) == 15) & (tw == 0), Ci.shape)
            kind, k = rule.split(":") if ":" in rule else (rule, "1")
            k = int(k)
            top = {"rise": 32, "fall": 32, "scale": k + 1, "scaler": k + 1, "white": 32}[kind]
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
                for row in w.view(np.uint8).reshape(len(cand_arr), 32):
                    bb_ = row.tobytes()
                    if bb_ in distinct:
                        continue
                    distinct.add(bb_)
                    c = "%08X" % (zlib.crc32(bb_) & 0xFFFFFFFF)
                    if c in tpals:
                        seqs_by_crc[c].add(bb_)
                tried[(rule, "own STP" if tw is None else "snapshot " + fr.crc(tw.tobytes()))] += 1
    per_pal = {}
    for pal in sorted(tpals):
        seqs = seqs_by_crc.get(pal, set())
        f = next((REC / fn for fn in [f"{k}.clut.bin" for k in targets if k[9:] == pal] if (REC / fn).is_file()), None)
        per_pal[pal] = dict(distinct_generated_sequences_with_this_crc=len(seqs), unique=len(seqs) == 1,
                            recovered_file_equals_unique_sequence=(f is not None and len(seqs) == 1 and f.read_bytes() in seqs),
                            positions=sorted(list(x) for x in pos_of.get(pal, ())))
    # kept-phase equivalence at (288,500): rule rise from C12DB7DC reproduces each kept phase there
    T = None
    for p in sorted(fr.STATIC.glob("*/cluts.json")):
        for e in json.loads(p.read_text(encoding="utf-8")):
            if e["pal"] == "C12DB7DC":
                T = np.frombuffer(bytes.fromhex(e["words_hex"]), "<u2")
    gen = {fr.crc(wd.tobytes()): (n, wd.tobytes()) for n, wd in fr.phases(T, "rise")}
    kept288 = {pal: b for pal, b in kept.items() if (288, 500) in pos_of.get(pal, ())}
    equivalence = dict(position=[288, 500], final_palette="C12DB7DC (common/stage1 static, 272,504)", rule="rise min(n, T) per channel",
                       kept_phases=len(kept288),
                       reproduced_byte_for_byte=sum(1 for pal, b in kept288.items() if pal in gen and gen[pal][1] == b),
                       phases={pal: gen[pal][0] for pal in sorted(kept288) if pal in gen})
    labels = {}
    for k, info in rec["files"].items():
        labels[k] = dict(provenance="DERIVED: reconstructed CLUT words (generator + rule from real palettes), accepted on CRC32 == PAL; "
                                    "NOT a byte-captured sidecar",
                         evidence=info["evidence"], unique_sequence=per_pal[k[9:]]["unique"],
                         recovered_file_equals_unique_sequence=per_pal[k[9:]]["recovered_file_equals_unique_sequence"])
    out = dict(run=rd.name, owner="claude-einhander-s45", addendum_to=dict(path=str(REC / "recovery.json"), sha256=sha(REC / "recovery.json")),
               tool_sha256=sha(TOOL),
               status="PROVENANCE ADDENDUM; derived candidates only; a CRC match is not source, draw or live admission",
               direct_byte_captured=dict(note="the run's own .clut.bin sidecars (CRC-valid) are DIRECT captures; none of the 157 targets is among them",
                                         count=len(kept), any_target_captured=bool(set(kept) & tpals)),
               derived=dict(keys=len(labels), pals=len({k[9:] for k in labels})),
               candidates=dict(distinct_final_palettes=len(cands), templates=len(tmpls), rules=fr.RULES,
                               distinct_generated_sequences=len(distinct),
                               expected_false_matches_distinct=round(len(distinct) * len(tpals) / 2 ** 32, 5)),
               uniqueness=dict(all_recovered_unique=all(per_pal[k[9:]]["unique"] for k in labels),
                               all_files_equal_unique_sequence=all(per_pal[k[9:]]["recovered_file_equals_unique_sequence"] for k in labels),
                               per_pal=per_pal),
               equivalence_evidence=equivalence,
               negative_evidence=dict(unmatched_pals=rec["unrecovered_pals"], unmatched_keys=rec["unrecovered_keys"],
                                      generators_tried={f"{a} | {b}": n for (a, b), n in sorted(tried.items())},
                                      note="no generated sequence over all templates x rules x candidates has these CRCs"),
               labels=labels)
    (rd / "provenance.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print("distinct candidates", len(cands), "distinct generated", len(distinct), "expected false", out["candidates"]["expected_false_matches_distinct"])
    print("all unique", out["uniqueness"]["all_recovered_unique"], "files equal", out["uniqueness"]["all_files_equal_unique_sequence"],
          "equivalence", equivalence["reproduced_byte_for_byte"], "/", equivalence["kept_phases"], "captured targets", out["direct_byte_captured"]["any_target_captured"])
    print("run", rd.name, "provenance.json", sha(rd / "provenance.json"))


if __name__ == "__main__":
    main()
