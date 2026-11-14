#!/usr/bin/env python3
"""Confirm static predictions against a live capture, and gate pack imports (read-only on inputs).

Modes
  confirm:  python -I validate_predicted.py confirm --stage-dir stages/stage2 --live <dir> [--live <dir>...]
                [--draws <capture.jsonl>...] --out <report.json>
            A live source counts only when it is complete: <KEY>.words.bin + .source.json (+ .clut.bin for
            4/8bpp), known_words == total_words, every valid.bin byte non-zero, CRC32(words) == TEX and
            CRC32(clut) == PAL (the acquisition gate-K rule). For every complete live key:
              key-confirmed      KEY was predicted and the live words equal textures/<TEX>.words.bin
              tex-confirmed      TEX predicted and words identical, but this CLUT was not predicted
                                 (runtime CLUT variant: render it from the index master with the live CLUT)
              MISMATCH           TEX predicted but live words differ (prediction wrong: never import)
              unpredicted        TEX not predicted (author from the live source as today)
            Predicted keys/textures never seen live are listed as unconfirmed.
  gate:     python -I validate_predicted.py gate --stage-dir stages/stageN --live <dir>... --keys <file>
                [--pack-dir <dir>] --out <report.json>
            <file> lists the keys of HD art built on a static source (one KEY per line or a JSON list);
            --pack-dir adds every <KEY>.png / <KEY>.*.png in that folder whose TEX is a static prediction.
            Exit status 1 if any such key lacks a complete, byte-identical live source: the rule is that a
            static-sourced HD texture is imported only after live capture confirms its exact key.
  selftest: python -I validate_predicted.py selftest   (synthetic stage folder + live dumps, no disc)
"""
import glob
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import zlib

KEYRX = re.compile(r"([0-9A-F]{8})-([0-9A-F]{8})")
QUIET = "C:/github/Einhander/remaster-audit/comfy-authoring/CPU-QUIET"


def cpu_yield():
    import time
    while os.path.exists(QUIET):
        time.sleep(30)


def crc(b):
    return "%08X" % (zlib.crc32(b) & 0xFFFFFFFF)


def load_stage(d, with_common=True):
    """Textures/keys of a stage folder, plus the sibling common/ folder (front end, HUD, fonts and the
    engine are resident in every stage). Each texture row gets `_dir` for its words file."""
    texs, keys = {}, {}
    dirs = [d]
    root = os.path.dirname(os.path.abspath(d))
    common = os.path.join(root, "common")
    if not os.path.isdir(common) and os.path.exists(os.path.join(root, "FREEZE.json")):
        # partial export (e.g. stages-v3): common stays current in the export its FREEZE.json names
        cur = json.load(open(os.path.join(root, "FREEZE.json"), encoding="utf-8")).get("current_scopes", {})
        if "common" in cur:
            common = os.path.join(os.path.dirname(root), cur["common"]["export"], "common")
    if with_common and os.path.isdir(common) and os.path.abspath(common) != os.path.abspath(d):
        dirs.append(common)
    for dd in reversed(dirs):  # the stage itself wins
        for r in json.load(open(os.path.join(dd, "textures.json"), encoding="utf-8")):
            r["_dir"] = dd
            texs[r["tex"]] = r
        for r in json.load(open(os.path.join(dd, "keys.json"), encoding="utf-8")):
            keys[r["key"]] = r
    return texs, keys


def live_sources(dirs):
    out, rejected = {}, {}
    for d in dirs:
        cpu_yield()
        for wp in glob.glob(os.path.join(d, "**", "*.words.bin"), recursive=True):
            key = os.path.basename(wp)[:-10]
            m = KEYRX.fullmatch(key)
            if not m or key in out:
                continue
            base = wp[:-10]
            why = []
            meta = {}
            if os.path.exists(base + ".source.json"):
                meta = json.load(open(base + ".source.json", encoding="utf-8"))
            else:
                why.append("no source.json")
            if meta.get("predicted") or meta.get("raw_origin") == "static_disc_prediction":
                why.append("is a static prediction, not a capture")
            words = open(wp, "rb").read()
            if crc(words) != m.group(1):
                why.append("CRC32(words) != TEX")
            if meta and meta.get("known_words") != meta.get("total_words"):
                why.append("known_words != total_words")
            if os.path.exists(base + ".valid.bin"):
                if not all(open(base + ".valid.bin", "rb").read()):
                    why.append("valid.bin has unknown words")
            else:
                why.append("no valid.bin")
            clut = open(base + ".clut.bin", "rb").read() if os.path.exists(base + ".clut.bin") else None
            if m.group(2) != "00000000":
                if clut is None:
                    why.append("no clut.bin")
                elif crc(clut) != m.group(2):
                    why.append("CRC32(clut) != PAL")
            if why:
                rejected[key] = dict(dir=d, reasons=why)
            else:
                out[key] = dict(words=words, clut=clut, meta=meta, path=wp)
    return out, rejected


def drawn_keys(paths):
    keys = set()
    rx = re.compile(r'"key":"([0-9A-F]{8}-[0-9A-F]{8})"')
    for p in paths:
        cpu_yield()
        for line in open(p, encoding="utf-8"):
            if "source_draw_query_matched" in line:
                m = rx.search(line)
                if m:
                    keys.add(m.group(1))
    return keys


def confirm(stage_dir, live_dirs, draws=()):
    texs, keys = load_stage(stage_dir)
    live, rejected = live_sources(live_dirs)
    tex_words = {}
    res = dict(key_confirmed=[], tex_confirmed=[], mismatch=[], unpredicted=[])
    for key, s in sorted(live.items()):
        tex = key.split("-")[0]
        if tex in texs:
            if tex not in tex_words:
                p = os.path.join(texs[tex].get("_dir", stage_dir), "textures", tex + ".words.bin")
                tex_words[tex] = open(p, "rb").read() if os.path.exists(p) else None
            same = tex_words[tex] == s["words"]
            if not same:
                res["mismatch"].append(dict(key=key, live=s["path"], predicted=texs[tex]["sources"][0]))
            elif key in keys:
                res["key_confirmed"].append(dict(key=key, predicted_confidence=keys[key]["confidence"],
                                                 kind=keys[key]["kind"], live=s["path"]))
            else:
                res["tex_confirmed"].append(dict(key=key, tex_confidence=texs[tex]["confidence"],
                                                 kind=texs[tex]["kinds"], live=s["path"],
                                                 note="new CLUT for a confirmed texture"))
        else:
            res["unpredicted"].append(dict(key=key, live=s["path"]))
    seen_tex = set(k.split("-")[0] for k in live)
    drawn = drawn_keys(draws) if draws else set()
    res["summary"] = dict(
        live_complete=len(live), live_rejected=len(rejected),
        key_confirmed=len(res["key_confirmed"]), tex_confirmed=len(res["tex_confirmed"]),
        mismatch=len(res["mismatch"]), unpredicted=len(res["unpredicted"]),
        predicted_textures=len(texs), predicted_textures_seen_live=len(seen_tex & set(texs)),
        predicted_keys=len(keys), predicted_keys_seen_live=len(set(live) & set(keys)),
        drawn_keys=len(drawn), drawn_keys_predicted=len(drawn & set(keys)),
        drawn_keys_tex_predicted=sum(1 for k in drawn if k.split("-")[0] in texs))
    res["rejected_live"] = rejected
    res["confirmed_import_allowlist"] = sorted([r["key"] for r in res["key_confirmed"]] +
                                               [r["key"] for r in res["tex_confirmed"]])
    return res


def gate(stage_dir, live_dirs, keys_file=None, pack_dir=None):
    texs, _ = load_stage(stage_dir)
    want = set()
    if keys_file:
        txt = open(keys_file, encoding="utf-8").read()
        try:
            v = json.loads(txt)
            want |= set(v if isinstance(v, list) else v.keys())
        except ValueError:
            want |= set("%s-%s" % t for t in KEYRX.findall(txt))
    if pack_dir:
        for p in glob.glob(os.path.join(pack_dir, "**", "*.png"), recursive=True):
            m = KEYRX.search(os.path.basename(p))
            if m and m.group(1) in texs:
                want.add("%s-%s" % m.groups())
    c = confirm(stage_dir, live_dirs)
    ok = set(c["confirmed_import_allowlist"])
    blocked = sorted(k for k in want if k not in ok)
    mism = set(r["key"] for r in c["mismatch"])
    return dict(pass_=not blocked, checked=len(want), allowed=sorted(want & ok),
                blocked=[dict(key=k, reason=("live words differ from the static source" if k in mism else
                                             "no complete live source for this exact key")) for k in blocked],
                rule="static-sourced HD art is imported only after live capture confirms its exact key")


def selftest():
    tmp = tempfile.mkdtemp(prefix="ein-static-selftest-")
    try:
        st = os.path.join(tmp, "stage")
        os.makedirs(os.path.join(st, "textures"))
        words = bytes(range(256)) * 4
        tex = crc(words)
        clut = struct.pack("<16H", *range(0x8000, 0x8010))
        pal = crc(clut)
        clut2 = struct.pack("<16H", *range(0x8100, 0x8110))
        pal2 = crc(clut2)
        open(os.path.join(st, "textures", tex + ".words.bin"), "wb").write(words)
        json.dump([dict(tex=tex, kinds=["strip"], confidence="exact-static", sources=[dict(kind="strip")])],
                  open(os.path.join(st, "textures.json"), "w"))
        json.dump([dict(key=tex + "-" + pal, kind="strip", confidence="likely")], open(os.path.join(st, "keys.json"), "w"))
        live = os.path.join(tmp, "live")
        os.makedirs(live)

        def dump(key, w, c, valid=True, predicted=False):
            b = os.path.join(live, key)
            open(b + ".words.bin", "wb").write(w)
            open(b + ".clut.bin", "wb").write(c)
            open(b + ".valid.bin", "wb").write(b"\x01" * (len(w) // 2) if valid else b"\x00" * (len(w) // 2))
            json.dump(dict(key=key, known_words=len(w) // 2, total_words=len(w) // 2, predicted=predicted),
                      open(b + ".source.json", "w"))
        dump(tex + "-" + pal, words, clut)                       # key-confirmed
        dump(tex + "-" + pal2, words, clut2)                     # tex-confirmed (new CLUT)
        bad = bytearray(words)
        bad[0] ^= 1
        dump(crc(bytes(bad)) + "-" + pal, bytes(bad), clut)      # unpredicted
        dump("DEADBEEF-" + pal, words, clut)                     # rejected: CRC(words) != TEX
        c = confirm(st, [live])
        s = c["summary"]
        assert s["key_confirmed"] == 1 and s["tex_confirmed"] == 1 and s["unpredicted"] == 1, s
        assert s["mismatch"] == 0 and s["live_rejected"] == 1, s
        kf = os.path.join(tmp, "keys.json")
        json.dump([tex + "-" + pal, tex + "-0BADF00D"], open(kf, "w"))
        g = gate(st, [live], keys_file=kf)
        assert not g["pass_"] and g["allowed"] == [tex + "-" + pal] and len(g["blocked"]) == 1, g
        # a static prediction placed in a live folder must never count as a capture
        shutil.rmtree(live)
        os.makedirs(live)
        dump(tex + "-" + pal, words, clut, predicted=True)
        g2 = gate(st, [live], keys_file=kf)
        assert not g2["pass_"] and not g2["allowed"], g2
        return dict(passed=True, cases=7)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 2

    def opt(name, many=False):
        vals = [a[i + 1] for i, x in enumerate(a) if x == name and i + 1 < len(a)]
        return vals if many else (vals[0] if vals else None)
    mode = a[0]
    if mode == "selftest":
        r = selftest()
        print(json.dumps(r))
        return 0
    stage_dir = opt("--stage-dir")
    lives = opt("--live", True)
    out = opt("--out")
    if mode == "confirm":
        r = confirm(stage_dir, lives, opt("--draws", True))
        code = 1 if r["summary"]["mismatch"] else 0
        print(json.dumps(r["summary"], indent=1))
    elif mode == "gate":
        r = gate(stage_dir, lives, opt("--keys"), opt("--pack-dir"))
        code = 0 if r["pass_"] else 1
        print(json.dumps(dict(pass_=r["pass_"], checked=r["checked"], allowed=len(r["allowed"]),
                              blocked=len(r["blocked"])), indent=1))
    else:
        print(__doc__)
        return 2
    if out:
        json.dump(r, open(out, "w", encoding="utf-8"), indent=1, default=str)
    return code


if __name__ == "__main__":
    sys.exit(main())
