#!/usr/bin/env python3
"""s45 menu/HUD (EIN-MENU-HUD-20261114): implemented-vs-missing UI STATE REGISTER. Light, read-only (JSON reads only).

For each UI state (boot, title, title menu, selection, config/file/name entry/rankings, instructions/demo, in-play HUD,
pause/continue/countdown, HUD fades, game over, results, return to title) it lists the texture families (TEX) that draw
it, every known key (typography inventory + any frozen delivery), which frozen lane folders deliver each key, the keys no
lane delivers, live GL-submission evidence (docs/media/gallery/stage1-ui-results.json) and the open items the lane
READMEs/ledgers state. "Delivered" means a frozen candidate folder carries the key: NOT installed, NOT live-accepted, and
NOT class-validated by this tool (s45 w6-primary-probe shows centre-only fixes fail the proto-v2b primary policy).
Writes ONLY s45/menu-hud/state-register/<UTC>/register.json and REGISTER.md."""
import collections
import datetime
import hashlib
import json
import re
from pathlib import Path

ROOT = Path("C:/github/Einhander")
CA = ROOT / "remaster-audit/comfy-authoring"
S45 = ROOT / "remaster-audit/parallel-stages-20261114/s45"
TYPO = CA / "t9-title-menus/inventory/typography-inventory.json"
UI = ROOT / "docs/media/gallery/stage1-ui-results.json"
JH = S45 / "menu-hud/fade-aliases-v1/20261114T150907Z/result.json"
STOCK = Path("C:/github/REMASTER_STAGING/stage1_remaster/page-source/stock/einhander-texture-replacements")
LANES = sorted(p.parent.name for p in CA.glob("*/frozen"))   # every comfy-authoring lane with a frozen/ folder
REGION_CAVEAT = {"8BA3BB4D": "HUD gauge rect [0,64,64,96] sits on a player-hull page: a hull delivery may keep native there",
                 "B24C6DA2": "HUD arrow-gauge strip overlaps player-hull pages: region coverage unproven",
                 "B2473AF8": "lives glyph exact regions (w4-signs-hud) on player page 832,256"}
KEY_RE = re.compile(r"\b([0-9A-F]{8})-([0-9A-F]{8})\b")
STATES = [   # (state, TEX families, behaviour still needing an installed-menu run)
    ("boot splash", ["1AEAD6A5", "7F7452F9", "4E783C96"], "boot order before pack activation"),
    ("title screen / logo / footer", ["282438F3", "1D953D67", "8E1A509D"], "attract/demo loop and return"),
    ("title menu (GAME START / CONFIGURATION / FILE OPTION / GALLERY)", ["323B5FB0"], "cursor highlight / STP blend states"),
    ("fighter / armament selection", ["D0365088", "1AD90FC9", "3DA22883", "41E75A55", "7D2C7E3C", "AAE3C8F2", "57FFDED8", "EF372CD7",
                                      "ECFB77E3"],
     "highlighted CLUT states, selector arrows (key unproven)"),
    ("configuration / file option / name entry / rankings",
     ["2C6866AA", "8BE06E98", "8D0FCF8A", "9D8DF52A", "AD49126E", "C544AC0D", "B77B98B9", "AEE859DC"],
     "every page of Configuration, File Option save/load, name grid, ranking table"),
    ("instructions / demo play", ["E6B65424"], "demo attract text"),
    ("in-play HUD (score, ammo, weapon names, lives, hit gauge, arrows)",
     ["BDAE4156", "E1F18F98", "786B98BF", "2C781811", "921FC559", "D050AD1B", "5C02D3C1", "913A6603", "913FE978", "5F101F62",
      "AAA5C104", "E4774D79", "44C16454", "8BA3BB4D", "B24C6DA2", "B2473AF8"], "weapon pickup/swap wordmarks, lives loss"),
    ("pause / CONTINUE? / countdown / QUIT", ["DD0B6963", "BDAE4156"], "pause menu, continue countdown, quit-to-title"),
    ("HUD fade overlays (stage-end / boss-kill)", ["BDAE4156", "D050AD1B", "5C02D3C1", "913A6603", "913FE978", "5F101F62", "AAA5C104"],
     "157 historical fade aliases: palette phases"),
    ("game over", ["5125FF82"], "game over -> title"),
    ("results / evaluation / grades", ["8E1A509D", "48F8001A", "FCCD2514"], "Total / Field / Fight evaluation pages"),
    ("return to title", [], "behaviour only: reuses the title textures; not observed live"),
]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def keys_in(obj):
    return {f"{a}-{b}" for a, b in KEY_RE.findall(json.dumps(obj))}


def manifest_keys(m):
    """Keys a manifest delivers: 'keys' (list of str/dict) or 'files' (list of dicts with 'key'); else regex over 'keys'."""
    out = set()
    for fld in ("keys", "files", "targets"):
        v = m.get(fld)
        if isinstance(v, list):
            for e in v:
                if isinstance(e, str) and KEY_RE.fullmatch(e):
                    out.add(e)
                elif isinstance(e, dict) and isinstance(e.get("key"), str) and KEY_RE.fullmatch(e["key"]):
                    out.add(e["key"])
        elif isinstance(v, dict):
            out |= {k for k in v if KEY_RE.fullmatch(k)}
        if out:
            return out, fld
    return out, None


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "menu-hud/state-register" / stamp
    rd.mkdir(parents=True, exist_ok=False)
    typo = json.loads(TYPO.read_text(encoding="utf-8"))
    ui = json.loads(UI.read_text(encoding="utf-8"))
    inputs = {str(TYPO): sha(TYPO), str(UI): sha(UI)}
    # frozen deliveries: every <lane>/frozen/<folder>/manifest.json
    deliveries, by_key, region_cov = [], collections.defaultdict(list), collections.defaultdict(list)
    idx_meta = {}
    for lane in LANES:
        for ix in ("FROZEN-INDEX.json", "INDEX.json"):
            p = CA / lane / ix
            if p.is_file():
                inputs[str(p)] = sha(p)
                for e in json.loads(p.read_text(encoding="utf-8")).get("entries", []):
                    if isinstance(e, dict) and "folder" in e:
                        idx_meta[(lane, e["folder"].split("/")[-1])] = dict(status=e.get("status"), supersedes=e.get("supersedes"))
        for mp in sorted((CA / lane / "frozen").glob("*/manifest.json")):
            m = json.loads(mp.read_text(encoding="utf-8"))
            ks, fld = manifest_keys(m)
            meta = idx_meta.get((lane, mp.parent.name), {})
            sup = str(meta.get("supersedes") or m.get("supersedes") or "")
            d = dict(lane=lane, folder=mp.parent.name, manifest=str(mp.relative_to(ROOT)), manifest_sha256=sha(mp),
                     status=meta.get("status") or m.get("status"), key_field=fld, keys=sorted(ks), supersedes=sup[:300])
            deliveries.append(d)
            for k in ks:
                by_key[k].append(f"{lane}/{d['folder']}")
            for e in m.get("keys") if isinstance(m.get("keys"), list) else []:   # exact-region deliveries covering page keys
                if isinstance(e, dict) and e.get("exact_region_key"):
                    for pk in set(e.get("craft_page_keys_same_region") or []):
                        region_cov[pk].append(f"{lane}/{d['folder']}:{e['exact_region_key']} uv {e.get('source_uv_half_open')}")
    # s45 J-H candidates (class-failing; derived CLUTs)
    jh_keys = set()
    if JH.is_file():
        inputs[str(JH)] = sha(JH)
        jh_keys = {e["key"] for e in json.loads(JH.read_text(encoding="utf-8"))["keys"]}
    typo_keys = typo["keys"]
    submitted = {e["key"] for e in ui.get("font_bindings_submitted_gl", [])}
    states = []
    for name, texs, behaviour in STATES:
        tset = set(texs)
        if name.startswith("HUD fade"):   # the 157 historical fade aliases: J-H 152 derived + w6 hud-fades-v1 24
            known = sorted(jh_keys | {k for k, v in by_key.items() if "w6-hud-fades/hud-fades-v1" in v})
        else:
            known = sorted({k for k in typo_keys if k[:8] in tset} | {k for k in by_key if k[:8] in tset})
        rows = []
        for k in known:
            lanes = sorted(by_key.get(k, []))
            ti = typo_keys.get(k, {})
            rows.append(dict(key=k, priority=ti.get("priority"), roles=ti.get("roles"), delivered_in=lanes,
                             s45_jh_candidate=k in jh_keys, gl_submitted_live=k in submitted,
                             native_source_ready=all((STOCK / f"{k}.{x}.bin").is_file() for x in ("words", "clut")),
                             region_caveat=REGION_CAVEAT.get(k[:8]), region_covered_by=sorted(region_cov.get(k, [])),
                             legacy_v13_pack=bool((ti.get("v13") or {}).get("exists")),
                             legacy_v13_origin=(ti.get("v13") or {}).get("candidate_json_origin")))
        n_del = sum(1 for r in rows if r["delivered_in"])
        states.append(dict(state=name, textures=texs, behaviour_open=behaviour, keys=len(rows), delivered=n_del,
                           only_s45_candidate=sum(1 for r in rows if not r["delivered_in"] and r["s45_jh_candidate"]),
                           undelivered=[r["key"] for r in rows if not r["delivered_in"] and not r["s45_jh_candidate"]],
                           undelivered_region_covered=[r["key"] for r in rows if not r["delivered_in"] and r["region_covered_by"]],
                           undelivered_legacy_v13_only=[r["key"] for r in rows if not r["delivered_in"] and r["legacy_v13_pack"]],
                           live_gl_submitted=[r["key"] for r in rows if r["gl_submitted_live"]], rows=rows))
    # highest-ready missing: typography keys with priority high and no frozen delivery and no s45 candidate
    missing_high = sorted(k for k, v in typo_keys.items() if v.get("priority") == "high" and not by_key.get(k) and k not in jh_keys)
    ready = {k: all((STOCK / f"{k}.{x}.bin").is_file() for x in ("words", "clut")) for k in typo_keys}
    missing_norm = sorted(k for k, v in typo_keys.items() if v.get("priority") != "high" and not by_key.get(k) and k not in jh_keys)
    out = dict(run=stamp, owner="claude-einhander-s45", task="EIN-MENU-HUD-20261114", tool_sha256=sha(__file__), inputs=inputs,
               scope_note="delivered = present in a frozen candidate folder; not installed, not live-accepted, not class-validated here",
               live_evidence=dict(observed_ui=ui.get("observed_ui"), return_to_title_verified=ui.get("return_to_title_verified"),
                                  font_bindings_submitted_gl=sorted(submitted), limitations=ui.get("limitations")),
               v13_text_ink_flags=typo.get("findings", {}).get("v13_text_ink_flags"),
               states=states, deliveries=deliveries,
               missing=dict(high=missing_high, normal=missing_norm,
                            high_roles={k: typo_keys[k].get("roles") for k in missing_high},
                            native_source_ready={k: ready[k] for k in missing_high + missing_norm},
                            high_region_covered={k: sorted(region_cov[k]) for k in missing_high if region_cov.get(k)},
                            high_without_any_coverage=[k for k in missing_high if not region_cov.get(k)]),
               region_caveats=REGION_CAVEAT, lanes_scanned=LANES)
    (rd / "register.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    md = [f"# Menu / HUD state register `{stamp}` (s45, EIN-MENU-HUD-20261114)", "",
          "Delivered = carried by a frozen candidate folder. That is not installed, not live-accepted and not class-validated.",
          "Live evidence: the closed 600 s Stage 1 census (`docs/media/gallery/stage1-ui-results.json`).", "",
          "| state | textures | keys | delivered | s45-only candidate | undelivered (region-covered / legacy v13 only) | GL-submitted live | behaviour still open |",
          "|---|---|---|---|---|---|---|---|"]
    for s in states:
        md.append(f"| {s['state']} | {', '.join(s['textures']) or '-'} | {s['keys']} | {s['delivered']} | {s['only_s45_candidate']} | "
                  f"{len(s['undelivered'])} ({len(s['undelivered_region_covered'])} / {len(s['undelivered_legacy_v13_only'])}) | {len(s['live_gl_submitted'])} | {s['behaviour_open']} |")
    md += ["", f"Observed live: {', '.join(ui.get('observed_ui') or [])}. Return to title verified: {ui.get('return_to_title_verified')}.", "",
           f"## Typography keys with no frozen delivery and no s45 candidate: high {len(missing_high)}, normal {len(missing_norm)}", ""]
    for k in missing_high:
        cov = "; region-covered by " + ", ".join(region_cov[k]) if region_cov.get(k) else ""
        md.append(f"- high `{k}` (native source {'ready' if ready[k] else 'NOT archived'}{cov}): {'; '.join(typo_keys[k].get('roles') or [])[:120]}")
    md += ["", "## Undelivered keys per state", ""]
    for s in states:
        if s["undelivered"]:
            md.append(f"- {s['state']}: " + ", ".join(f"`{k}`" for k in s["undelivered"][:40]) + (" ..." if len(s["undelivered"]) > 40 else ""))
    (rd / "REGISTER.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("deliveries", len(deliveries), "keys delivered", len(by_key), "typo keys", len(typo_keys))
    for s in states:
        print(f"{s['state'][:48]:48} keys {s['keys']:4} del {s['delivered']:4} s45 {s['only_s45_candidate']:4} undel {len(s['undelivered']):4} live {len(s['live_gl_submitted'])}")
    print("missing high", [(k, ready[k]) for k in missing_high])
    print("lanes", len(LANES), "high region-covered", sum(1 for k in missing_high if region_cov.get(k)),
          "high uncovered", [k for k in missing_high if not region_cov.get(k)])
    print("missing normal", len(missing_norm), missing_norm[:20])
    print("run", stamp, sha(rd / "register.json"))


if __name__ == "__main__":
    main()
