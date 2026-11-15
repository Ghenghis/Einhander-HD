"""s23: full-stage Stage 2 / Stage 3 coverage matrix by family, r3 (light: JSON only, no pixels; r2 f130c11c... and r1
f8d85cf1... preserved, r2 never run). r3 = the two semantic corrections of msg_7eeb24a4c4270287 / msg_0cd2315bb40ccf8d /
msg_8a79eec95cc1ce97: (1) the four 442981F7 rows are labelled a POSSIBLE 65560E82 correspondence with equivalence
unverified, owned by capture / material mapping until source or live proof, with a separate documented `possible_alias`
field; their raw authored/source fields and every gap count stay unchanged; (2) Stage-1 candidate-ledger entries are
PROVENANCE only: integration counts only an imported or existing pack entry; candidate-only rows stay in "authored but
not privately integrated" with integration "unknown (stage1 candidate ledger only)"; admission "not established", live
and E2E "none". The whole output is an OWNERSHIP ATTRIBUTION CORRECTION (family labels), not resolved coverage or
visual gaps. Output must be a NEW folder inside s23/runs (exclusive, confined). Earlier r2 text: r2 applies the PINNED ownership records of 2026-11-14 as explicit family overrides, so the matrix
no longer shows false S23 gaps: member-1/1 Stage-1 carryover effects (25 rows) -> "effects (carried over from Stage 1)",
imported sky 65560E82 x2 -> "world/background", one-frame transient page hashes 442981F7 x4 -> "transient page hash
(covered by 65560E82)", 3955512F-8B7DD252 -> "player/pods/HUD globals (common 0/14, 0/11)". Every override is listed in
the output with its basis; refuses if a pinned record changed. Nothing else differs from r1.

  python -I fullstage_coverage.py <out_dir>

Key universe per stage (fullgame-prep/stage-review/<stage>/): live-observed keys (keys-live.json), pack-imported keys
(keys-imported.json) and listed predicted-static keys (keys-predicted-static.json). Family = the stage review's family
whose (member, VRAM page) basis contains the key's TEX member/page; else 'unassigned'.
Per key, each gate is reported as an observed state, never inferred:
  source  : complete_live_source | live_drawn (no complete source) | imported_pack | predicted_static
  authored: list of folders whose manifest lists the key (comfy-authoring/*/frozen/*, s23 proposals) or none
  cpu     : strict whole-cell result when s23 J1 / proposal manifests carry one, else 'not run'
  integ   : 'imported pack' for keys-imported, else 'none' (no private S2/S3 composition exists)
  live    : 'none' (no live S2/S3 review exists), e2e: 'none'
Gaps name the dependency owner: capture/live/integration -> codex-einhander; authoring/proof review of world/effects ->
claude-einhander-s23; enemies/boss -> w4-enemies lane owner (unassigned, reported); HUD/lettering -> shared UI;
player/pods globals -> support / shared skin owner. Output only in <out_dir>.
"""
import glob
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

RA = "C:/github/Einhander/remaster-audit"
SR = RA + "/fullgame-prep/stage-review"
S23 = RA + "/parallel-stages-20261114/s23"
OWNER = {"world/background": "claude-einhander-s23", "effects (stage-specific)": "claude-einhander-s23",
         "enemies / vehicles": "enemy lane (w4-enemies; owner to assign)", "boss": "enemy/boss lane (owner to assign)",
         "mid-boss": "enemy/boss lane (owner to assign)", "effects (carried over from Stage 1)": "shared effects (Stage 1 lane)",
         "HUD/lettering": "shared UI session", "player/pods/HUD globals (common 0/14, 0/11)": "support / shared skin owner",
         "unassigned (TEX not in static export)": "codex-einhander (capture) then claude-einhander-s23", "unassigned": "claude-einhander-s23 (triage)"}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def authored_index():
    idx = defaultdict(list)
    manifests = sorted(glob.glob(RA + "/comfy-authoring/*/frozen/*/manifest.json")) + sorted(glob.glob(S23 + "/proposals/*/manifest.json"))
    for mp in manifests:
        try:
            m = json.load(open(mp, encoding="utf-8"))
        except Exception:
            continue
        keys = m.get("keys")
        if isinstance(keys, dict):
            name = mp.replace("\\", "/").split("/")[-2]
            lane = mp.replace("\\", "/").split("/comfy-authoring/")[-1].split("/")[0] if "/comfy-authoring/" in mp.replace("\\", "/") else "s23-proposal"
            for k in keys:
                if len(k) == 17 and k[8] == "-":
                    idx[k].append(f"{lane}/{name}")
    # existing pack + every Stage-1 candidate ledger (a key already shipped or composed is NOT unauthored; avoids
    # duplicate asset builds - correction 2026-11-14 ~17:12Z after J9's queue overlapped 14 pack keys)
    import re
    cov = json.load(open(RA + "/overall-remaster-coverage.json", encoding="utf-8"))
    for x in cov.get("selected_file_provenance", []):
        k = x.get("key", "")[:17]
        if len(k) == 17:
            idx[k].append(f"pack/{x.get('origin', 'base')}")
    key_re = re.compile(r"^([0-9A-F]{8}-[0-9A-F]{8})\.png$")
    ledgers = sorted(glob.glob(RA + "/dev-center-evidence/stage1-completion-20261112/*/candidate.json"))
    for c in ledgers:
        try:
            d = json.load(open(c, encoding="utf-8"))
        except Exception:
            continue
        name = c.replace("\\", "/").split("/")[-2]
        for f in d.get("files", []):
            m = key_re.match(f.get("name", ""))
            if m and f"candidate/{name}" not in idx[m.group(1)]:
                idx[m.group(1)].append(f"candidate/{name}")
    return idx, len(manifests) + 1 + len(ledgers)


def family_lookup(fams):
    rules = []
    for f in fams:
        members = f.get("members") or []
        pages = f.get("vram_pages") or []
        rules.append((f["family"], set(members), set(pages)))
    def find(member, page_xy):
        pg = f"{page_xy[0]},{page_xy[1]}" if page_xy else None
        for name, mem, pages in rules:
            if member in mem and (not pages or pg in pages):
                return name
        for name, mem, pages in rules:
            if member in mem:
                return name
        return "unassigned"
    return find


OWNERSHIP = {S23 + "/runs/ownership-20261114T183239Z/s2-unassigned-gaps.json": "1420fd6e9dd40df2c2b4a572b2b6ab81f4ba681e841de203ec5f57da1124acc2",
             S23 + "/runs/ownership-20261114T184349Z/unassigned-family-owners.json": "528960faee3ef9eb68608ce008315658b8a3529f1583b52c25b0395c54893306"}
OWNER["transient page hash (possible 65560E82 correspondence; equivalence unverified)"] = "codex-einhander (capture / material mapping) until source or live proof"


def overrides():
    for p, h in OWNERSHIP.items():
        if sha(p) != h:
            raise SystemExit(f"pinned ownership record changed: {p}")
    gaps = json.load(open(list(OWNERSHIP)[0], encoding="utf-8"))
    fam = json.load(open(list(OWNERSHIP)[1], encoding="utf-8"))
    ov = {"stage2": {}, "stage3": {}}
    for k in gaps["classification"]:
        f = "transient page hash (possible 65560E82 correspondence; equivalence unverified)" if k.startswith("442981F7") else "player/pods/HUD globals (common 0/14, 0/11)"
        ov["stage2"][k] = dict(family=f, basis="s2-unassigned-gaps.json 1420fd6e: " + gaps["classification"][k][:160])
        if k.startswith("442981F7"):
            ov["stage2"][k]["possible_alias"] = dict(key="65560E82-" + k[9:], basis="same page (640,0) and CLUT, next-frame hash in draws-s2; metadata only: affected-word / UV equivalence and live replacement NOT verified")
    for sk, row in fam["rows"].items():
        st, k = sk.split("/", 1)
        f = "effects (carried over from Stage 1)" if row["owner"].startswith("shared effects") else "world/background"
        ov[st][k] = dict(family=f, basis="unassigned-family-owners.json 528960fa: " + row["owner"])
    return ov


def main(out):
    parent = os.path.realpath(os.path.dirname(os.path.abspath(out)))
    if os.path.normcase(parent) != os.path.normcase(os.path.realpath(S23 + "/runs")):
        raise SystemExit("output must be a NEW folder directly inside s23/runs")
    os.makedirs(out, exist_ok=False)
    OV = overrides()
    auth, nman = authored_index()
    strict = {}
    for l in open(S23 + "/runs/j1-20261114T134041Z/rows.jsonl", encoding="utf-8"):
        r = json.loads(l)
        strict.setdefault(r["key"], []).append(r["strict_pass_np"])
    for mp in glob.glob(S23 + "/proposals/*/manifest.json"):
        m = json.load(open(mp, encoding="utf-8"))
        for k, v in (m.get("keys") or {}).items():
            for f in (v.get("files") or {}).values():
                if "strict_pass" in f:
                    strict.setdefault(k, []).append(f["strict_pass"])
    res = dict(owner="claude-einhander-s23", tool="fullstage_coverage_r3.py",
               scope="OWNERSHIP ATTRIBUTION CORRECTION: family labels only; raw authored/source fields and gap counts unchanged; not resolved coverage or visual gaps; admission not established", created_utc=datetime.now(timezone.utc).isoformat(), authored_manifests_scanned=nman,
               inputs={}, ownership_pins=OWNERSHIP, stages={})
    for st in ("stage2", "stage3"):
        files = {n: f"{SR}/{st}/{n}" for n in ("families.json", "keys-live.json", "keys-imported.json", "keys-predicted-static.json")}
        res["inputs"][st] = {n: sha(p) for n, p in files.items() if os.path.exists(p)}
        fams = json.load(open(files["families.json"], encoding="utf-8"))["families"]
        find = family_lookup(fams)
        live = json.load(open(files["keys-live.json"], encoding="utf-8"))["keys"] if os.path.exists(files["keys-live.json"]) else {}
        imp = json.load(open(files["keys-imported.json"], encoding="utf-8"))["keys"]
        pred = json.load(open(files["keys-predicted-static.json"], encoding="utf-8"))["keys"]
        rows = {}
        for k, e in pred.items() if isinstance(pred, dict) else ((e["key"], e) for e in pred):
            rows[k] = dict(family=find(e.get("tex_member"), e.get("page_xy")), source="predicted_static",
                           confidence=e.get("confidence"), pal_candidates=e.get("pal_candidates_at_position"))
        v4 = RA + f"/fullgame-prep/static-extraction/stages-v4/{st}/keys.json"
        if os.path.exists(v4):          # the w7-stage3 lane authored from the stages-v4 export; include its listed keys too
            res["inputs"][st]["stages-v4 keys.json"] = sha(v4)
            for e in json.load(open(v4, encoding="utf-8")):
                k = e["key"]
                if k not in rows and not e.get("render_all_transparent"):
                    rows[k] = dict(family=find(e.get("tex_member"), e.get("page_xy")), source="predicted_static",
                                   confidence=e.get("confidence"), pal_candidates=e.get("pal_candidates_at_position"), export="stages-v4")
        for k, e in live.items():
            ts = e.get("tex_static") or {}
            fam = find(ts.get("member"), (e.get("page_xy") or [None])[0]) if ts else "unassigned (TEX not in static export)"
            if e.get("stage1_global_family"):
                fam = rows.get(k, {}).get("family", fam)
            rows[k] = dict(family=fam, source="complete_live_source" if e.get("source_complete") else "live_drawn", draws=e.get("draws"))
        for k, e in imp.items():
            r = rows.setdefault(k, dict(family=e.get("stage1_global_family") or "unassigned", source="imported_pack"))
            r["imported"] = True
        applied = []
        for k, o in OV.get(st, {}).items():
            if k in rows:
                rows[k]["family_r1"] = rows[k]["family"]
                rows[k]["family"] = o["family"]
                rows[k]["override"] = o["basis"]
                if "possible_alias" in o:
                    rows[k]["possible_alias"] = o["possible_alias"]
                applied.append(dict(key=k, family_r1=rows[k]["family_r1"], family=o["family"]))
        res.setdefault("overrides_applied", {})[st] = applied
        fam_stats = defaultdict(Counter)
        gaps = defaultdict(Counter)
        for k, r in rows.items():
            r["authored"] = auth.get(k, [])
            s = strict.get(k)
            r["cpu_strict"] = ("pass" if all(s) else "FAIL") if s else "not run"
            r["provenance"] = ("imported pack" if r.get("imported") else
                               "existing pack" if any(a.startswith("pack/") for a in r["authored"]) else
                               "stage1 candidate ledger" if any(a.startswith("candidate/") for a in r["authored"]) else "none")
            r["integration"] = (r["provenance"] if r["provenance"] in ("imported pack", "existing pack") else
                                "unknown (stage1 candidate ledger only; no Stage 2/3 composition evidence)" if r["provenance"] == "stage1 candidate ledger" else "none")
            r["admission"] = "not established"
            f = r["family"]
            c = fam_stats[f]
            c["keys"] += 1
            c["source:" + r["source"]] += 1
            c["authored"] += bool(r["authored"])
            c["cpu_strict_pass"] += r["cpu_strict"] == "pass"
            c["integrated_pack_or_import"] += r["integration"] in ("imported pack", "existing pack")
            c["candidate_ledger_provenance_only"] += r["provenance"] == "stage1 candidate ledger"
            if r["source"] in ("live_drawn", "complete_live_source") and not r["authored"]:
                gaps[f]["drawn but no authored HD"] += 1
            if r["source"] == "live_drawn":
                gaps[f]["drawn without complete source"] += 1
            if r["source"] == "predicted_static":
                gaps[f]["predicted only (needs live key/CLUT proof)"] += 1
            if r["authored"] and r["cpu_strict"] == "not run":
                gaps[f]["authored but no s23 strict check"] += 1
            if r["authored"] and r["integration"] not in ("imported pack", "existing pack"):
                gaps[f]["authored but not privately integrated"] += 1
        res["stages"][st] = dict(keys=len(rows),
                                 families={f: dict(c, owner=OWNER.get(f, "triage"), gaps=dict(gaps[f]), admission="not established", live_visual="none", stage_e2e="none")
                                           for f, c in sorted(fam_stats.items())},
                                 rows=rows)
    p = out + "/fullstage-coverage.json"
    json.dump(res, open(p, "w", encoding="utf-8"), indent=1)
    md = ["# Stage 2 / 3 full-stage coverage by family (claude-einhander-s23)", "",
          f"Generated {res['created_utc']}. JSON: fullstage-coverage.json. {res['scope']}. Observed states only; admission not established; live visual and stage E2E are 'none' for every family.", ""]
    for st, s in res["stages"].items():
        md += [f"## {st}: {s['keys']} keys (live + imported + listed predicted)", "",
               "| Family | Keys | Complete live src | Live drawn only | Imported | Predicted only | Authored | s23 strict pass | Pack/import integrated | Candidate-ledger provenance only | Owner | Main gaps |",
               "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
        for f, c in s["families"].items():
            g = "; ".join(f"{k} {v}" for k, v in sorted(c["gaps"].items(), key=lambda x: -x[1])[:3])
            md.append(f"| {f} | {c['keys']} | {c.get('source:complete_live_source', 0)} | {c.get('source:live_drawn', 0)} | {c.get('source:imported_pack', 0)} | "
                      f"{c.get('source:predicted_static', 0)} | {c['authored']} | {c['cpu_strict_pass']} | {c['integrated_pack_or_import']} | {c['candidate_ledger_provenance_only']} | {c['owner']} | {g} |")
        md.append("")
    open(out + "/FULLSTAGE-COVERAGE.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(json.dumps(dict(out=p, sha256=sha(p), md_sha256=sha(out + "/FULLSTAGE-COVERAGE.md"), manifests=nman,
                          keys={st: s["keys"] for st, s in res["stages"].items()})))


if __name__ == "__main__":
    main(sys.argv[1])
