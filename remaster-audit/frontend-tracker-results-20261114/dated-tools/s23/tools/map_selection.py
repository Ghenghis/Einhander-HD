"""s23 Stage 2/3 selection map (claude-einhander-s23).

Read-only metadata pass. It reads the frozen candidate manifests named by the
lane-readiness report, applies the per-key current-selection rules from the
w7-stage2 / w7-stage3 ledgers, re-hashes every selected and alternative key
PNG (bytes only, no PNG decode), and records what proof exists for each key:

  * centre-only class proof  : the manifests' own class_validation rule
                               ("class at every native texel centre"), plus
                               forced_texel_centres (centre stamps) per file.
  * strict whole-cell proof  : R2 displacement / R4 connectivity / R3 interior
                               from claude-backlog/class-mip DESIGN-V2. Not run
                               here (needs PNG decode = pixel job, CPU slot).
  * live/source proof        : draw records, CLUT kind and PAL competition.

Usage:  python -I map_selection.py <out_dir>
Writes <out_dir>/selection-map.json and <out_dir>/SELECTION-MAP.md.
Nothing outside <out_dir> is written.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

ROOT = "C:/github/Einhander"
READINESS = ROOT + "/remaster-audit/runtime-review/seven-stage-status-20261114/lane-readiness-20261114T131712Z.json"
READINESS_SHA = "07cd9358083107da96bc209dc1bfa8685820c1316f1455c146c31ac6fc2283b8"
S2 = ROOT + "/remaster-audit/comfy-authoring/w7-stage2/frozen"
S3 = ROOT + "/remaster-audit/comfy-authoring/w7-stage3/frozen"


def below_normal():
    try:
        import ctypes
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    except Exception:
        pass


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(folder):
    p = folder + "/manifest.json"
    return json.load(open(p, encoding="utf-8")), sha256(p)


# Selection rules, verbatim from w7-stage2/LEDGER.md "Current set per key" and
# the lane-readiness candidate_selection counts.
S2_FLAMES, S2_GLOW, S2_SMOKE = "AD934A7E-FC338604", "4915FBCF-056E3BD0", "3DD37B6B-AFAD5A36"
S2_GROUND_RETAINED_V2 = "65560E82-83E366BC"


def s2_selection(manifests):
    sel = {}
    for k in manifests["stage2-prep-v2"]["keys"]:
        sel[k] = ("stage2-prep-v2", "phase_prep_v2")
    for k in manifests["stage2-train-cars-v4"]["keys"]:
        sel[k] = ("stage2-train-cars-v4", "train_cars_v4")
    for k in manifests["stage2-sky-ground-v3"]["keys"]:
        sel[k] = ("stage2-sky-ground-v3", "sky_ground_v3")
    assert S2_GROUND_RETAINED_V2 in manifests["stage2-sky-ground-v2"]["keys"]
    sel[S2_GROUND_RETAINED_V2] = ("stage2-sky-ground-v2", "sky_ground_retained_v2")
    for k in (S2_FLAMES, S2_GLOW):
        assert k in manifests["stage2-opening-fx-v2"]["keys"]
        sel[k] = ("stage2-opening-fx-v2", "opening_fx_v2")
    assert S2_SMOKE in manifests["stage2-opening-fx-v3"]["keys"]
    sel[S2_SMOKE] = ("stage2-opening-fx-v3", "opening_fx_v3")
    for k in manifests["stage2-opening-fx-v1"]["keys"]:
        if k not in sel:
            sel[k] = ("stage2-opening-fx-v1", "opening_fx_retained_v1")
    return sel


def s3_selection(manifests):
    sel = {}
    for k in manifests["stage3-machinery-walls-v1"]["keys"]:
        sel[k] = ("stage3-machinery-walls-v1", "machinery_and_walls")
    for k in manifests["stage3-signage-props-v1"]["keys"]:
        sel[k] = ("stage3-signage-props-v1", "signage_props")
    return sel


# Documented defects that must not ship (w7-stage3/LEDGER.md, signage-v1 honest read).
S3_DO_NOT_SHIP_PAGES = {"E49BC3F1": "dithered brick wall + CAUTION-plate stipple become cellular camouflage; ledger: should not ship from this method",
                        "AA5DBEF2": "dithered granite panels become cellular camouflage; ledger: should not ship from this method"}


def file_records(folder_path, entry):
    out = {}
    for res, f in (entry.get("files") or {}).items():
        p = folder_path + "/" + f["path"]
        rec = {k: f.get(k) for k in ("path", "sha256", "dims", "px_per_texel", "forced_texel_centres", "class_mismatches", "alpha_values")}
        if os.path.exists(p):
            actual = sha256(p)
            rec["sha256_actual"] = actual
            rec["sha256_ok"] = actual == f.get("sha256")
            rec["bytes"] = os.path.getsize(p)
        else:
            rec["sha256_actual"] = None
            rec["sha256_ok"] = False
            rec["missing"] = True
        out[res] = rec
    return out


def live_summary(entry):
    live = entry.get("live")
    if not live:
        return {"draw_records": 0, "note": "no draw record in manifest (predicted from static export only)"}
    return {"draw_records": live.get("draws"), "frames": live.get("frames"), "runs": live.get("runs"),
            "clut_xy": live.get("clut_xy"), "semi": live.get("semi"), "uv_top": live.get("uv_top")}


def clut_summary(entry):
    c = entry.get("clut") or {}
    out = {"crc32": c.get("crc32"), "kind": c.get("kind"), "vram_xy": c.get("vram_xy")}
    listed = entry.get("listed")
    if isinstance(listed, dict):
        out["listed_confidence"] = listed.get("confidence")
        out["pal_candidates_at_position"] = listed.get("pal_candidates_at_position")
        out["pair_count"] = listed.get("pair_count")
    if "listed_in_export" in entry:
        out["listed_in_export"] = entry["listed_in_export"]
    return out


def main(out_dir):
    below_normal()
    os.makedirs(out_dir, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    readiness_sha = sha256(READINESS)
    readiness = json.load(open(READINESS, encoding="utf-8"))
    pinned = {}
    for st in readiness["stages"]:
        if st["stage"] in (2, 3):
            for f in st["candidate_folders"]:
                pinned[os.path.basename(f["path"].replace("\\", "/"))] = f["manifest_sha256"]

    report = {"tool": "s23/tools/map_selection.py", "tool_sha256": sha256(os.path.abspath(__file__)),
              "owner": "claude-einhander-s23", "started_utc": started,
              "readiness": {"path": READINESS, "sha256": readiness_sha, "expected": READINESS_SHA, "ok": readiness_sha == READINESS_SHA},
              "pixel_decode": False,
              "proof_scope": "metadata only: manifest pins, byte hashes, recorded centre-only checks, recorded draw/CLUT evidence. "
                             "No strict whole-cell (R2/R3/R4) result is claimed here.",
              "stages": {}}

    for stage, base, folders, selector in (
            (2, S2, ["stage2-prep-v2", "stage2-sky-ground-v2", "stage2-sky-ground-v3", "stage2-train-cars-v4",
                     "stage2-opening-fx-v1", "stage2-opening-fx-v2", "stage2-opening-fx-v3",
                     # superseded, mapped only as alternatives / history
                     "stage2-prep-v1", "stage2-sky-ground-v1", "stage2-train-cars-v1", "stage2-train-cars-v2", "stage2-train-cars-v3"],
             s2_selection),
            (3, S3, ["stage3-machinery-walls-v1", "stage3-signage-props-v1", "stage3-machinery-walls-material-v1"], s3_selection)):
        manifests, msha = {}, {}
        for name in folders:
            manifests[name], msha[name] = load(base + "/" + name)
        sel = selector(manifests)
        folder_info = {}
        for name in folders:
            m = manifests[name]
            folder_info[name] = {"manifest_sha256": msha[name], "pinned_by_readiness": pinned.get(name),
                                 "pin_ok": (pinned.get(name) == msha[name]) if name in pinned else None,
                                 "status": m.get("status"), "keys": len(m.get("keys") or {}),
                                 "class_validation": m.get("class_validation"),
                                 "supersedes": m.get("supersedes")}
        keys = {}
        page_methods = {}
        for key in sorted(sel):
            folder, group = sel[key]
            entry = manifests[folder]["keys"][key]
            tex = entry.get("tex") or key.split("-")[0]
            rec = {"selected_folder": folder, "selection_group": group, "tex": tex,
                   "state": entry.get("state"), "clut": clut_summary(entry), "live": live_summary(entry),
                   "files": file_records(base + "/" + folder, entry),
                   "alternatives": {}}
            for other in folders:
                if other != folder and key in (manifests[other].get("keys") or {}):
                    oe = manifests[other]["keys"][key]
                    rec["alternatives"][other] = {"status": manifests[other].get("status"),
                                                  "files": file_records(base + "/" + other, oe)}
            forced = {r: f.get("forced_texel_centres") for r, f in rec["files"].items()}
            rec["proof"] = {
                "centre_only_class": all((f.get("class_mismatches") == 0) for f in rec["files"].values()),
                "forced_texel_centres": forced,
                "centre_stamp_risk": any((v or 0) > 0 for v in forced.values()),
                "strict_whole_cell": "NOT RUN (pixel decode needs a CPU slot)",
                "live_key_clut_confirmed": False,
                "missing": [m for m in (
                    "live key + CLUT confirmation (validate_predicted confirm + gate)",
                    "strict whole-cell R2/R4 (+R3 diagnostic) on every file",
                    "full-rate draw/UV coverage" if not entry.get("live") else "full-rate draw/UV coverage (current records are sampled)",
                    "live motion/shimmer A/B")],
            }
            if stage == 3 and tex in S3_DO_NOT_SHIP_PAGES:
                rec["proof"]["documented_defect"] = S3_DO_NOT_SHIP_PAGES[tex]
                rec["proof"]["ship_status"] = "BLOCKED (documented rejected cells; isolated repair proposal required)"
            if rec["clut"].get("pal_candidates_at_position") and rec["clut"]["pal_candidates_at_position"] > 1:
                rec["proof"]["palette_ambiguity"] = f'{rec["clut"]["pal_candidates_at_position"]} PAL candidates at this CLUT position'
            if (rec["clut"].get("kind") or "").startswith("recovered"):
                rec["proof"]["palette_source"] = "recovered from CRC-validated CPU-VRAM snapshot (not in static export)"
            keys[key] = rec
            page_methods.setdefault(tex, {}).setdefault(folder, []).append(key)
        multi = {t: v for t, v in page_methods.items() if len(v) > 1}
        report["stages"][str(stage)] = {
            "selected_keys": len(keys),
            "selection_counts": {g: sum(1 for r in keys.values() if r["selection_group"] == g) for g in sorted({r["selection_group"] for r in keys.values()})},
            "folders": folder_info,
            "pages": {t: {f: sorted(v) for f, v in d.items()} for t, d in sorted(page_methods.items())},
            "pages_with_mixed_methods": multi,
            "keys": keys,
        }
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    out = out_dir + "/selection-map.json"
    with open(out + ".tmp", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    os.replace(out + ".tmp", out)
    write_md(report, out_dir + "/SELECTION-MAP.md")
    print(json.dumps({"ok": True, "out": out, "sha256": sha256(out)}))


def write_md(r, path):
    L = ["# Stage 2/3 selection map (claude-einhander-s23)", "",
         f"Generated {r['finished_utc']} by `{r['tool']}` (sha256 `{r['tool_sha256']}`).",
         f"Readiness pin `{r['readiness']['sha256']}` ok={r['readiness']['ok']}. Pixel decode: **none**. "
         "Strict whole-cell results: **none claimed**. Every key below is predicted-static.", ""]
    for st, s in r["stages"].items():
        L += [f"## Stage {st}: {s['selected_keys']} selected keys", "",
              "| Group | Keys |", "|---|---:|"] + [f"| {g} | {n} |" for g, n in s["selection_counts"].items()] + [""]
        L += ["| Folder | manifest sha256 | readiness pin ok | status | keys |", "|---|---|---|---|---:|"]
        for n, fi in s["folders"].items():
            L.append(f"| {n} | `{fi['manifest_sha256'][:16]}…` | {fi['pin_ok']} | {fi['status']} | {fi['keys']} |")
        L += ["", "| Key | Selected | CLUT kind | draws | forced centres (2048/1024) | bytes ok | flags |", "|---|---|---|---:|---|---|---|"]
        for k, kr in s["keys"].items():
            fc = kr["proof"]["forced_texel_centres"]
            ok = all(f.get("sha256_ok") for f in kr["files"].values()) and all(
                f.get("sha256_ok") for a in kr["alternatives"].values() for f in a["files"].values())
            flags = []
            if kr["proof"].get("documented_defect"): flags.append("DO-NOT-SHIP")
            if kr["proof"].get("palette_ambiguity"): flags.append(kr["proof"]["palette_ambiguity"])
            if kr["proof"].get("palette_source"): flags.append("recovered CLUT")
            if kr["proof"]["centre_stamp_risk"]: flags.append("centre stamps")
            L.append(f"| {k} | {kr['selected_folder']} | {kr['clut'].get('kind')} | {kr['live'].get('draw_records')} | "
                     f"{fc.get('page2048')}/{fc.get('page1024')} | {ok} | {'; '.join(flags)} |")
        if s["pages_with_mixed_methods"]:
            L += ["", "Pages whose selected keys come from more than one method/folder (phase consistency must be checked):", ""]
            for t, d in s["pages_with_mixed_methods"].items():
                L.append(f"- {t}: " + "; ".join(f"{f}: {', '.join(v)}" for f, v in d.items()))
        L.append("")
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
