#!/usr/bin/env python3
"""s45: write BACKLOG-S45.md from the latest backlog/ and page-reuse/ runs (read-only inputs; JSON + 32 KiB words)."""
import datetime
import hashlib
import json
from pathlib import Path

import numpy as np

RA = Path("C:/github/Einhander/remaster-audit")
S45 = RA / "parallel-stages-20261114/s45"
BT = "`"


def code(x):
    return BT + str(x) + BT


def main():
    bp = sorted((S45 / "backlog").glob("*/backlog.json"))[-1]
    b = json.loads(bp.read_text(encoding="utf-8"))
    rp = sorted((S45 / "page-reuse").glob("*/reuse.json"))[-1]
    ru = json.loads(rp.read_text(encoding="utf-8"))
    reuse = {st: {x["tex"]: x for x in ru["stages"][st]} for st in ru["stages"]}
    tot = {}
    for st in ("4", "5"):
        rows = b["stages"][st]["rows"]
        un = [r for r in rows if r["cls"] == "UNAUTHORED"]
        common = [r for r in un if all(m.startswith("0/") for m in r["members"])]
        spec = [r for r in un if any(not m.startswith("0/") for m in r["members"])]

        def triv(r):
            a = (RA / f"fullgame-prep/static-extraction/stages/stage{st}/textures/{r['tex']}.words.bin").read_bytes()
            w = np.frombuffer(a, "<u2")
            if r["depths"] == [0] and len(a) == 32768:
                idx = np.stack([(w >> (4 * k)) & 0xF for k in range(4)], -1).ravel()
            else:
                idx = w.astype(np.int64)
            h = np.bincount(idx)
            return (h > 0).sum() <= 2 or h.max() / h.sum() >= 0.97
        tr = [r for r in spec if triv(r)]
        content = [r for r in spec if r not in tr]
        c4 = [r for r in content if r["depths"] == [0] and "page" in r["kinds"] and r["tex_confidence"] != "runtime-composed-needs-capture"]
        rc = [r for r in content if (r["tex_confidence"] == "runtime-composed-needs-capture" or "raw" in r["kinds"]) and r not in c4]
        fb = [r for r in content if r not in c4 and r not in rc]
        tot[st] = dict(sel=sum(1 for r in rows if r["cls"] == "SELECTED"), common=len(common), spec=len(spec), triv=tr, c4=c4, rc=rc, fb=fb,
                       total=b["stages"][st]["tex_total"])
    L = ["# Stage 4 / Stage 5 authoring backlog beyond the selected 23 keys (static prediction level)", ""]
    L.append(f"Written {datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%MZ')} by {code('claude-einhander-s45')}.")
    L.append(f"Sources: {code(bp.relative_to(S45).as_posix())} (sha256 {code(hashlib.sha256(bp.read_bytes()).hexdigest())}) and "
             f"{code(rp.relative_to(S45).as_posix())} (sha256 {code(hashlib.sha256(rp.read_bytes()).hexdigest())}).")
    L.append("")
    L.append("These come from static disc predictions only. Runtime-only keys are outside this list by construction:")
    L.append("- animated or runtime-written CLUTs (on Stage 1, 60% of drawn keys);")
    L.append("- MoveImage cells;")
    L.append("- code paths the static model does not read.")
    L.append("")
    L.append("Boss and route identity of a page is not recorded on the disc, so it comes from capture.")
    L += ["", "## Totals", "", "| | Stage 4 | Stage 5 |", "|---|---|---|"]

    def row(label, f):
        L.append(f"| {label} | {f('4')} | {f('5')} |")
    row("texture CRCs with predicted keys", lambda st: tot[st]["total"])
    row("selected (authored, candidate)", lambda st: tot[st]["sel"])
    row("shared, unbuilt (05E1881C)", lambda st: 1)
    row("unauthored, common members only (0/x; mostly also predicted for Stage 1)", lambda st: tot[st]["common"])
    row("unauthored, stage-specific", lambda st: tot[st]["spec"])
    row("of which trivial (one index, or one value on >= 97% of the page)", lambda st: f"{len(tot[st]['triv'])} ({', '.join(code(r['tex']) for r in tot[st]['triv'])})")
    row("**of which 4bpp content pages, exact or likely static words**", lambda st: f"**{len(tot[st]['c4'])}** ({sum(r['nonzero_keys'] for r in tot[st]['c4'])} keys)")
    row("of which runtime-composed or raw (need capture)", lambda st: f"{len(tot[st]['rc'])} ({sum(r['nonzero_keys'] for r in tot[st]['rc'])} keys)")
    row("of which 8bpp / 15bpp page fallbacks (mostly 1-2 static keys)", lambda st: f"{len(tot[st]['fb'])} ({sum(r['nonzero_keys'] for r in tot[st]['fb'])} keys)")
    L += ["",
          f"- {code('011FFCA6')} is byte-identical in S4 and S5, and every one of its words is 0: it is a cleared VRAM page. It "
          "needs no authoring; native pass-through or a flat fill is enough.",
          f"- {code('10932164')} (S4 member 2/18, S5 member 3/10; 1-2 keys) is noise-like data.",
          f"- {code('05E1881C')} is covered by {code('PANORAMA-05E1881C-OWNERSHIP.md')}.", ""]
    for st, name in (("4", "Stage 4"), ("5", "Stage 5")):
        L += [f"## {name}: 4bpp content pages to author (most keys first)", "",
              "| TEX | member | VRAM | keys | best pair | nearest authored page (texel / strip identity) |", "|---|---|---|---|---|---|"]
        for r in sorted(tot[st]["c4"], key=lambda r: -r["nonzero_keys"]):
            x = (reuse.get(st, {}).get(r["tex"]) or {}).get("best_authored") or {}
            near = f"{x.get('tex')} {x.get('page_xy')} {x.get('texels')} / {x.get('strips')}/32" if x else "-"
            L.append(f"| {code(r['tex'])} | {', '.join(r['members'])} | {'; '.join(str(tuple(p)) for p in r['page_xy'])} | "
                     f"{r['nonzero_keys']} | {r['best_pair']} | {near} |")
        L += ["", f"**{name}: runtime-composed or raw pages.** Author these only after a capture shows the composed words: " +
              ", ".join(f"{code(r['tex'])} ({', '.join(r['members'])} {tuple(r['page_xy'][0])})" for r in tot[st]["rc"]), "",
              f"**{name}: 8bpp / 15bpp page fallbacks.** These are depth readings that the static TSB harvest predicts at a 4bpp "
              "position. Each one is real only if a capture shows a draw at that depth. The Duerer 8bpp set is the main "
              f"exception; see {code('DUERER-8BPP-PLAN.md')}. The fallbacks: " +
              ", ".join(code(r["tex"]) for r in tot[st]["fb"]), ""]
    L += ["## Suggested order (CPU, after J-AB2 / probes / repairs)", "",
          f"1. **Stage 5 Duerer member 3/17 pages 768 / 832 / 896** ({code('D8403129')}, {code('81FB494C')}, {code('11FA828A')}).",
          "   - These complete the boss armour set, using the Duerer v3 (class-aware FX) method.",
          "   - They need identity marks from S5-5.",
          f"2. **Stage 4 section-b world** (member 2/22: {code('9B8107D2')} at 640, {code('B8C589D7')} at 896) and the 2/15 "
          "pages at 832 / 896.",
          "   - Use the world v3 method and Stage 4 swatches.",
          f"   - {code('9B8107D2')} shares 72% of its texels (16/32 strips) with the authored {code('E8769E55')}.",
          "3. **Stage 4 enemy variants** in members 2/19, 2/23 and 2/24 (320-768).",
          "   - Their static key and pair counts equal those of the 2/13 enemy pages, but they share less than 40% of their "
          "words, so they are separate art.",
          f"   - The 512,0 pages ({code('63155483')}, {code('DA56446E')}, {code('4D604948')}; 105 keys each) are the largest single "
          "pages.",
          f"4. **Stage 5 stage-entry 3/1 pages** at 448 / 512 ({code('327A20CE')}, {code('4DB524A5')}), and the 960,0 replacements "
          f"({code('4F542B30')} member 3/6, {code('CC4D7802')} member 3/13). These two also overwrite the panorama column.",
          "5. Everything is predicted-static. Import only after `validate_predicted.py confirm` + `gate` on the live run."]
    out = S45 / "BACKLOG-S45.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(out, hashlib.sha256(out.read_bytes()).hexdigest())
    for st in ("4", "5"):
        print(st, "c4", len(tot[st]["c4"]), sum(r["nonzero_keys"] for r in tot[st]["c4"]), "rc", len(tot[st]["rc"]), "fb", len(tot[st]["fb"]))


if __name__ == "__main__":
    main()
