#!/usr/bin/env python3
"""s67 (claude-einhander-s67) Stage 6 selection reconcile. LIGHT CPU, READ-ONLY on w7-stage6.

Builds the per-key selection map for the 101 Stage 6 candidate keys (83 batch 2 + 18 batch 1) from the frozen manifests and
the lane ledger, applying the lane's own supersede/fallback/failed rules, and records for every selected key:
  * the selected folder + manifest sha256, version role (new key / replacement version of an existing key),
  * native source proof from the frozen 32 KiB copies: CRC32(words) == TEX, CRC32(clut) == CLUT (cheap; no PNG decode),
  * native class census of the page under that CLUT (cutout / opaque / STP texel counts) to size the strict audit,
  * the manifest's recorded gates and the gate TYPE (texel-centre only vs whole-cell), and PNG file presence/size only.
NO PNG decode, NO PNG hashing, NO pixel test (those wait for a shared CPU slot).
Writes ONLY C:/github/Einhander/remaster-audit/parallel-stages-20261114/s67/stage6/selection-map-<UTC>.json."""
import datetime
import hashlib
import json
import zlib
from pathlib import Path

import numpy as np

ROOT = Path("C:/github/Einhander")
S6 = ROOT / "remaster-audit/comfy-authoring/w7-stage6"
OUT = ROOT / "remaster-audit/parallel-stages-20261114/s67/stage6"
LANE = ROOT / "remaster-audit/runtime-review/seven-stage-status-20261114/lane-readiness-20261114T131712Z.json"
GATE_KEYS = [ROOT / "remaster-audit/runtime-diagnostics-v58/capture-checklists/keys/S6-gate-keys.txt",
             ROOT / "remaster-audit/claude-backlog/capture-checklists/keys/S6-gate-keys.txt"]

# Per-texture selection, from LEDGER.json (frozen_batch1 / frozen_batch2 / frozen_20261113_gpu / chunk_fxv4_20261113 / failed).
SELECT = {
    "10932164": ("stage6-large-explosion-10932164-v1", "batch1", "new"),
    "E653AA46": ("stage6-electric-bolts-E653AA46-v1", "batch1", "new"),
    "CB07BBCB": ("stage6-camo-craft-CB07BBCB-v1", "batch1", "new"),
    "D552405C": ("stage6-smoke-exhaust-D552405C-v4", "batch1", "replacement_version"),   # v4 preferred, v1 fallback
    "43C26C42": ("stage6-vram320-0-43C26C42-61A869E5-v1", "batch2", "new"),             # fx-v2 FAILED -> v1 retained
    "61A869E5": ("stage6-vram320-0-43C26C42-61A869E5-v1", "batch2", "new"),
    "20961255": ("stage6-vram704-0-20961255-fx-v2", "batch2", "replacement_version"),   # supersedes v1 keys
    "E0849F81": ("stage6-vram704-0-20961255-E0849F81-v1", "batch2", "new"),
    "8F498326": ("stage6-vram384-0-8F498326-fx-v2", "batch2", "replacement_version"),   # supersedes v1 keys
    "F07625EE": ("stage6-vram384-0-8F498326-F07625EE-v1", "batch2", "new"),
    "03F5CF11": ("stage6-vram448-0-03F5CF11-A5969BC9-v1", "batch2", "new"),
    "A5969BC9": ("stage6-vram448-0-03F5CF11-A5969BC9-v1", "batch2", "new"),
}
ALTERNATES = {  # retained, NOT selected, NOT additive
    "D552405C": ["stage6-smoke-exhaust-D552405C-v1"],
    "20961255": ["stage6-vram704-0-20961255-E0849F81-v1"],
    "8F498326": ["stage6-vram384-0-8F498326-F07625EE-v1"],
}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def crc(b):
    return "%08X" % (zlib.crc32(b) & 0xFFFFFFFF)


def rel(p):
    return str(Path(p).relative_to(ROOT)).replace("\\", "/")


def words_idx(wb, width_words=64):
    w = np.frombuffer(wb, "<u2").reshape(-1, width_words)
    idx = np.zeros((w.shape[0], width_words * 4), np.uint8)
    for k in range(4):
        idx[:, k::4] = (w >> (4 * k)) & 0xF
    return idx


def class_census(idx, clut_bytes):
    rr = np.frombuffer(clut_bytes, "<u2").astype(np.int64)
    cls = np.where(rr == 0, 0, np.where(rr & 0x8000, 255, 127)).astype(np.uint8)
    nat = cls[idx]
    return dict(cutout=int((nat == 0).sum()), opaque=int((nat == 127).sum()), stp=int((nat == 255).sum()),
                indices_used=int(len(np.unique(idx))), clut_entries_zero=int((rr == 0).sum()),
                clut_entries_stp=int(((rr & 0x8000) != 0).sum()))


def stage1_record(key):
    """Batch1 10932164 Stage1-reused keys keep their CLUT copy in the Stage 1 w2-effects source."""
    m = json.loads((S6 / "frozen/stage6-large-explosion-10932164-v1/manifest.json").read_text(encoding="utf-8"))
    for k in m.get("stage1_keys_checked") or []:
        if k["key"] == key:
            return k
    return None


def ledger_entry(ledger, name, kind):
    for sect in ("frozen_batch1", "frozen_batch2", "frozen_20261113_gpu", "failed"):
        e = (ledger.get(sect) or {}).get(name) or (ledger.get(sect) or {}).get(f"{kind}/{name}")
        if e:
            return e
    return ((ledger.get("chunk_fxv4_20261113") or {}).get("result") or {}).get(f"{kind}/{name}") or {}


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    ledger_p = S6 / "LEDGER.json"
    ledger = json.loads(ledger_p.read_text(encoding="utf-8"))
    lane = json.loads(LANE.read_text(encoding="utf-8"))
    lane6 = next(s for s in lane["stages"] if s["stage"] == 6)

    folders = {}
    for kind in ("frozen", "failed"):
        for mf in sorted((S6 / kind).glob("*/manifest.json")):
            m = json.loads(mf.read_text(encoding="utf-8"))
            folders[mf.parent.name] = dict(kind=kind, path=rel(mf.parent), manifest_sha256=sha(mf), m=m,
                                           keys=[k["key"] for k in m.get("keys", [])])

    rows, idx_cache, problems = [], {}, []
    for tex, (fname, batch, role) in SELECT.items():
        f = folders[fname]
        for k in f["m"]["keys"]:
            key = k["key"]
            if key[:8] != tex:
                continue
            pal = key[9:]
            src = S6 / "frozen" / fname / "source"
            wp = src / f"{tex}.words.bin"
            row = dict(key=key, tex=tex, clut=pal, batch=batch, selected_folder=f["path"], manifest_sha256=f["manifest_sha256"],
                       role=role, status=k.get("status"), origin=k.get("origin"), import_rule=k.get("import_rule"))
            if tex not in idx_cache:
                wb = wp.read_bytes()
                idx_cache[tex] = (words_idx(wb), crc(wb), sha(wp))
            idx, wcrc, wsha = idx_cache[tex]
            row.update(words=rel(wp), words_sha256=wsha, words_crc=wcrc, words_crc_proven=wcrc == tex)
            cp = src / f"{tex}-{pal}.clut.bin"
            s1 = None
            if cp.exists():
                cb = cp.read_bytes()
                row.update(clut_file=rel(cp), clut_sha256=sha(cp), clut_crc=crc(cb), clut_crc_proven=crc(cb) == pal,
                           native_class=class_census(idx, cb))
            else:
                s1 = stage1_record(key)
                row.update(clut_file=None, clut_crc_proven=None,
                           clut_note="no Stage 6 CLUT copy; Stage 1 byte-for-byte reuse (manifest clut_crc_ok=%s, stage1_clut_xy=%s)"
                                     % ((s1 or {}).get("clut_crc_ok"), (s1 or {}).get("stage1_clut_xy")))
                problems.append(f"{key}: CLUT words not in the Stage 6 source copy (Stage 1 byte-for-byte reuse); "
                                "strict audit must take the CLUT from the Stage 1 w2-effects source")
            files = {}
            for tag in ("2048", "1024"):
                r = k.get(f"png_{tag}") or ((s1 or stage1_record(key) or {}).get(f"png_{tag}"))
                if r is None:
                    files[tag] = dict(error="no png record in manifest")
                    problems.append(f"{key}: no png_{tag} record")
                    continue
                fp = S6 / "frozen" / fname / r["path"]
                files[tag] = dict(path=r["path"], manifest_sha256=r["sha256"], exists=fp.exists(),
                                  bytes=fp.stat().st_size if fp.exists() else None, size=r.get("size"),
                                  byte_identical_to_stage1=r.get("byte_identical_to_stage1"), stage1_file=r.get("stage1_file"))
                if not fp.exists():
                    problems.append(f"{key}: missing {r['path']}")
            row["files"] = files
            g = k.get("gates") or ((s1 or {}).get("gates")) or {}
            row["recorded_gates"] = {t: dict(g.get(t) or {}) for t in ("2048", "1024")}
            row["recorded_gate_type"] = "texel-centre only (2x2 px straddling each native texel centre); NOT whole-cell"
            row["whole_cell_strict"] = "NOT RUN (needs CPU slot: proto-v2b cm_validate R1-R4 + cm_flags_ex connectivity)"
            row["alternates_retained"] = [folders[a]["path"] for a in ALTERNATES.get(tex, []) if key in folders[a]["keys"]]
            rows.append(row)

    sel = [r["key"] for r in rows]
    dup = sorted({k for k in sel if sel.count(k) > 1})
    gate_sets = {}
    for gp in GATE_KEYS:
        if gp.exists():
            ks = [x.strip() for x in gp.read_text(encoding="utf-8").splitlines() if x.strip()]
            gate_sets[rel(gp)] = dict(sha256=sha(gp), count=len(ks), only_in_gate=sorted(set(ks) - set(sel)),
                                      only_in_selection=sorted(set(sel) - set(ks)))
    lane_folders = {Path(c["path"]).name for c in lane6["candidate_folders"]}
    sel_folders = {r["selected_folder"].split("/")[-1] for r in rows}
    stage1_reused = [r["key"] for r in rows if (r.get("origin") or "").startswith("Stage 1")]
    failed = {}
    for n, f in folders.items():
        if f["kind"] != "failed":
            continue
        e = ledger_entry(ledger, n, "failed")
        failed[n] = dict(path=f["path"], manifest_sha256=f["manifest_sha256"], keys=f["keys"], ledger_why=e.get("why"),
                         ledger_manifest_sha256=e.get("manifest_sha256"),
                         manifest_hash_matches_ledger=(e.get("manifest_sha256") == f["manifest_sha256"]) if e.get("manifest_sha256") else None,
                         overlaps_selected_keys=sorted(set(f["keys"]) & set(sel)))
    frozen_hashes = {}
    for n, f in folders.items():
        if f["kind"] != "frozen":
            continue
        want = ledger_entry(ledger, n, "frozen").get("manifest_sha256")
        lane_h = next((c["manifest_sha256"] for c in lane6["candidate_folders"] if Path(c["path"]).name == n), None)
        frozen_hashes[n] = dict(actual=f["manifest_sha256"], ledger=want, lane_readiness=lane_h,
                                ledger_ok=(want == f["manifest_sha256"]) if want else None,
                                lane_ok=(lane_h == f["manifest_sha256"]) if lane_h else None,
                                selected_keys=sum(1 for r in rows if r["selected_folder"].endswith(n)), all_keys=len(f["keys"]))
    by_tex = {}
    for r in rows:
        by_tex[r["tex"]] = by_tex.get(r["tex"], 0) + 1
    res = dict(
        run=stamp, owner="claude-einhander-s67", task="EIN-S6-WHOLE-CELL-20261114",
        inputs=dict(ledger=dict(path=rel(ledger_p), sha256=sha(ledger_p), written=ledger.get("written")),
                    lane_readiness=dict(path=rel(LANE), sha256=sha(LANE))),
        totals=dict(selected_keys=len(rows), unique=len(set(sel)), duplicates=dup, by_tex=by_tex,
                    batch2=sum(r["batch"] == "batch2" for r in rows), batch1=sum(r["batch"] == "batch1" for r in rows),
                    replacement_version_keys=sum(r["role"] == "replacement_version" for r in rows),
                    new_keys=sum(r["role"] == "new" for r in rows), stage1_reused_keys=stage1_reused,
                    stage6_own_render_keys=len(rows) - len(stage1_reused),
                    words_crc_proven=sum(bool(r.get("words_crc_proven")) for r in rows),
                    clut_crc_proven=sum(bool(r.get("clut_crc_proven")) for r in rows),
                    png_files_present=sum(1 for r in rows for f in r["files"].values() if f.get("exists")),
                    keys_with_stp_texels=sum(1 for r in rows if (r.get("native_class") or {}).get("stp", 0) > 0),
                    whole_cell_strict_run=0),
        gate_key_files=gate_sets,
        lane_readiness_folder_check=dict(listed=sorted(lane_folders), selected=sorted(sel_folders),
                                         selected_but_not_listed=sorted(sel_folders - lane_folders),
                                         listed_but_not_selected=sorted(lane_folders - sel_folders)),
        frozen_manifest_hashes=frozen_hashes, failed_preserved=failed, alternates=ALTERNATES, problems=problems, rows=rows,
        limits=["No PNG decode or PNG hashing: PNG checks are presence/size only against manifest-recorded sha256.",
                "All recorded lane gates are texel-centre checks; no whole-cell strict class result exists for any Stage 6 key.",
                "All keys are predicted-static (stages-v4/stage6 for batch 2/fx-v2, stages/stage6 for batch 1); live key/CLUT unconfirmed.",
                "Set A/B residency, GP0 part masks, real quad sizes/animation order and runtime CLUTs are absent (CR-S6-1..5)."],
        status="DATA ONLY; read-only on w7-stage6; no art edits")
    out = OUT / f"selection-map-{stamp}.json"
    out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    t = res["totals"]
    print("selected", t["selected_keys"], "unique", t["unique"], "dups", t["duplicates"], "b2", t["batch2"], "b1", t["batch1"],
          "repl", t["replacement_version_keys"], "new", t["new_keys"], "stage1_reused", len(t["stage1_reused_keys"]))
    print("words_crc", t["words_crc_proven"], "clut_crc", t["clut_crc_proven"], "png_present", t["png_files_present"],
          "stp_keys", t["keys_with_stp_texels"])
    print("gate files", json.dumps(gate_sets))
    print("lane folder check", json.dumps(res["lane_readiness_folder_check"]))
    print("frozen hashes", json.dumps({n: (v["ledger_ok"], v["lane_ok"], v["selected_keys"], v["all_keys"]) for n, v in frozen_hashes.items()}))
    print("failed", json.dumps({n: (v["manifest_hash_matches_ledger"], len(v["keys"]), v["overlaps_selected_keys"][:3]) for n, v in failed.items()}))
    print("problems", len(problems), problems[:6])
    print("out", out, sha(out))


if __name__ == "__main__":
    main()
