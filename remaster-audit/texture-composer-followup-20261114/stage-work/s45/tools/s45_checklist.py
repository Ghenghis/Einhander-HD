#!/usr/bin/env python3
"""s45 (claude-einhander-s45): KEYED capture / admission checklist for Stages 4 and 5, generated from read-only static data
and s45's own audit runs. JSON only (no PNG decode). Writes s45/checklist/<UTC>/CHECKLIST-S45.json and .md.

Sections: A gate keys (selected frozen art), B shared panorama 05E1881C keys, C Duerer 8bpp candidates (+ their 4bpp
sub-image pages), D palette-phase holds on authored pages, E unauthored stage-specific pages, F run prerequisites.
Every item lists: exact page / depth / CLUT xy / PAL, static evidence, current s45 audit status, the capture fields that
admit it, and the evidence still missing."""
import collections
import datetime
import hashlib
import json
from pathlib import Path

RA = Path("C:/github/Einhander/remaster-audit")
S45 = RA / "parallel-stages-20261114/s45"
READINESS = RA / "runtime-review/seven-stage-status-20261114/lane-readiness-20261114T131712Z.json"
STATIC = RA / "fullgame-prep/static-extraction/stages"
REVIEW = RA / "fullgame-prep/stage-review"
CHK = RA / "runtime-diagnostics-v58/capture-checklists"
AUDIT = {4: S45 / "strict-audit/20261114T141046Z-s4/result.json", 5: S45 / "strict-audit/20261114T141041Z-s5/result.json"}
PROBE = {4: S45 / "probe-audit/20261114T141200Z-s4/result.json", 5: S45 / "probe-audit/20261114T141451Z-s5/result.json"}
COVERAGE = S45 / "clut-coverage/20261114T135254Z/coverage.json"
SOURCE_MAP = S45 / "source-map/20261114T133831Z/source-map.json"
DRAW_FIELDS = ["key", "frame", "source_kind", "depth", "semi", "page_xy", "clut_xy", "uv_bounds", "uv_vertices", "xy"]
COMPLETE_SOURCE = ("complete source in <run>/stage{st}-source/: <KEY>.words.bin + .clut.bin + .valid.bin + .source.json, "
                   "CRC32(words) = TEX, CRC32(clut) = PAL, known_words = total_words, valid.bin all non-zero")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def jl(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "checklist" / stamp
    rd.mkdir(parents=True, exist_ok=False)
    inputs = {str(p.relative_to(RA)).replace("\\", "/"): sha(p) for p in
              [READINESS, COVERAGE, SOURCE_MAP, *AUDIT.values(), *PROBE.values(), CHK / "S4.md", CHK / "S5.md"]}
    readiness = jl(READINESS)
    cov = jl(COVERAGE)
    smap = jl(SOURCE_MAP)
    out = dict(run=stamp, owner="claude-einhander-s45", tasks=["EIN-S4-WHOLE-CELL-20261114", "EIN-S5-WHOLE-CELL-20261114"],
               inputs=inputs, status="CHECKLIST ONLY: nothing here is confirmed live; every key is predicted-static",
               admission_sequence=[
                   "1 capture: continuous recomp run into the stage, stock textures for that stage's keys, stock-first dump",
                   "2 validate_predicted.py confirm (key-confirmed = byte-identical words and CLUT) and gate on the gate list",
                   "3 drawn CLUT differs from the review CLUT -> re-render that key from the frozen palette-independent master",
                   "4 s45 strict audit of every admitted export: primary (R1 + conn-only, cm_flags_ex bound 1e9) must be 0; "
                   "s/2 (bound 0.5) recorded as diagnostic; FX pages: post-render class snap (cm_repair) or class-aware rebuild if it fails",
                   "5 composer: opt-in cutout RGB fill (R5) on the new composition copy (root decision msg_80aa44e1)",
                   "6 integration, live A/B, motion and gameplay acceptance by codex-einhander (and the user's look decisions)"],
               sections={})
    for st in (4, 5):
        sd = STATIC / f"stage{st}"
        keys = {e["key"]: e for e in jl(sd / "keys.json")}
        pr = jl(REVIEW / f"stage{st}/palette-review.json")
        hold = set(pr["cycling_or_runtime_clut_candidate_keys"])
        zero_only = {tuple(x) for x in pr["zero_only_positions"]}
        common = {tuple(x) for x in (pr.get("stage1_runtime_modified_positions") or {}).get("common_area", [])}
        fam = {}
        for p in pr["pages"]:
            for v in p["versions"]:
                fam[(v["tex"], p["depth"])] = v.get("family")

        def phase(key, xy):
            if key not in hold:
                return None
            xy = tuple(xy or ())
            if xy in zero_only:
                return "runtime-written (zero-only static CLUT position): PAL unknown until captured"
            if xy in common:
                return "Stage 1 runtime-modified common position"
            return "several effective static candidates at this position: capture which one is drawn, and every phase"
        audit = collections.defaultdict(dict)
        for r in jl(AUDIT[st])["rows"]:
            audit[r["key"]][r["file"]] = dict(primary=r["primary_pass"], s2_strict=r["strict_pass"], conn_px=r.get("conn_viol_px"),
                                              s2_px=r.get("s2_viol_px"), r5=r["v2"]["r5_fringe_px"])
        probes = collections.defaultdict(dict)
        for r in jl(PROBE[st])["rows"]:
            if "error" not in r:
                probes[r["tex"]][f"{r['set']}:{r['key']}:{r['size']}"] = dict(primary=r["primary_pass"], s2_strict=r["strict_pass"],
                                                                                  conn_px=r["conn_viol_px"], s2_px=r["s2_viol_px"], cutout_share=r["cutout_share"])
        lane = next(s for s in readiness["stages"] if s["stage"] == st)
        S = smap["stages"][str(st)]
        # ---- A: gate keys
        A = []
        for set_name, s in S["sets"].items():
            for tex, pg in s["pages"].items():
                for rk in pg["rendered"]:
                    key = rk["key"]
                    if any(a["key"] == key for a in A):
                        next(a for a in A if a["key"] == key)["sets"].append(set_name)
                        continue
                    pc = cov["pages"][f"S{st}:{tex}"]
                    ok = [k for k in pc["keys"] if "error" not in k and not k["all_zero"]]
                    rv = next(k for k in ok if k["key"] == key)
                    competitors = [dict(key=k["key"], clut_xy=k["clut_xy"], pair_count=k["pair_count"], cutout_share=k["cutout_share"],
                                        stp_share=k["stp_share"]) for k in ok if k["key"] != key and
                                   ((k["pair_count"] or 0) > (rv["pair_count"] or 0) or (k["cutout_share"] > 0 and (k["pair_count"] or 0) >= 0.5 * (rv["pair_count"] or 1)))]
                    competitors.sort(key=lambda k: -(k["pair_count"] or 0))
                    pb = probes.get(tex, {})
                    missing = [f"complete source of {key} (or of whichever {tex}-* key is drawn)",
                               f"draw rows of {tex}-* keys with fields {DRAW_FIELDS}",
                               "which surface each page region is (identity), from the draw xy/uv and a still"]
                    if pg["palette_hold_keys"]:
                        missing.append(f"AQ-05 phase lists for the page's palette-hold keys ({len(pg['palette_hold_keys'])})")
                    if any(not v["primary"] for v in pb.values()):
                        missing.append("FX class-ownership fix verified on the failing probe key (cm_repair copy or class-aware rebuild)")
                    A.append(dict(item=f"S{st}-A-{key}", stage=st, key=key, tex=tex, pal=key[9:], sets=[set_name], member=pg["member"],
                                  family=fam.get((tex, 0)), page_xy=pg["page_xy"], depth=0, clut_xy=rk["clut_xy"],
                                  static=dict(confidence=rk["static_key"]["confidence"], pair_count=rk["static_key"]["pair_count"],
                                              pal_candidates_at_position=rk["static_key"]["pal_candidates_at_position"],
                                              words_crc_proven=pg["crc_proven"], clut_crc_proven=rk["clut_crc_proven"]),
                                  review_clut_classes=dict(cutout_entries=rk["clut"]["cutout_entries"], stp_entries=rk["clut"]["stp_entries"]),
                                  phase=phase(key, rk["clut_xy"]),
                                  regions=[r["kind"] for r in pg["regions"]],
                                  competing_cluts=competitors[:5],
                                  audit_frozen_exports=audit.get(key, {}), audit_transparency_probes=pb,
                                  admit_when=["validate_predicted confirm lists the key key-confirmed", "gate passes for the gate list",
                                              "strict audit primary = 0 on the admitted exports"],
                                  missing_evidence=missing))
        # ---- B: panorama
        P = smap["panorama_05E1881C"]["stages"][str(st)]
        B = [dict(item=f"S{st}-B-{r['key']}", stage=st, key=r["key"], tex="05E1881C", page_xy=[960, 0], depth=0, clut_xy=r["clut_xy"],
                  pair_count=r["pair_count"], zero_clut=r["pal_all_zero"], phase=phase(r["key"], r["clut_xy"]),
                  ramp_rho=(r.get("clut") or {}).get("lum_rank_rho"),
                  slice_of_8bpp_row=(st == 5 and r["clut_xy"] and r["clut_xy"][1] in (509, 510, 511)),
                  missing_evidence=[f"draw rows over one full horizontal pan, full rate (repeat_sample_frames 1), fields {DRAW_FIELDS}",
                                    "CLUT words at the drawn clut_xy (stock-first dump while on screen; snapshot = second source)",
                                    "u wrap period from uv_bounds; one 4K still per section"]) for r in P["keys"]]
        # ---- C: 8bpp (stage 5 only)
        C = []
        if st == 5:
            dur = smap["duerer_8bpp"]
            for k in dur["depth1_page_keys"]:
                halves = (k["left_half_4bpp_tex"] or []) + (k["right_half_4bpp_tex"] or [])
                sub = [t for t in ("1F11EE57", "BFC445B0", "3D108041") if t in halves]
                if not sub:
                    continue
                half = "L" if sub[0] in (k["left_half_4bpp_tex"] or []) else "R"
                reg = dur["regions"][sub[0]]
                rng = reg["as_8bpp_texpage_here"] if half == "L" else reg["as_8bpp_texpage_one_page_left"]
                xy = tuple(k["clut_xy"])
                C.append(dict(item=f"S5-C-{k['key']}", stage=5, key=k["key"], tex=k["key"][:8], pal=k["key"][9:], depth=1,
                              texpage_x=k["page_xy"][0], page_words=[128, 256], halves=dict(left=k["left_half_4bpp_tex"], right=k["right_half_4bpp_tex"]),
                              holds_subimage_of=sub[0], subimage_half=half, subimage_u8=rng["u"], subimage_v=rng["v"],
                              member=k["tex_member"], family=fam.get((k["key"][:8], 1)), clut_xy=list(xy), clut_entries=256,
                              pair_count=k["pair_count"], pal_all_zero=k["pal_all_zero"],
                              clut_status=("runtime-written row (zero-only in static data): real 256-colour palette only from the capture"
                                           if xy in zero_only else
                                           ("all-zero static candidate at a position that also has a non-zero static candidate: "
                                            "the row is cleared at some phase (draws nothing then)" if k["pal_all_zero"] else
                                            "static 256-word row (3/1 upload 0,504,256,8)")),
                              phase=phase(k["key"], xy),
                              missing_evidence=["a depth-1 draw row with this texpage x and key during the Duerer fight (S5-5 marks)",
                                                "complete source with a 256-entry .clut.bin (a 16-entry read at clut_xy is not enough)",
                                                "uv_bounds of the draw inside the sub-image range (u8/v above) vs the neighbouring page half",
                                                "semi for the draw; CPU-VRAM snapshot of CLUT rows 496/509-511 at the mark (flash/fade phases)"]))
            for t in ("1F11EE57", "BFC445B0", "3D108041"):
                reg = dur["regions"][t]
                C.append(dict(item=f"S5-C-subimage-{t}", stage=5, tex=t, depth=0, page_xy=reg["page_xy"], member=reg["member"],
                              blocks8=reg["blocks8"], bbox_4bpp_texels=reg["bbox_4bpp_texels"], current_delivery="Duerer v2 native pass-through (NOT HD) in these blocks",
                              decision_rule="if no depth-1 draw of these words appears across the whole fight: 8bpp reading is wrong; keep 4bpp; report it",
                              unpredicted_risk="texpage 576 (BFC445B0|1168CC84) or 640/704 cross-member pages would be new, unpredicted CRCs"))
        # ---- D: palette-phase holds on authored pages
        D = []
        for set_name, s in S["sets"].items():
            for tex, pg in s["pages"].items():
                for hk in pg["palette_hold_keys"] or []:
                    if any(d["key"] == hk for d in D):
                        continue
                    e = keys.get(hk) or {}
                    D.append(dict(item=f"S{st}-D-{hk}", stage=st, key=hk, tex=tex, page_xy=pg["page_xy"], depth=e.get("depth", 0),
                                  clut_xy=e.get("clut_xy"), pair_count=e.get("pair_count"), zero_clut=hk[9:] == "190A55AD",
                                  phase=phase(hk, e.get("clut_xy")) or "listed palette-hold by the lane",
                                  missing_evidence=["AQ-05 hold window covering one full cycle/fade of this CLUT position",
                                                    "complete source of every phase key seen (phase order from full-rate draw rows)"]))
        # ---- E: unauthored stage-specific 4bpp content pages
        bl = jl(sorted((S45 / "backlog").glob("*/backlog.json"))[-1])
        E = []
        for r in bl["stages"][str(st)]["rows"]:
            if r["cls"] != "UNAUTHORED" or not any(not m.startswith("0/") for m in r["members"]) or r["depths"] != [0] or "page" not in r["kinds"]:
                continue
            if r["tex"] in ("011FFCA6",):
                continue
            E.append(dict(item=f"S{st}-E-{r['tex']}", stage=st, tex=r["tex"], members=r["members"], family=fam.get((r["tex"], 0)),
                          page_xy=r["page_xy"], depth=0, nonzero_keys=r["nonzero_keys"], best_pair=r["best_pair"], tex_confidence=r["tex_confidence"],
                          missing_evidence=["draw rows of its keys (which keys are drawn, which CLUT, where on screen)",
                                            "identity mark/still of what it is"] +
                                           (["composed page words (runtime-composed: raw upload overlaps the page)"]
                                            if r["tex_confidence"] == "runtime-composed-needs-capture" else [])))
        F = dict(route="continuous recomp run through Stages 1-%d into Stage %d (AQ-02 stage-select and AQ-03b DuckStation states cannot confirm keys)" % (st - 1, st),
                 pack="stock textures for every Stage %d key (no HD pack); HD dump stock-first to <run>/stage%d-source/" % (st, st),
                 recorder="draw rows with fields %s; marks stage:%d:entry, seg:%d:<id> at each 0x80081382 change, clear:%d; CPU-VRAM snapshot at every mark" % (DRAW_FIELDS, st, st, st),
                 gate_list=str(CHK / f"keys/S{st}-gate-keys.txt"), checklist=str(CHK / f"S{st}.md"))
        out["sections"][f"stage{st}"] = dict(A_gate_keys=A, B_panorama=B, C_8bpp=C, D_phase_holds=D, E_unauthored_pages=E, F_prerequisites=F,
                                             counts=dict(A=len(A), B=len(B), C=len(C), D=len(D), E=len(E)))
    js = rd / "CHECKLIST-S45.json"
    js.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    # ---- markdown summary
    BT = "`"
    L = [f"# Stages 4 and 5: keyed capture and admission checklist (s45, {stamp})", "",
         f"Machine-readable: {BT}CHECKLIST-S45.json{BT} (sha256 {BT}{sha(js)}{BT}). Every key is predicted-static and nothing is confirmed "
         "live. Base checklists: `runtime-diagnostics-v58/capture-checklists/S4.md` and `S5.md`; this file adds per-key status and "
         "missing evidence.", "", "## Admission sequence", ""] + [f"{i}. {x[2:]}" for i, x in enumerate(out["admission_sequence"], 1)] + [""]
    for st in (4, 5):
        sec = out["sections"][f"stage{st}"]
        L += [f"## Stage {st}", "", f"Counts: gate keys {sec['counts']['A']}, panorama keys {sec['counts']['B']}, 8bpp items {sec['counts']['C']}, "
              f"phase holds {sec['counts']['D']}, unauthored content pages {sec['counts']['E']}.", "",
              "### A. Gate keys (frozen candidate art)", "",
              "| key | family | page | CLUT xy | pairs | phase | frozen exports (primary / s/2) | transparency probe | best competing CLUT |",
              "|---|---|---|---|---|---|---|---|---|"]
        for a in sec["A_gate_keys"]:
            fe = a["audit_frozen_exports"]
            fe_s = ", ".join(f"{k[4:]} {'P' if v['primary'] else 'FAIL'}/{'ok' if v['s2_strict'] else 'fail ' + str(v['s2_px'])}" for k, v in sorted(fe.items()))
            pb = a["audit_transparency_probes"]
            pb_s = "; ".join(f"{k.split(':')[1][9:]} {k.split(':')[2]} {'P' if v['primary'] else 'FAIL conn ' + str(v['conn_px'])}" +
                             ("" if v["s2_strict"] else f" s2 {v['s2_px']}") for k, v in sorted(pb.items())) or "-"
            comp = a["competing_cluts"][0] if a["competing_cluts"] else None
            comp_s = f"{comp['key'][9:]} @{comp['clut_xy']} ({comp['pair_count']} pairs, cut {comp['cutout_share']})" if comp else "-"
            L.append(f"| {BT}{a['key']}{BT} | {a['family']} | {a['page_xy']} | {a['clut_xy']} | {a['static']['pair_count']} | "
                     f"{'hold' if a['phase'] else '-'} | {fe_s} | {pb_s} | {comp_s} |")
        L += ["", "Missing for every gate key: its complete source (or that of the drawn sibling key), draw rows, surface identity. "
              "Pages with palette-hold keys also need AQ-05 phase lists, and FX pages whose probe failed need the class fix verified "
              "(see the JSON `missing_evidence`).", ""]
        if sec["C_8bpp"]:
            L += ["### C. Duerer 8bpp candidates (depth 1; 128 x 256-word page; 256-entry CLUT)", "",
                  "| key | texpage x | halves L / R | sub-image | 8bpp u / v | CLUT xy | pairs | CLUT status |", "|---|---|---|---|---|---|---|---|"]
            for c in sec["C_8bpp"]:
                if "key" not in c:
                    continue
                L.append(f"| {BT}{c['key']}{BT} | {c['texpage_x']} | {c['halves']['left']} / {c['halves']['right']} | {c['holds_subimage_of']} "
                         f"({c['subimage_half']}) | {c['subimage_u8']} / {c['subimage_v']} | {c['clut_xy']} | {c['pair_count']} | "
                         f"{'ALL-ZERO: ' if c['pal_all_zero'] else ''}{c['clut_status'].split(':')[0]} |")
            L += ["", "Each needs:",
                  "- a depth-1 draw row (key, texpage, `uv_bounds`, `semi`) during the S5-5 marks;",
                  "- a complete source with a 256-entry CLUT;",
                  "- a CPU-VRAM snapshot of CLUT rows 496 and 509-511 for the flash and fade phases.",
                  "If none of the three sub-images is drawn at depth 1 during the whole fight, the 8bpp reading is wrong: the "
                  "sub-images stay 4bpp native pass-through, and this must be reported.", ""]
        L += ["### B. Panorama 05E1881C keys", "", "| key | CLUT xy | pairs | phase | ramp rho | slice of an 8bpp row |", "|---|---|---|---|---|---|"]
        for b in sec["B_panorama"]:
            L.append(f"| {BT}{b['key']}{BT} | {b['clut_xy']} | {b['pair_count']} | {'hold' if b['phase'] else '-'} | {b['ramp_rho']} | "
                     f"{'yes' if b['slice_of_8bpp_row'] else '-'} |")
        L += ["", f"### D. Palette-phase holds on authored pages: {len(sec['D_phase_holds'])} keys", "",
              ", ".join(f"{BT}{d['key']}{BT}" for d in sec["D_phase_holds"]), "",
              f"### E. Unauthored stage-specific 4bpp content pages: {len(sec['E_unauthored_pages'])}", "",
              ", ".join(f"{BT}{e['tex']}{BT} ({'/'.join(e['members'])}, {e['family']})" for e in sec["E_unauthored_pages"]), "",
              "### F. Run prerequisites", ""] + [f"- **{k}:** {v}" for k, v in sec["F_prerequisites"].items()] + [""]
    md = rd / "CHECKLIST-S45.md"
    md.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("run", stamp, "json", sha(js), "md", sha(md))
    for st in (4, 5):
        print("S%d" % st, out["sections"][f"stage{st}"]["counts"])


if __name__ == "__main__":
    main()
