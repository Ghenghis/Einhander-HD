"""Join the s23 selection map with an existing strict whole-cell audit result (claude-einhander-s23).

Read-only. No PNG decode. Inputs are two JSON files; the output goes to <out_dir>.
  python -I join_strict.py <selection-map.json> <later-stages result.json> <out_dir>

For every selected file (and every alternative file) it records the audit row's R1..R5,
connectivity-only and drawn-rect counts, flags missing rows, and compares the lane's
recorded forced_texel_centres with the manifest value.  It does not re-validate pixels;
the cross-check of the audit's own correctness is a separate (pixel) job.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def norm(p):
    return os.path.normcase(os.path.normpath(p.replace("/", os.sep)))


def main(sel_path, res_path, out_dir):
    sel = json.load(open(sel_path, encoding="utf-8"))
    res = json.load(open(res_path, encoding="utf-8"))
    rows = {}
    for r in res["rows"]:
        if "path" in r:
            rows[norm(r["path"])] = r
    base = {"2": "C:/github/Einhander/remaster-audit/comfy-authoring/w7-stage2/frozen",
            "3": "C:/github/Einhander/remaster-audit/comfy-authoring/w7-stage3/frozen"}
    out = {"tool": "s23/tools/join_strict.py", "tool_sha256": sha256(os.path.abspath(__file__)),
           "created_utc": datetime.now(timezone.utc).isoformat(),
           "selection_map": {"path": sel_path, "sha256": sha256(sel_path)},
           "strict_audit": {"path": res_path, "sha256": sha256(res_path), "run": res.get("run"), "rule": res.get("rule"),
                            "note": "produced by claude-einhander (original), not by s23; joined here, not re-run"},
           "stages": {}}
    for st, s in sel["stages"].items():
        keys_out, tot = {}, {"files": 0, "rows_found": 0, "strict_pass": 0, "primary_pass": 0, "r5_fringe_files": 0,
                             "r5_fringe_px": 0, "lane_forced_mismatch": 0, "errors": 0}
        for k, kr in s["keys"].items():
            def one(folder, fk, f):
                p = norm(base[st] + "/" + folder + "/" + f["path"])
                r = rows.get(p)
                if r is None:
                    return {"row": None}
                if "error" in r:
                    return {"row": "error", "error": r["error"]}
                v2 = r["v2"]
                return {"row": "ok", "scale": r["scale"], "strict_pass": r["strict_pass"], "primary_pass": r["primary_pass"],
                        "r1": v2["r1_centre_bad"], "r2_px": v2["r2_displaced_px"], "r3_px": v2["r3_uniform_bad_px"],
                        "r4_px": v2["r4_island_px"], "r5_fringe_px": v2["r5_fringe_px"],
                        "r5_fringe_share_of_pixels": round(v2["r5_fringe_px"] / v2["pixels"], 6) if v2["pixels"] else None,
                        "pinhole_cells": v2["pinhole_cells"], "nonclass_px": v2["nonclass_px"], "conn_viol_px": r["conn_viol_px"],
                        "drawn": r.get("drawn"), "crc_proven": r.get("crc_proven"), "words_sha_ok": r.get("words_sha_ok"),
                        "lane_reported_forced": (r.get("lane_reported") or {}).get("forced_texel_centres"),
                        "manifest_forced": f.get("forced_texel_centres"),
                        "file_sha256_at_map": f.get("sha256_actual")}
            sel_files = {fk: one(kr["selected_folder"], fk, f) for fk, f in kr["files"].items()}
            alt = {a: {fk: one(a, fk, f) for fk, f in ad["files"].items()} for a, ad in kr["alternatives"].items()}
            for j in sel_files.values():
                tot["files"] += 1
                if j["row"] == "ok":
                    tot["rows_found"] += 1
                    tot["strict_pass"] += int(j["strict_pass"])
                    tot["primary_pass"] += int(j["primary_pass"])
                    if j["r5_fringe_px"]:
                        tot["r5_fringe_files"] += 1
                        tot["r5_fringe_px"] += j["r5_fringe_px"]
                    if j["lane_reported_forced"] != j["manifest_forced"]:
                        tot["lane_forced_mismatch"] += 1
                elif j["row"] == "error":
                    tot["errors"] += 1
            keys_out[k] = {"selected_folder": kr["selected_folder"], "selection_group": kr["selection_group"],
                           "selected": sel_files, "alternatives": alt,
                           "documented_defect": kr["proof"].get("documented_defect"),
                           "palette_ambiguity": kr["proof"].get("palette_ambiguity"),
                           "palette_source": kr["proof"].get("palette_source"),
                           "draw_records": kr["live"].get("draw_records")}
        out["stages"][st] = {"totals_selected": tot, "keys": keys_out}
    os.makedirs(out_dir, exist_ok=True)
    p = out_dir + "/strict-join.json"
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    os.replace(p + ".tmp", p)
    print(json.dumps({"ok": True, "out": p, "sha256": sha256(p),
                      "totals": {st: v["totals_selected"] for st, v in out["stages"].items()}}))


if __name__ == "__main__":
    main(*sys.argv[1:4])
