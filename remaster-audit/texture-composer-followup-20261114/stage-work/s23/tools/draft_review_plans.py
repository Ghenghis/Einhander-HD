"""s23: draft composer plans for the S2/S3 REVIEW-ONLY install passes (S2-5 fly-past, S3-3 wall hold, S3 signage A/B).
Light (hashing + small binary files). Writes only under s23/plans/<stamp>/.

  python -I draft_review_plans.py

The plans follow remaster-audit/build_stage1_frozen_candidate.py ("parent={path,sha256}; entries=[{manifest, key, image,
native_source}]"). Every image/manifest is pinned by sha256; every entry carries a full-upload native_source whose words
are the CRC-proven static-export page and whose CLUT is a 32-byte file written here from the manifest's words_hex
(crc32 checked) so the composer can prove WORDS-CLUT == key. Each entry is validated by importing the composer and
calling its own verified_native_source (read only; the composer's main() is NOT run).
Left for codex-einhander (owner of composition, installs and live runs): "parent" and "cutout_rgb_fill" are null.
These keys are predicted-static: the plans are for review-only installs after or alongside the stock-first capture,
exactly as S2.md S2-5 / S3.md S3-3 describe; they are not admission.
"""
import hashlib
import json
import os
import sys
import zlib
from datetime import datetime, timezone

ROOT = "C:/github/Einhander"
RA = ROOT + "/remaster-audit"
S23 = RA + "/parallel-stages-20261114/s23"
sys.path.insert(0, RA)
import build_stage1_frozen_candidate as C  # noqa: E402  (read-only use of verified_native_source)

SETS = {
    "S2-5-train-cars-v4": (RA + "/comfy-authoring/w7-stage2/frozen/stage2-train-cars-v4", None),
    "S2-5-sky-ground-v3": (RA + "/comfy-authoring/w7-stage2/frozen/stage2-sky-ground-v3", None),
    "S3-3-walls-v1": (RA + "/comfy-authoring/w7-stage3/frozen/stage3-machinery-walls-v1", None),
    "S3-3-walls-material-v1": (RA + "/comfy-authoring/w7-stage3/frozen/stage3-machinery-walls-material-v1", None),
    "S3-signage-v1": (RA + "/comfy-authoring/w7-stage3/frozen/stage3-signage-props-v1", None),
    "S3-signage-p1a": (S23 + "/proposals/s3-dither-hybrid-a-20261114T143143Z", RA + "/comfy-authoring/w7-stage3/frozen/stage3-signage-props-v1"),
    "S3-signage-p1b": (S23 + "/proposals/s3-dither-hybrid-b-20261114T143143Z", RA + "/comfy-authoring/w7-stage3/frozen/stage3-signage-props-v1"),
}
PLANS = {  # one plan per review pass; S2-5 installs both S2 sets together (S2.md)
    "plan-S2-5-flypast.json": ["S2-5-train-cars-v4", "S2-5-sky-ground-v3"],
    "plan-S3-3-walls-v1.json": ["S3-3-walls-v1"],
    "plan-S3-3-walls-material-v1.json": ["S3-3-walls-material-v1"],
    "plan-S3-signage-v1.json": ["S3-signage-v1"],
    "plan-S3-signage-p1a.json": ["S3-signage-p1a"],
    "plan-S3-signage-p1b.json": ["S3-signage-p1b"],
}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = f"{S23}/plans/{stamp}"
    os.makedirs(out + "/native-cluts")
    entries_by_set, report = {}, {}
    for name, (folder, base) in SETS.items():
        mpath = folder + "/manifest.json"
        m = json.load(open(mpath, encoding="utf-8"))
        bm = json.load(open(base + "/manifest.json", encoding="utf-8")) if base else m
        pages = {}                                   # page words from any frozen manifest of the same stage (J1 rule)
        stage_root = os.path.dirname(base or folder) if "comfy-authoring" in (base or folder) else None
        for nm in sorted(os.listdir(stage_root)):
            mp2 = f"{stage_root}/{nm}/manifest.json"
            if os.path.exists(mp2):
                for t, pg2 in (json.load(open(mp2, encoding="utf-8")).get("pages") or {}).items():
                    if isinstance(pg2, dict) and isinstance(pg2.get("words"), dict) and t not in pages:
                        pages[t] = pg2
        rows = []
        for key, ke in sorted(m["keys"].items()):
            tex = key[:8]
            src_key = bm["keys"][key]
            cb = bytes.fromhex(src_key["clut"]["words_hex"])
            assert len(cb) == 32 and "%08X" % (zlib.crc32(cb) & 0xFFFFFFFF) == key[9:], key
            cp = f"{out}/native-cluts/{key}.clut.bin"
            if not os.path.exists(cp):
                open(cp, "wb").write(cb)
            pg = pages[tex]
            wp = pg["words"]["path"]
            img = folder + "/" + ke["files"]["page2048"]["path"]
            ns = dict(source_words=dict(path=wp, sha256=sha(wp)), source_clut=dict(path=cp.replace("\\", "/"), sha256=sha(cp)),
                      source_shape_words=[pg["vram_rect_words"][2], pg["vram_rect_words"][3]], depth=0)
            proof = C.verified_native_source(ns, key)          # composer's own check (raises on mismatch)
            row = dict(manifest=dict(path=mpath, sha256=sha(mpath)), key=key, image=dict(path=img, sha256=sha(img)), native_source=ns)
            rows.append(row)
        entries_by_set[name] = rows
        report[name] = dict(entries=len(rows), manifest_sha256=sha(mpath), native_source_verified=len(rows))
    written = {}
    for pname, sets in PLANS.items():
        plan = dict(parent=None, cutout_rgb_fill=None,
                    purpose="REVIEW-ONLY install pass (S2.md S2-5 / S3.md S3-3, S3 signage A/B); predicted-static keys; not admission",
                    drafted_by="claude-einhander-s23", drafted_utc=datetime.now(timezone.utc).isoformat(),
                    todo_for_codex=["set parent={path,sha256} of the candidate to extend", "set cutout_rgb_fill policy (opt-in)",
                                    "run only after or alongside the stock-first capture; record live receipts"],
                    entries=[e for s in sets for e in entries_by_set[s]])
        p = f"{out}/{pname}"
        json.dump(plan, open(p, "w", encoding="utf-8"), indent=1)
        written[pname] = dict(entries=len(plan["entries"]), sha256=sha(p))
    summary = dict(out=out, sets=report, plans=written, composer=dict(path=RA + "/build_stage1_frozen_candidate.py", sha256=sha(RA + "/build_stage1_frozen_candidate.py")))
    json.dump(summary, open(out + "/SUMMARY.json", "w", encoding="utf-8"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
