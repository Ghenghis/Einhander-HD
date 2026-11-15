"""s23: collect Stage 2 cycling-phase CLUT words from a capture's source dumps into the input file of J6.
Light (reads 32-byte .clut.bin files and small JSON only; no pixel work).

  python -I phase_words_from_capture.py <out.json> <source_dir> [<source_dir> ...]

Wanted keys: every phase of the two cycling positions in the frozen stage2-prep-v1 palette_phase_inventory
(3DD37B6B @ 96,484 and AD934A7E @ 128,484), known and unknown. For each wanted key found as <KEY>.clut.bin in any given
directory (stock-first dump <run>/stage2-source/ or recorder native-source-<i>/ / native/):
  * 32 bytes and crc32(bytes) == PAL, else rejected (recorded with the reason);
  * the companion <KEY>.source.json clut_xy must equal the inventory position when present, else rejected;
  * known phases are compared with the frozen words (static export / recovered) as a control; a mismatch is reported.
The output maps KEY -> words hex for J6 (unknown phases only under "words", controls under "controls"), plus a
per-key provenance table and the list of phases still missing. Nothing is written except <out.json>.
"""
import hashlib
import json
import os
import sys
import zlib
from datetime import datetime, timezone

ROOT = "C:/github/Einhander"
PREP1 = ROOT + "/remaster-audit/comfy-authoring/w7-stage2/frozen/stage2-prep-v1/manifest.json"
PREP1_SHA = "9e4a8270e988791efdc8fb37573447b5c89389014dc30a562eb093da4e5c83a0"
PREP2 = ROOT + "/remaster-audit/comfy-authoring/w7-stage2/frozen/stage2-prep-v2/manifest.json"
POSITIONS = {"3DD37B6B @ 96,484": (96, 484), "AD934A7E @ 128,484": (128, 484)}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main(out, dirs):
    assert sha(PREP1) == PREP1_SHA
    inv = json.load(open(PREP1, encoding="utf-8"))["palette_phase_inventory"]
    known = {k: v["clut"]["words_hex"] for k, v in json.load(open(PREP2, encoding="utf-8"))["keys"].items()}
    wanted = {}
    for pos, xy in POSITIONS.items():
        e = inv[pos]
        for k in e["known_static"] + e["known_recovered"] + e["unknown"]:
            wanted[k] = dict(position=pos, clut_xy=list(xy), unknown=k in e["unknown"])
    found, rejected, controls, prov = {}, {}, {}, {}
    for d in dirs:
        for k, w in wanted.items():
            p = os.path.join(d, k + ".clut.bin")
            if not os.path.exists(p) or k in found:
                continue
            b = open(p, "rb").read()
            crc = "%08X" % (zlib.crc32(b) & 0xFFFFFFFF)
            reason = None
            if len(b) != 32:
                reason = f"length {len(b)} != 32"
            elif crc != k[9:]:
                reason = f"crc32 {crc} != PAL {k[9:]}"
            sj = os.path.join(d, k + ".source.json")
            meta = json.load(open(sj, encoding="utf-8")) if os.path.exists(sj) else None
            if reason is None and meta and meta.get("clut_xy") and list(meta["clut_xy"]) != w["clut_xy"]:
                reason = f"clut_xy {meta['clut_xy']} != inventory {w['clut_xy']}"
            if reason:
                rejected.setdefault(k, []).append(dict(path=p.replace("\\", "/"), reason=reason))
                continue
            prov[k] = dict(path=p.replace("\\", "/"), sha256=hashlib.sha256(b).hexdigest(), source_json=sj.replace("\\", "/") if meta else None,
                           frame=(meta or {}).get("frame"), cpu_vram_may_be_stale=(meta or {}).get("cpu_vram_may_be_stale"), **w)
            if w["unknown"]:
                found[k] = b.hex()
            else:
                controls[k] = dict(words_hex=b.hex(), equals_frozen=(known.get(k) == b.hex()) if k in known else None)
    missing = sorted(k for k, w in wanted.items() if w["unknown"] and k not in found)
    res = dict(owner="claude-einhander-s23", created_utc=datetime.now(timezone.utc).isoformat(), source_dirs=[d.replace("\\", "/") for d in dirs],
               prep_v1_manifest=PREP1_SHA, wanted=len(wanted), unknown_wanted=sum(w["unknown"] for w in wanted.values()),
               words=found, controls=controls, rejected=rejected, provenance=prov, unknown_still_missing=missing,
               note="Feed {words} to tools/j6_phase_export.py as the phase-words file. A phase is complete only with a "
                    "gate-A hold showing the sequence repeats (S2.md S2-2).")
    json.dump(res, open(out, "w", encoding="utf-8"), indent=1)
    print(json.dumps(dict(found=len(found), controls=len(controls), rejected=len(rejected), missing=len(missing), out=out, sha256=sha(out))))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
