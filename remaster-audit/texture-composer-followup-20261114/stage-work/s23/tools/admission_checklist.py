"""s23: keyed Stage 2/3 capture + admission checklist (light: JSON/text only, no pixel work).

  python -I admission_checklist.py <out_dir>

One row per key: the 39 + 39 selected keys, the 60 unknown Stage 2 cycling phases and the 4 unexported drawn
Stage 2 actor keys. Every fact is labelled VERIFIED (CRC/sha proof or an actual logged draw row) or INFERRED (static
prediction, listed pairing, inferred cell). Each row lists the missing evidence with the capture item that supplies it
(runtime-diagnostics-v58/capture-checklists S2.md / S3.md) and the admission blockers. Inputs are pinned by sha256.
Also checks that the checklist key files S2-gate-keys.txt / S3-gate-keys.txt equal the s23 selection.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

ROOT = "C:/github/Einhander"
RA = ROOT + "/remaster-audit"
S23 = RA + "/parallel-stages-20261114/s23"
IN = {
    "selection_map": S23 + "/runs/selection-20261114T133254Z/selection-map.json",
    "j1_rows": S23 + "/runs/j1-20261114T134041Z/rows.jsonl",
    "phase_coverage": S23 + "/runs/phase-coverage-20261114T134554Z/phase-coverage.json",
    "draws_s2": RA + "/comfy-authoring/w7-stage2/work/draws-s2.json",
    "s2_gate_keys": RA + "/runtime-diagnostics-v58/capture-checklists/keys/S2-gate-keys.txt",
    "s3_gate_keys": RA + "/runtime-diagnostics-v58/capture-checklists/keys/S3-gate-keys.txt",
    "s2_unknown_phases": RA + "/runtime-diagnostics-v58/capture-checklists/keys/S2-unknown-phase-keys-60.txt",
    "s2_checklist": RA + "/runtime-diagnostics-v58/capture-checklists/S2.md",
    "s3_checklist": RA + "/runtime-diagnostics-v58/capture-checklists/S3.md",
    "j2a_partial": S23 + "/proposals/s3-dither-hybrid-a-20261114T140153Z/manifest.json",
}
S3_PAGES = {"B53A4C57": [640, 0], "59B55BC8": [704, 0], "66A350AA": [896, 0], "E49BC3F1": [960, 0], "AA5DBEF2": [384, 256]}
ACTOR_KEYS = {"3DD37B6B-3C1DB4B6": [192, 484], "3DD37B6B-86558368": [48, 484], "3DD37B6B-B949240B": [64, 484], "3DD37B6B-FAC936BC": [208, 484]}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def keys_file(p):
    return [l.strip() for l in open(p, encoding="utf-8") if l.strip() and not l.startswith("#")]


def main(out):
    os.makedirs(out, exist_ok=True)
    pins = {k: dict(path=v, sha256=sha(v)) for k, v in IN.items()}
    sel = json.load(open(IN["selection_map"], encoding="utf-8"))["stages"]
    j1 = {}
    for l in open(IN["j1_rows"], encoding="utf-8"):
        r = json.loads(l)
        j1.setdefault(r["key"], {})[r["file"]] = r
    phase = json.load(open(IN["phase_coverage"], encoding="utf-8"))["positions"]
    draws = json.load(open(IN["draws_s2"], encoding="utf-8"))
    j2a = json.load(open(IN["j2a_partial"], encoding="utf-8"))
    cyc = {}
    for pos, v in phase.items():
        for k, kv in v["keys"].items():
            cyc[k] = dict(position=pos, phases=v["palettes"], words=kv["words"], selected_draw_share=v["selected_draw_share"])
    rows = []

    def strict_r5(key):
        f = j1.get(key, {})
        if not f:
            return None
        return dict(VERIFIED=dict(strict_whole_cell_pass=all(x["strict_pass_np"] for x in f.values()),
                                  equals_dll_audit=all(x["all_equal"] for x in f.values()),
                                  r5_fringe_px={fk: x["np"]["r5_fringe_px"] for fk, x in f.items()},
                                  png_sha256={fk: x["png_sha256"] for fk, x in f.items()}))

    # ---- Stage 2 selected
    for key, kr in sorted(sel["2"]["keys"].items()):
        d = draws.get(key, {})
        clut = kr["clut"]
        verified = {"tex_words": "CRC-proven page words (static export stage2)"}
        inferred = {}
        if (clut.get("kind") or "").startswith("recovered"):
            verified["clut_words"] = "recovered from CRC-validated marked CPU-VRAM snapshot (run evidence in manifest)"
        else:
            verified["clut_words"] = "static export CLUT, crc32 == PAL"
        if d:
            verified["draw_rows"] = dict(rows=d.get("n"), frames=d.get("frames"), runs=d.get("runs"), page_xy=d.get("page_xy"),
                                         clut_xy_seen=d.get("clut_xy"), semi=d.get("semi"), uv_top=(d.get("uv_top") or [])[:4],
                                         note="sampled_activation_forward repeat 60; not full rate")
        inferred["clut_slot_static"] = clut.get("vram_xy")
        seen = [list(x) for x in (d.get("clut_xy") or [])]
        if clut.get("vram_xy") and seen and clut["vram_xy"] not in seen:
            inferred["clut_slot_note"] = f"static slot {clut['vram_xy']} differs from drawn clut_xy {seen}"
        missing, blockers = [], []
        missing.append("stock-first complete source (words/clut/valid/source.json) + validate_predicted confirm/gate (S2-1)")
        missing.append("full-rate draw rows with real UVs (S2-3)")
        if key in cyc and cyc[key]["phases"] > 1:
            blockers.append(f"cycling position {cyc[key]['position']}: {cyc[key]['phases']} phases, words for only 4; selected phases cover "
                            f"{round(100 * cyc[key]['selected_draw_share'], 1)}% of sampled draws -> hold until S2-2 + J6 export of every phase")
        if kr["selection_group"] in ("train_cars_v4", "sky_ground_v3"):
            missing.append("live fly-past with candidates installed (S2-5): crawl/shimmer gate")
        if key in ("0F01F0FA-8FD3DE52", "0F01F0FA-F11578EE", "0F01F0FA-BE954EE4", "0F01F0FA-B692B4C2"):
            blockers.append("thin edge-on draws shimmer ~0.85-0.97x stock in SIMULATION; needs class-aware mips (runtime), not art")
        rows.append(dict(stage=2, key=key, kind="selected", tex=kr["tex"], depth="4bpp (16-entry CLUT)",
                         page_xy=(d.get("page_xy") or [None])[0], selected_folder=kr["selected_folder"], group=kr["selection_group"],
                         VERIFIED=verified, INFERRED=inferred, art=strict_r5(key),
                         r5_plan="root composer opt-in cutout_rgb_fill on new compositions (msg_fc43765a)",
                         missing_evidence=missing, admission_blockers=blockers,
                         admission="BLOCKED" if blockers else "PENDING live confirmation"))
    # ---- Stage 2 unknown cycling phases
    unk = keys_file(IN["s2_unknown_phases"])
    for key in unk:
        d = draws.get(key, {})
        rows.append(dict(stage=2, key=key, kind="unknown_cycling_phase", tex=key[:8], depth="4bpp (16-entry CLUT)",
                         page_xy=(d.get("page_xy") or [None])[0],
                         VERIFIED=dict(tex_words="CRC-proven page words", key_crc_from_draw_log=True,
                                       draw_rows=dict(rows=d.get("n"), frames=d.get("frames"), clut_xy_seen=d.get("clut_xy")) if d else None),
                         INFERRED=dict(position=cyc.get(key, {}).get("position")),
                         art=None, missing_evidence=["CLUT words (stock-first <KEY>.clut.bin or CRC-matched snapshot) + AQ-05 hold for gate A (S2-2)",
                                                     "then J6 export from frozen prep-v1 master (CPU grant)"],
                         admission_blockers=["no CLUT words"], admission="BLOCKED"))
    # ---- Stage 2 cross-lane actor keys
    for key, xy in ACTOR_KEYS.items():
        d = draws.get(key, {})
        rows.append(dict(stage=2, key=key, kind="cross_lane_unexported", tex=key[:8], depth="4bpp (16-entry CLUT)",
                         page_xy=(d.get("page_xy") or [None])[0],
                         VERIFIED=dict(tex_words="CRC-proven page words (static export stage2)", clut_words="static export CLUT",
                                       draw_rows=dict(rows=d.get("n"), frames=d.get("frames"), clut_xy_seen=d.get("clut_xy"), uv_top=(d.get("uv_top") or [])[:3]) if d else None),
                         INFERRED=dict(owner="w4-enemies family post_drache_actors (drache-sources.json)"),
                         art=None, missing_evidence=["owner decision + stock source (S2-4 / CAPTURE-REQUESTS C1-C3)"],
                         admission_blockers=["no HD art in any lane"], admission="NOT AUTHORED"))
    # ---- Stage 3 selected
    for key, kr in sorted(sel["3"]["keys"].items()):
        clut = kr["clut"]
        tex = kr["tex"]
        blockers = ["predicted-static only: no Stage 3 draw row exists (S3-1)"]
        if (clut.get("pal_candidates_at_position") or 0) > 1:
            blockers.append(f"{clut['pal_candidates_at_position']} PAL candidates at CLUT {clut.get('vram_xy')}: drawn CLUT unknown (S3-2)")
        if tex in ("E49BC3F1", "AA5DBEF2"):
            done = key in j2a["keys"]
            blockers.append("v1 dither/granite cells documented do-not-ship; J2 proposal "
                            + ("partial output exists for this key (run 20261114T140153Z), full rerun queued" if done else "not yet produced for this key (rerun queued)"))
        rows.append(dict(stage=3, key=key, kind="selected", tex=tex, depth="4bpp (16-entry CLUT)", page_xy=S3_PAGES.get(tex),
                         selected_folder=kr["selected_folder"], group=kr["selection_group"],
                         VERIFIED=dict(tex_words="CRC-proven page words (static export stages-v4/stage3, sha == FREEZE.json)",
                                       clut_words="static export CLUT, crc32 == PAL (owner 2/0 or 2/1 stage CLUT block)"),
                         INFERRED=dict(pairing=dict(confidence=clut.get("listed_confidence"), pair_count=clut.get("pair_count"),
                                                    pal_candidates_at_position=clut.get("pal_candidates_at_position"), clut_xy=clut.get("vram_xy")),
                                       cells="inferred from page content on the 32-texel grid (no real UV rects)"),
                         art=strict_r5(key), r5_plan="root composer opt-in cutout_rgb_fill",
                         missing_evidence=["draw rows for every draw of the page (S3-1) -> tools/s3_draws_vs_cells.py",
                                           "CPU-VRAM snapshot of CLUT rows 483-497 while drawn (S3-2)",
                                           "2 s scrolling-wall hold stock/v1/material-v1 (S3-3)" if kr["selection_group"] == "machinery_and_walls" else
                                           "CAUTION sign on screen still + draw row (S3-4)" if tex == "E49BC3F1" else "live look of props"],
                         admission_blockers=blockers, admission="BLOCKED"))
    s2gate, s3gate = set(keys_file(IN["s2_gate_keys"])), set(keys_file(IN["s3_gate_keys"]))
    consistency = dict(s2_gate_keys_equal_selection=s2gate == set(sel["2"]["keys"]), s3_gate_keys_equal_selection=s3gate == set(sel["3"]["keys"]),
                       s2_only_in_gate=sorted(s2gate - set(sel["2"]["keys"])), s2_only_in_selection=sorted(set(sel["2"]["keys"]) - s2gate),
                       s3_only_in_gate=sorted(s3gate - set(sel["3"]["keys"])), s3_only_in_selection=sorted(set(sel["3"]["keys"]) - s3gate),
                       unknown_phase_file_equals_inventory=set(unk) == {k for k, v in cyc.items() if v["words"] == "UNKNOWN"})
    res = dict(owner="claude-einhander-s23", created_utc=datetime.now(timezone.utc).isoformat(), inputs=pins, consistency=consistency,
               counts=dict(rows=len(rows), by_kind={k: sum(1 for r in rows if r["kind"] == k) for k in sorted({r["kind"] for r in rows})},
                           by_admission={k: sum(1 for r in rows if r["admission"] == k) for k in sorted({r["admission"] for r in rows})}),
               rows=rows,
               legend="VERIFIED = CRC/sha proof or an actual logged draw row. INFERRED = static prediction, listed pairing or inferred cell. "
                      "No row is live-confirmed or look-accepted; GPU/live capture belongs to codex-einhander.")
    p = out + "/admission-checklist.json"
    json.dump(res, open(p, "w", encoding="utf-8"), indent=1)
    md = ["# Stage 2 / 3 keyed admission checklist (claude-einhander-s23)", "",
          f"Generated {res['created_utc']}. JSON: admission-checklist.json. VERIFIED = CRC/sha proof or a logged draw row; INFERRED = prediction.",
          f"Gate-key files vs s23 selection: S2 equal={consistency['s2_gate_keys_equal_selection']}, S3 equal={consistency['s3_gate_keys_equal_selection']}; "
          f"60-phase file equals inventory={consistency['unknown_phase_file_equals_inventory']}.", "",
          "| St | Key | Kind | Page xy | CLUT (static / drawn) | Draw rows | Strict / R5 px (2048) | Admission | Blockers |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        dr = (r["VERIFIED"].get("draw_rows") or {}) if isinstance(r["VERIFIED"], dict) else {}
        cl = r["INFERRED"].get("clut_slot_static") or (r["INFERRED"].get("pairing") or {}).get("clut_xy")
        art = r.get("art") or {}
        av = art.get("VERIFIED") or {}
        sr = f"{'pass' if av.get('strict_whole_cell_pass') else ('-' if not av else 'FAIL')} / {(av.get('r5_fringe_px') or {}).get('page2048', '-')}"
        md.append(f"| {r['stage']} | {r['key']} | {r['kind']} | {r.get('page_xy')} | {cl} / {dr.get('clut_xy_seen', '-')} | {dr.get('rows', 0) or 0} | {sr} | "
                  f"{r['admission']} | {'; '.join(r['admission_blockers'])[:180]} |")
    open(out + "/ADMISSION-CHECKLIST.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(json.dumps(dict(out=p, sha256=sha(p), md_sha256=sha(out + "/ADMISSION-CHECKLIST.md"), consistency=consistency, counts=res["counts"])))


if __name__ == "__main__":
    main(sys.argv[1])
