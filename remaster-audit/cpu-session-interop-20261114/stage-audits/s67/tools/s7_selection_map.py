#!/usr/bin/env python3
"""s67 (claude-einhander-s67) Stage 7 selection + master inventory reconcile. LIGHT CPU, READ-ONLY on w7-stage7.

For the 26 Stage 7 exported candidate keys (fleet parts 22, backdrop 2, planet limb 2) records: folder + manifest sha256,
listed/unlisted status against stages-v4/stage7/keys.json (563 predicted keys), CRC proof of the page words (static export
copy named by the manifest) and of the manifest CLUT words, native class census, recorded centre gates / forced centres,
PNG presence/size (no decode, no hashing). Inventories the export-less masters (explosion 966EEDF1 v1/v2, hull masters
7622FFA1/E8241ECC/636344D8, transmission page 3F4CA363 v1/v2, planet 9B2F0BFD) and the 3F4CA363 v2 dense-kanji fallbacks.
Evaluates the C4FDEDD2-EAD968A1 inferred pairing against the static listing and validate_predicted.py gate semantics.
Writes ONLY C:/github/Einhander/remaster-audit/parallel-stages-20261114/s67/stage7/selection-map-<UTC>.json."""
import datetime
import hashlib
import json
import zlib
from pathlib import Path

import numpy as np

ROOT = Path("C:/github/Einhander")
S7 = ROOT / "remaster-audit/comfy-authoring/w7-stage7"
OUT = ROOT / "remaster-audit/parallel-stages-20261114/s67/stage7"
SX = ROOT / "remaster-audit/fullgame-prep/static-extraction"
LANE = ROOT / "remaster-audit/runtime-review/seven-stage-status-20261114/lane-readiness-20261114T131712Z.json"
GATE = S7 / "work/gate-keys-stage7.txt"
GATE_COPY = ROOT / "remaster-audit/runtime-diagnostics-v58/capture-checklists/keys/S7-gate-keys.txt"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def crc(b):
    return "%08X" % (zlib.crc32(b) & 0xFFFFFFFF)


def rel(p):
    try:
        return str(Path(p).resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def idx_of(wb, ww, hh, nclut):
    w16 = np.frombuffer(wb, "<u2")[:ww * hh].reshape(hh, ww)
    if nclut == 16:
        return np.stack([(w16 >> (4 * k)) & 0xF for k in range(4)], axis=-1).reshape(hh, ww * 4)
    if nclut == 256:
        return np.stack([w16 & 0xFF, w16 >> 8], axis=-1).reshape(hh, ww * 2)
    raise ValueError(nclut)


def census(idx, clut_words):
    rr = np.array(clut_words, np.int64)
    cls = np.where(rr == 0, 0, np.where(rr & 0x8000, 255, 127)).astype(np.uint8)
    nat = cls[idx]
    return dict(cutout=int((nat == 0).sum()), opaque=int((nat == 127).sum()), stp=int((nat == 255).sum()),
                indices_used=int(len(np.unique(idx))), clut_entries_zero=int((rr == 0).sum()),
                clut_entries_stp=int(((rr & 0x8000) != 0).sum()))


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    v4keys = json.loads((SX / "stages-v4/stage7/keys.json").read_text(encoding="utf-8"))
    listed = {r["key"]: r for r in v4keys}
    lane = json.loads(LANE.read_text(encoding="utf-8"))
    lane7 = next(s for s in lane["stages"] if s["stage"] == 7)
    lane_h = {Path(c["path"]).name: c["manifest_sha256"] for c in lane7["candidate_folders"]}

    folders, rows, masters, problems, words_cache = {}, [], [], [], {}
    for mf in sorted((S7 / "frozen").glob("*/manifest.json")):
        d = mf.parent
        m = json.loads(mf.read_text(encoding="utf-8"))
        fs = d / "FILES.sha256.json"
        folders[d.name] = dict(path=rel(d), manifest_sha256=sha(mf), status=m.get("status"), state=m.get("state"),
                               keys=sorted((m.get("keys") or {}).keys()), files_sha256_json=sha(fs) if fs.exists() else None,
                               lane_readiness_sha256=lane_h.get(d.name))
        folders[d.name]["lane_ok"] = (lane_h[d.name] == folders[d.name]["manifest_sha256"]) if d.name in lane_h else None
        pages = m.get("pages") or {}
        if not pages and isinstance(m.get("page"), dict):
            pages = {m["page"].get("tex") or m["page"].get("texture_crc") or "?": m["page"]}
        for tex, pg in pages.items():
            w = pg.get("words") if isinstance(pg, dict) else None
            rect = pg.get("vram_rect_words") if isinstance(pg, dict) else None
            if isinstance(w, dict) and w.get("path") and Path(w["path"]).exists():
                b = Path(w["path"]).read_bytes()
                words_cache.setdefault(tex, dict(path=rel(w["path"]), sha256=hashlib.sha256(b).hexdigest(), crc=crc(b),
                                                 crc_proven=crc(b) == tex, manifest_sha256=w.get("sha256"), rect=rect, b=b))
            mk = sorted(k for k in (m.get("keys") or {}) if k.startswith(tex))
            if not mk:
                masters.append(dict(folder=d.name, tex=tex, member=pg.get("member") if isinstance(pg, dict) else None,
                                    confidence=pg.get("confidence") if isinstance(pg, dict) else None,
                                    listed_keys=pg.get("listed_keys") if isinstance(pg, dict) else None,
                                    master=pg.get("master") if isinstance(pg, dict) else None,
                                    keyed_runtime_exports=0))
        if not (m.get("keys") or {}) and not pages:
            masters.append(dict(folder=d.name, tex=(m.get("page") or {}).get("tex") if isinstance(m.get("page"), dict) else None,
                                page=m.get("page"), key_exports=m.get("key_exports"), keyed_runtime_exports=0,
                                master=m.get("master") if isinstance(m.get("master"), (dict, str)) else None))
        for key, k in (m.get("keys") or {}).items():
            tex, pal = key[:8], key[9:]
            cl = k.get("clut") or {}
            hx = cl.get("hex") or ""
            cw = [int.from_bytes(bytes.fromhex(hx[i:i + 4]), "little") for i in range(0, len(hx), 4)]
            cb = bytes.fromhex(hx)
            row = dict(key=key, tex=tex, clut=pal, folder=d.name, manifest_sha256=folders[d.name]["manifest_sha256"],
                       state=k.get("state"), listed_in_stages_v4=key in listed,
                       listed_confidence=(listed.get(key) or {}).get("confidence"), manifest_listed=k.get("listed"),
                       why=k.get("why"), clut_vram_xy=cl.get("vram_xy"), clut_owner=cl.get("owner"),
                       clut_crc=crc(cb), clut_crc_proven=crc(cb) == pal, clut_entries=len(cw))
            wc = words_cache.get(tex)
            if wc:
                row.update(words=wc["path"], words_crc_proven=wc["crc_proven"],
                           words_sha_matches_manifest=wc["sha256"] == wc["manifest_sha256"])
                rc = wc["rect"]
                row["native_class"] = census(idx_of(wc["b"], rc[2], rc[3], len(cw)), cw)
            else:
                row.update(words=None, words_crc_proven=None)
                problems.append(f"{key}: no page words recorded")
            files = {}
            for fk, f in (k.get("files") or {}).items():
                fp = d / f["path"]
                files[fk] = dict(path=f["path"], manifest_sha256=f["sha256"], exists=fp.exists(),
                                 bytes=fp.stat().st_size if fp.exists() else None, dims=f.get("dims"),
                                 recorded_forced_texel_centres=f.get("forced_texel_centres"),
                                 recorded_class_mismatches=f.get("class_mismatches"))
                if not fp.exists():
                    problems.append(f"{key}: missing {f['path']}")
            row["files"] = files
            row["recorded_gate_type"] = "texel-centre only (top label at each native texel centre); NOT whole-cell"
            row["whole_cell_strict"] = "NOT RUN (needs CPU slot: proto-v2b cm_validate R1-R4 + cm_flags_ex connectivity)"
            row["forced_centres_flag"] = any((f.get("recorded_forced_texel_centres") or 0) > 0 for f in files.values())
            rows.append(row)

    sel = [r["key"] for r in rows]
    gate = {}
    for gp in (GATE, GATE_COPY):
        if gp.exists():
            ks = [x.strip() for x in gp.read_text(encoding="utf-8").splitlines() if x.strip()]
            gate[rel(gp)] = dict(sha256=sha(gp), count=len(ks), only_in_gate=sorted(set(ks) - set(sel)),
                                 only_in_exports=sorted(set(sel) - set(ks)))
    # C4FDEDD2-EAD968A1 pairing
    slot_users = sorted(k for k, r in listed.items() if r.get("clut_xy") == [0, 504])
    pal_users = sorted(k for k in listed if k.endswith("-EAD968A1"))
    tex_listed = {t: sorted(k for k in listed if k.startswith(t)) for t in ("4C783149", "C4FDEDD2", "9B2F0BFD")}
    c4 = next((r for r in rows if r["key"] == "C4FDEDD2-EAD968A1"), None)
    pairing = dict(
        key="C4FDEDD2-EAD968A1", exported=c4 is not None, in_gate_list=any("C4FDEDD2-EAD968A1" not in g["only_in_exports"] for g in gate.values()),
        listed_in_stages_v4=c4["listed_in_stages_v4"] if c4 else None, listed_keys_per_planet_tex=tex_listed,
        clut_slot_0_504_listed_users=slot_users, clut_EAD968A1_listed_users=pal_users,
        words_crc_proven=(c4 or {}).get("words_crc_proven"), clut_crc_proven=(c4 or {}).get("clut_crc_proven"),
        status="INFERRED, UNCONFIRMED: no static listing pairs C4FDEDD2 with any CLUT; EAD968A1 slot 0,504 is shared by "
               f"{len(pal_users)} listed TEX, so co-use with 4C783149 is weak evidence",
        gate_semantics=("validate_predicted.py confirm/gate puts a live source of an unlisted key with a known TEX into "
                        "tex_confirmed and its import allowlist; gate therefore passes it on a complete live source of the "
                        "exact key, but it does NOT check clut_xy or draw rows. S7-1 pass criterion (a) (C4FDEDD2 drawn with "
                        "the same clut_xy as 4C783149) must be checked from capture.jsonl draw rows separately."),
        admission_rule="keep exported candidate; admit only with a complete live source for the exact key AND a draw row on "
                       "page 832,0 with clut_xy [0,504]; if drawn with another CLUT, re-render from the frozen C4FDEDD2 master")
    # 3F4CA363 v2 dense kanji
    tx = {}
    v2 = S7 / "frozen/stage7-transmission-page-3F4CA363-v2/manifest.json"
    if v2.exists():
        m2 = json.loads(v2.read_text(encoding="utf-8"))
        t = m2.get("text") or {}
        dv = t.get("dense_v1_fallback")
        tx = dict(manifest_sha256=sha(v2), dense_v1_fallback_count=(dv.get("components") if isinstance(dv, dict) else (len(dv) if dv is not None else None)),
                  dense_v1_fallback=dv, text_keys=sorted(t.keys()), key_exports=m2.get("key_exports"),
                  known_limits=m2.get("known_limits"))
    by = {}
    for r in rows:
        by.setdefault(r["folder"], 0)
        by[r["folder"]] += 1
    res = dict(
        run=stamp, owner="claude-einhander-s67", task="EIN-S7-WHOLE-CELL-20261114",
        inputs=dict(ledger=dict(path=rel(S7 / "LEDGER.md"), sha256=sha(S7 / "LEDGER.md")),
                    stages_v4_keys=dict(path=rel(SX / "stages-v4/stage7/keys.json"), sha256=sha(SX / "stages-v4/stage7/keys.json"),
                                        count=len(listed)),
                    validate_predicted=dict(path=rel(SX / "validate_predicted.py"), sha256=sha(SX / "validate_predicted.py")),
                    lane_readiness=dict(path=rel(LANE), sha256=sha(LANE))),
        totals=dict(exported_keys=len(rows), unique=len(set(sel)), by_folder=by,
                    listed=sum(r["listed_in_stages_v4"] for r in rows), unlisted=[r["key"] for r in rows if not r["listed_in_stages_v4"]],
                    words_crc_proven=sum(bool(r.get("words_crc_proven")) for r in rows),
                    clut_crc_proven=sum(bool(r["clut_crc_proven"]) for r in rows),
                    png_files_present=sum(1 for r in rows for f in r["files"].values() if f["exists"]),
                    keys_with_forced_centres=[r["key"] for r in rows if r["forced_centres_flag"]],
                    keys_with_stp_texels=sum(1 for r in rows if (r.get("native_class") or {}).get("stp", 0) > 0),
                    export_less_master_entries=len(masters), whole_cell_strict_run=0),
        gate_key_files=gate, planet_pairing=pairing, transmission_v2_text=tx, export_less_masters=masters,
        folders=folders, problems=problems,
        rows=[{k: v for k, v in r.items()} for r in rows],
        limits=["No PNG decode or PNG hashing: PNG checks are presence/size only against manifest-recorded sha256.",
                "Recorded lane gates are texel-centre checks; no whole-cell strict class result exists for any Stage 7 key.",
                "All keys predicted-static; drawn CLUTs (fades), hull identity, 704,256 residency and US-build text lines unknown "
                "(CR7-1..5)."],
        status="DATA ONLY; read-only on w7-stage7; no art edits")
    for w in words_cache.values():
        w.pop("b", None)
    res["page_words"] = words_cache
    out = OUT / f"selection-map-{stamp}.json"
    out.write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf-8")
    t = res["totals"]
    print("exported", t["exported_keys"], "unique", t["unique"], "by", t["by_folder"], "listed", t["listed"], "unlisted", t["unlisted"])
    print("words_crc", t["words_crc_proven"], "clut_crc", t["clut_crc_proven"], "png", t["png_files_present"],
          "forced", t["keys_with_forced_centres"], "stp_keys", t["keys_with_stp_texels"])
    print("gate", json.dumps(gate))
    print("pairing", json.dumps({k: v for k, v in pairing.items() if k not in ("gate_semantics",)})[:900])
    print("masters", json.dumps([(x["folder"], x.get("tex"), x.get("listed_keys")) for x in masters]))
    print("kanji", tx.get("dense_v1_fallback_count"), json.dumps(tx.get("dense_v1_fallback"))[:400])
    print("folders lane_ok", json.dumps({n: f["lane_ok"] for n, f in folders.items()}))
    print("problems", problems[:6])
    print("out", out, sha(out))


if __name__ == "__main__":
    main()
