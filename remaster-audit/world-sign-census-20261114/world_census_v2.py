#!/usr/bin/env python3
"""Stage 1 HD world-layer coverage census v2 (claude-einhander). Read-only, CPU-light, below normal. No GPU, no game.

Joins, for every key of the current private candidate pack (frozen-w3-lit-v1):
  * TREATMENT, from the candidate provenance chain:
      authored            frozen lane set integrated in this pack (lane/set from the manifest path)
      legacy-neural       inherited unchanged; stage1-v1 base 'UltraSharp ...' method, or the REMASTER_STAGING
                          'world source-preserving addition' (local UltraSharp RGB, native classes)
      legacy-nearest      inherited unchanged; stage1-v1 base 'nearest 8x/16x' method (no new detail by construction)
      legacy-ui           inherited unchanged HUD / menu / typography / blueprint / results / diagram compositions
      legacy-other        anything else (reported by origin)
  * NOT-INTEGRATED AUTHORED SETS: every comfy-authoring/<lane>/frozen/<set>/manifest.json that names the key but is not the
    set integrated in this pack (later W4/W5/W6 work, superseded versions). Existence only; no quality claim.
  * LAYER (heuristic, labelled): from the lane/set name of the key's own authored set, else of any frozen set naming it, else
    inherited from another key on the same texture page ('page-inferred'), else from a legacy UI origin, else 'unknown'.
  * DRAW EVIDENCE from four retained ein-research-v1 logs (sampled_activation_forward, 60-frame repeat sampling, so these are
    samples, not all draws): queried, HD submitted, source kinds, 90th-percentile native bbox height (far <24 / mid 24..80 /
    near >80 px; a size proxy, not depth), frame span.
  * DRAWN WITHOUT A PACK ENTRY: keys queried in the logs that the current pack does not contain (native fallback).
Writes census-v2.json (rows + summaries) next to this script."""
import collections
import ctypes
import json
import re
from pathlib import Path

ROOT = Path("C:/github/Einhander")
E = ROOT / "remaster-audit/dev-center-evidence/stage1-completion-20261112"
CUR = E / "frozen-w3-lit-v1/candidate.json"
BASE = ROOT / "windows-x64/hd-textures/stage1-v1/manifest.json"
CA = ROOT / "remaster-audit/comfy-authoring"
LOGS = {"w3-emissive-on-v1": E / "w3-emissive-on-v1/hd-on_rewind-off/native-world-flypast/capture.jsonl",
        "w3-emissive-off-v1": E / "w3-emissive-off-v1/hd-on_rewind-off/native-world-flypast/capture.jsonl",
        "world-flypast-v1": E / "world-flypast-v1/hd-on_rewind-off/native-world-flypast/capture.jsonl",
        "actors-flypast-v4": E / "actors-flypast-v4/hd-on_rewind-off/native-world-flypast/capture.jsonl"}
W3 = CA / "w3-signs/INDEX.json"
HERE = Path(__file__).resolve().parent
KEY = re.compile(r"([0-9A-F]{8}-[0-9A-F]{8})")

LANE_LAYER = {"t1-sky": "sky-background", "t2-facades": "buildings-facades", "facade-pilot-20261112": "buildings-facades",
              "facade-pilot-v2-20261112": "buildings-facades", "facade-v3-architecture": "buildings-facades",
              "green-industrial": "buildings-facades", "t3-green-lights": "buildings-lights", "w3-emissive": "buildings-lights",
              "w3-canyon": "terrain-canyon", "w4-world": "world-props", "t4-signs": "signs", "w3-signs": "signs", "signs": "signs",
              "t6-player": "player", "w3-astraea": "player", "w4-player": "player", "t7-enemies": "enemies-bosses",
              "w3-mk3": "enemies-bosses", "w4-enemies": "enemies-bosses", "w6-drache": "enemies-bosses", "w2-effects": "effects",
              "w2-hud": "hud", "w3-hud": "hud", "w6-hud-fades": "hud", "t9-title-menus": "menus", "w4-menus": "menus"}
NAME_LAYER = [(re.compile(r"hud|lives|counter-digits|fades", re.I), "hud"),
              (re.compile(r"font|menu|spec-text|weapon-names|prompt-sheet|ranking|fighter-select", re.I), "menus"),
              (re.compile(r"board|sign|neon|rise|73BF9877|E360C964", re.I), "signs"),
              (re.compile(r"puff|fx|explos|smoke", re.I), "effects"),
              (re.compile(r"mk3|greif|drache|enemy", re.I), "enemies-bosses"),
              (re.compile(r"pod|astraea|player", re.I), "player"),
              (re.compile(r"sky|cloud", re.I), "sky-background"),
              (re.compile(r"facade|window", re.I), "buildings-facades"),
              (re.compile(r"canyon|deck|glow-bar|fd81c3c7|upload-strips|atlas", re.I), "world-other")]
UI_ORIGINS = ("HUD", "fresh typography", "fighter blueprint", "results art", "exact results region", "diagram", "extra menu")


def below():
    try:
        k = ctypes.windll.kernel32
        k.GetCurrentProcess.restype = ctypes.c_void_p
        k.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)
    except Exception:  # noqa: BLE001
        pass


def lane_of(path):
    p = Path(path).parts
    if "comfy-authoring" in p:
        i = p.index("comfy-authoring")
        return p[i + 1], (p[i + 3] if len(p) > i + 3 and p[i + 2] == "frozen" else p[i + 2] if len(p) > i + 2 else None)
    if "claude-backlog" in p:
        return "claude-backlog", p[-2]
    return "other", Path(path).parent.name


MIXED_LANES = {"w2-polish", "w4-world", "w4-signs-hud", "w5-cleanup", "w6-native-gaps", "w6-livepack-classfix", "claude-backlog", "other"}


def layer_for(lane, sset):
    """Single-purpose lanes map directly; mixed lanes are classified by set-name keywords."""
    if lane in LANE_LAYER and lane not in MIXED_LANES:
        return LANE_LAYER[lane]
    for rx, lay in NAME_LAYER:
        if sset and rx.search(sset):
            return lay
    return LANE_LAYER.get(lane)


def resolve_origins(cur):
    need = {f["name"] for f in cur["files"] if f.get("origin") == "unchanged immutable parent"}
    found = {}
    nxt = cur.get("parent_candidate") or cur.get("parent")
    p = Path(nxt["path"])
    depth = 0
    while need and p and p.exists() and depth < 40:
        c = json.loads(p.read_text(encoding="utf-8"))
        depth += 1
        for f in c.get("files", []):
            n = f["name"]
            if n in need and f.get("origin") and f["origin"] != "unchanged immutable parent":
                man = f["input"]["manifest"]["path"] if isinstance(f.get("input"), dict) and f["input"].get("manifest") else None
                found[n] = dict(origin=f["origin"], at=p.parent.name, lane=lane_of(man) if man else None,
                                method=f.get("processing_method"), sha256=f.get("sha256"))
                need.discard(n)
        nxt = c.get("parent_candidate") or c.get("parent")
        p = Path(nxt["path"]) if isinstance(nxt, dict) and str(nxt.get("path", "")).endswith(".json") else None
    for n in need:
        found[n] = dict(origin="unresolved", at=None, lane=None, method=None, sha256=None)
    return found


SKIP_SUBTREES = {"sources", "ref_sources", "inputs", "input", "parent", "base", "base_v13", "supersedes", "built_like",
                 "reference", "references", "superseded", "parents", "source", "stock_png", "clut"}
KEY_FIELDS = {"key", "register_key", "exact_key", "ref_key", "native_source_key", "exact_region_key"}
DELIVERY_DIR = re.compile(r"^(runtime|pack|export|out|delivery|page\d+)", re.I)


def _walk_keys(node, acc, skip=False):
    if isinstance(node, dict):
        for k, v in node.items():
            if skip or k in SKIP_SUBTREES:
                continue
            if isinstance(k, str) and KEY.fullmatch(k):
                acc.add(k)
            if k in KEY_FIELDS and isinstance(v, str) and KEY.fullmatch(v):
                acc.add(v)
            if isinstance(k, str) and k.lower().endswith(".png"):
                mm = KEY.search(Path(k).name)
                if mm:
                    acc.add(mm.group(1))
            _walk_keys(v, acc)
    elif isinstance(node, list):
        for v in node:
            _walk_keys(v, acc)
    elif isinstance(node, str) and node.lower().endswith(".png"):
        name = Path(node.replace("\\", "/")).name
        mm = KEY.fullmatch(name[:-4]) if len(name) == 21 else None
        if mm and DELIVERY_DIR.match(Path(node.replace("\\", "/")).parent.name or "x"):
            acc.add(mm.group(0))


def frozen_sets():
    """Keys a frozen set can deliver: PNG files named KEY.png in the set folder or its runtime*/pack*/export* subfolders
    (primary), plus key-valued manifest fields outside source/parent subtrees (secondary)."""
    sets = []
    for man in sorted(CA.glob("*/frozen/*/manifest.json")):
        lane, sset, sdir = man.parts[-4], man.parts[-2], man.parent
        file_keys = set()
        for d in [sdir] + [p for p in sdir.iterdir() if p.is_dir() and DELIVERY_DIR.match(p.name)]:
            for p in d.glob("*.png"):
                if KEY.fullmatch(p.stem):
                    file_keys.add(p.stem)
        try:
            m = json.loads(man.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            m = {}
        field_keys = set()
        _walk_keys(m, field_keys)
        keys = file_keys or field_keys
        sets.append(dict(lane=lane, set=sset, keys=sorted(keys), key_basis="files" if file_keys else ("manifest fields" if field_keys else None),
                         status=m.get("status"), frozen_utc=m.get("frozen_utc") or m.get("created_utc") or m.get("created_at_utc"),
                         path=str(man)))
    return sets


def draw_stats():
    st = collections.defaultdict(lambda: dict(queried=0, submitted=0, frames=set(), heights=[], kinds=set(), logs=set(), sizes=set()))
    for name, log in LOGS.items():
        if not log.exists():
            continue
        with open(log, encoding="utf-8") as f:
            for line in f:
                q = '"source_draw_query_matched"' in line
                s = '"replacement_gl_draw_submitted"' in line
                if not (q or s):
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                d = st[r["key"]]
                d["queried" if q else "submitted"] += 1
                d["frames"].add(r["frame"])
                ys = [v[1] % 240 for v in r["xy"]]
                d["heights"].append(max(ys) - min(ys))
                d["kinds"].add(str(r.get("source_kind")))
                d["logs"].add(name)
                if s:
                    d["sizes"].add(tuple(r.get("replacement_size") or ()))
    out = {}
    for k, d in st.items():
        h = sorted(d["heights"])
        p90 = h[min(len(h) - 1, int(0.9 * (len(h) - 1)))] if h else 0
        out[k] = dict(queried=d["queried"], submitted=d["submitted"], frame_span=[min(d["frames"]), max(d["frames"])],
                      p90_height_px=p90, size_proxy="far" if p90 < 24 else ("mid" if p90 <= 80 else "near"),
                      kinds=sorted(d["kinds"]), logs=sorted(d["logs"]), submitted_sizes=sorted(map(list, d["sizes"])))
    return out


def main():
    below()
    cur = json.loads(CUR.read_text(encoding="utf-8"))
    origins = resolve_origins(cur)
    base = {f["key"]: f for f in json.loads(BASE.read_text(encoding="utf-8"))["files"]}
    sets = frozen_sets()
    sets_by_key = collections.defaultdict(list)
    for s in sets:
        for k in s["keys"]:
            sets_by_key[k].append(s)
    draws = draw_stats()
    w3 = json.loads(W3.read_text(encoding="utf-8"))

    rows = {}
    for f in cur["files"]:
        name, key, o = f["name"], f["name"][:-4], f.get("origin")
        if o == "frozen artwork candidate" and isinstance(f.get("input"), dict) and f["input"].get("manifest"):
            lane, sset = lane_of(f["input"]["manifest"]["path"])
            tr = dict(treatment="authored", lane=lane, set=sset)
        elif o == "unchanged immutable parent":
            r = origins[name]
            if r.get("lane"):
                tr = dict(treatment="authored", lane=r["lane"][0], set=r["lane"][1], via=r["at"])
            elif r["origin"] == "base":
                b = base.get(key)
                meth = b["method"] if b else None
                same = bool(b) and b.get("sha256") == f.get("sha256")
                tr = dict(treatment="legacy-neural" if meth and "UltraSharp" in meth else "legacy-nearest" if meth and meth.startswith("nearest") else "legacy-other",
                          origin="stage1-v1 base", method=meth, base_sha_matches=same)
            elif r["origin"] == "world source-preserving addition":
                meth = r.get("method")
                tr = dict(treatment="legacy-neural" if meth and "UltraSharp" in meth else "legacy-nearest" if meth and "native 8x" in meth else "legacy-other",
                          origin=r["origin"], method=meth)
            elif r["origin"].startswith(UI_ORIGINS):
                tr = dict(treatment="legacy-ui", origin=r["origin"])
            else:
                tr = dict(treatment="legacy-other", origin=r["origin"], first_at=r["at"])
        else:
            tr = dict(treatment="legacy-other", origin=o)
        own = (tr.get("lane"), tr.get("set"))
        own_t = next((s["frozen_utc"] for s in sets_by_key.get(key, []) if (s["lane"], s["set"]) == own), None)
        others = [dict(lane=s["lane"], set=s["set"], status=s["status"], frozen_utc=s["frozen_utc"], basis=s["key_basis"],
                       relation=("newer" if own_t and s["frozen_utc"] and s["frozen_utc"] > own_t else
                                 "older" if own_t and s["frozen_utc"] else "unordered"))
                  for s in sets_by_key.get(key, []) if (s["lane"], s["set"]) != own]
        rows[key] = dict(key=key, page=key[:8], dims=f.get("dimensions"), **tr,
                         not_integrated_sets=[o for o in others if o["basis"] == "files"],
                         mentioned_by_manifests=[o for o in others if o["basis"] != "files"],
                         live_verified=f.get("live_verified"), draws=draws.get(key))

    # layer assignment
    for r in rows.values():
        lay, how = None, None
        if r["treatment"] == "authored":
            lay, how = layer_for(r["lane"], r["set"]), "own set"
        for group, label in (("not_integrated_sets", "frozen set delivering key"), ("mentioned_by_manifests", "manifest naming key")):
            if not lay and r[group]:
                s = r[group][-1]
                lay, how = layer_for(s["lane"], s["set"]), label
        if not lay and r["treatment"] == "legacy-ui":
            lay, how = ("hud" if r["origin"] == "HUD" else "menus"), "legacy UI origin"
        r["layer"], r["layer_basis"] = lay, how
    page_layers = collections.defaultdict(collections.Counter)
    for r in rows.values():
        if r["layer"]:
            page_layers[r["page"]][r["layer"]] += 1
    for r in rows.values():
        if not r["layer"]:
            c = page_layers.get(r["page"])
            if c:
                r["layer"], r["layer_basis"] = c.most_common(1)[0][0], "page-inferred"
            else:
                r["layer"], r["layer_basis"] = "unknown", None

    drawn_not_in_pack = {k: v for k, v in draws.items() if k not in rows}
    # sign join: W3 boards -> keys
    sign_rows = []
    for b in w3.get("boards", []):
        for ph in b.get("phase_keys", []) or []:
            k = ph.get("key")
            r = rows.get(k)
            sign_rows.append(dict(board=b.get("board"), content=b.get("content"), key=k, role=ph.get("role"),
                                  in_pack=bool(r), treatment=r["treatment"] if r else None, set=r.get("set") if r else None,
                                  drawn=bool(r and r["draws"]), size_proxy=r["draws"]["size_proxy"] if r and r["draws"] else None))

    def tab(pred=lambda r: True):
        t = collections.defaultdict(collections.Counter)
        for r in rows.values():
            if pred(r):
                t[r["layer"]][r["treatment"]] += 1
        return {k: dict(v) for k, v in sorted(t.items())}

    drawn = [r for r in rows.values() if r["draws"]]
    summary = dict(
        pack_keys=len(rows),
        treatment=dict(collections.Counter(r["treatment"] for r in rows.values())),
        layer_by_treatment_all=tab(),
        layer_by_treatment_drawn=tab(lambda r: bool(r["draws"])),
        drawn_in_pack=len(drawn),
        drawn_in_pack_hd_submitted=sum(1 for r in drawn if r["draws"]["submitted"]),
        drawn_by_treatment_and_size={f"{t}/{s}": n for (t, s), n in sorted(collections.Counter((r["treatment"], r["draws"]["size_proxy"]) for r in drawn).items())},
        legacy_with_not_integrated_deliverable_set=sum(1 for r in rows.values() if r["treatment"].startswith("legacy") and r["not_integrated_sets"]),
        legacy_with_not_integrated_deliverable_set_by_layer=dict(collections.Counter(r["layer"] for r in rows.values() if r["treatment"].startswith("legacy") and r["not_integrated_sets"])),
        authored_with_newer_deliverable_set=sum(1 for r in rows.values() if r["treatment"] == "authored" and any(o["relation"] == "newer" for o in r["not_integrated_sets"])),
        not_integrated_deliverable_sets=sorted({(o["lane"], o["set"]) for r in rows.values() for o in r["not_integrated_sets"]
                                                if r["treatment"].startswith("legacy") or o["relation"] == "newer"}),
        drawn_without_pack_entry=len(drawn_not_in_pack),
        frozen_sets_scanned=len(sets),
        frozen_sets_with_zero_parsed_keys=sum(1 for s in sets if not s["keys"]),
        live_verified_true=sum(1 for r in rows.values() if r["live_verified"] is True),
        w3_sign_phase_keys=len(sign_rows),
        w3_sign_phase_keys_in_pack=sum(1 for s in sign_rows if s["in_pack"]),
        limits=["Draw logs are 60-frame sampled first-activation captures of four Stage 1 flypasts with earlier packs; they are not complete scene coverage.",
                "Layer is a heuristic from lane/set names and same-page inheritance, not a visual verdict.",
                "size_proxy is on-screen native bbox height, not 3D depth.",
                "No row is live-accepted; 'authored' means a frozen candidate exists in this pack, not visual acceptance.",
                "A not-integrated frozen set is existence only; its quality and supersession status are not judged here."])
    out = dict(source_candidate=str(CUR), base_manifest=str(BASE), logs={k: str(v) for k, v in LOGS.items() if v.exists()},
               summary=summary, drawn_without_pack_entry=drawn_not_in_pack, w3_sign_phase_keys=sign_rows,
               frozen_sets=[{k: v for k, v in s.items() if k != "keys"} | dict(key_count=len(s["keys"])) for s in sets],
               rows=list(rows.values()))
    (HERE / "census-v2.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
