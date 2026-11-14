#!/usr/bin/env python3
"""s45 step 1 (claude-einhander-s45, EIN-S4/S5-WHOLE-CELL-20261114): READ-ONLY source / CLUT / region provenance map
for the Stage 4 (11) and Stage 5 (12) selected candidate keys, the shared 05E1881C panorama and the Stage 5 8bpp
Duerer sub-images. No PNG decode, no pixel work, no GPU: JSON parsing plus sha256/CRC32 of small native word/CLUT files.
Writes ONLY remaster-audit/parallel-stages-20261114/s45/source-map/<UTC>/. Below normal priority, one CPU."""
import datetime
import hashlib
import json
import shutil
import sys
import zlib
from pathlib import Path

RA = Path("C:/github/Einhander/remaster-audit")
OUT = RA / "parallel-stages-20261114/s45/source-map"
READINESS = RA / "runtime-review/seven-stage-status-20261114/lane-readiness-20261114T131712Z.json"
READINESS_SHA = "07cd9358083107da96bc209dc1bfa8685820c1316f1455c146c31ac6fc2283b8"
STATIC = RA / "fullgame-prep/static-extraction/stages"
COMFY = RA / "comfy-authoring"
CHK = RA / "runtime-diagnostics-v58/capture-checklists/keys"
PANO = COMFY / "w7-stage4/work/panorama-05E1881C/STATUS.json"


def sha_b(b):
    return hashlib.sha256(b).hexdigest()


def sha_f(p):
    return sha_b(Path(p).read_bytes())


def crc(b):
    return "%08X" % (zlib.crc32(b) & 0xFFFFFFFF)


def lines(p):
    p = Path(p)
    if not p.exists():
        return None
    return [x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip() and not x.startswith("#")]


def rank(a):
    o = sorted(range(len(a)), key=lambda i: a[i])
    r = [0.0] * len(a)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and a[o[j + 1]] == a[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2.0
        i = j + 1
    return r


def clut_stats(b):
    w = [int.from_bytes(b[i:i + 2], "little") for i in range(0, len(b), 2)]
    lum = [0.299 * (v & 31) + 0.587 * ((v >> 5) & 31) + 0.114 * ((v >> 10) & 31) for v in w]
    opaque = [i for i, v in enumerate(w) if v != 0]
    rho = None
    if len(w) == 16 and len(opaque) >= 3:  # Spearman |rho| of luminance vs index over the opaque entries
        rx, ry = rank(opaque), rank([lum[i] for i in opaque])
        n = len(rx)
        mx, my = sum(rx) / n, sum(ry) / n
        cov = sum((a - mx) * (c - my) for a, c in zip(rx, ry))
        vx = sum((a - mx) ** 2 for a in rx) ** 0.5
        vy = sum((c - my) ** 2 for c in ry) ** 0.5
        rho = round(abs(cov / (vx * vy)), 3) if vx and vy else None
    return dict(entries=len(w), cutout_entries=sum(1 for v in w if v == 0), stp_entries=sum(1 for v in w if v & 0x8000),
                opaque_entries=len(opaque), distinct_colours=len(set(v & 0x7FFF for v in w if v)), lum_rank_rho=rho)


def rel(p, d):
    return str(p.relative_to(d)).replace("\\", "/")


def stage_map(st, lane, static, issue):
    sd = static["dir"]
    gate_keys = lines(CHK / f"S{st}-gate-keys.txt")
    later_list = lines(CHK / f"S{st}-confirm-renderable-later.txt")
    hold_list = lines(CHK / f"S{st}-palette-hold-keys.txt")
    S = dict(selection=lane["candidate_selection"], expected_keys=lane["candidate_keys"], sets={}, selected_keys={},
             frozen_inventory={},
             static_files=dict(keys_json=sha_f(sd / "keys.json"), textures_json=sha_f(sd / "textures.json"),
                               cluts_json=sha_f(sd / "cluts.json"), freeze_json=sha_f(sd / "FREEZE.json")))
    later, hold = set(), set()
    selected_dirs = {Path(f["path"]).name: f for f in lane["candidate_folders"]}
    for mf in sorted((COMFY / f"w7-stage{st}/frozen").glob("*/manifest.json")):
        m = json.loads(mf.read_text(encoding="utf-8"))
        sup = m.get("supersedes")
        S["frozen_inventory"][mf.parent.name] = dict(
            manifest_sha256=sha_f(mf), status=m.get("status"),
            supersedes=sup.get("revision") if isinstance(sup, dict) else sup,
            selected=mf.parent.name in selected_dirs, pages=list((m.get("pages") or {}).keys()))
    for name, f in selected_dirs.items():
        mf = Path(f["manifest"])
        msha = sha_f(mf)
        if msha != f["manifest_sha256"]:
            issue(f"S{st} {name}: manifest sha {msha} != readiness {f['manifest_sha256']}")
        m = json.loads(mf.read_text(encoding="utf-8"))
        d = mf.parent
        files = m.get("files") or {}
        missing = [p for p in files if not (d / p).exists()]
        unlisted = sorted(rel(p, d) for p in d.rglob("*") if p.is_file() and rel(p, d) not in files and p.name != "manifest.json")
        size_bad = [p for p, v in files.items() if (d / p).exists() and v.get("bytes") is not None and (d / p).stat().st_size != v["bytes"]]
        if missing or unlisted or size_bad:
            issue(f"S{st} {name}: missing {len(missing)} unlisted {len(unlisted)} size-mismatch {len(size_bad)}")
        set_rec = dict(manifest_sha256=msha, status=m.get("status"), key_status=m.get("key_status"),
                       files_listed=len(files), files_missing=missing, files_unlisted=unlisted, files_size_mismatch=size_bad,
                       class_validation=m.get("class_validation"), pages={},
                       note="file existence and byte size checked; per-file sha256 of PNGs deferred to the CPU slot")
        for t, p in (m.get("pages") or {}).items():
            src = p.get("source") or {}
            wp = Path(src.get("path", ""))
            wb = wp.read_bytes() if wp.is_file() else b""
            st_tex = static["tex"].get(t) or {}
            pr = dict(member=p.get("member"), page_xy=p.get("page_xy"), mode=p.get("mode"), words=str(wp),
                      words_bytes=len(wb), words_sha_ok=sha_b(wb) == src.get("sha256"), crc_proven=crc(wb) == t,
                      static_tex_confidence=st_tex.get("confidence"), static_tex_kinds=st_tex.get("kinds"),
                      static_tex_members=sorted({s_.get("member") for s_ in st_tex.get("sources", [])}),
                      renderable_later=len(p.get("renderable_later") or []),
                      palette_hold_keys=p.get("palette_hold_keys"),
                      runtime_written_clut_positions=p.get("runtime_written_clut_positions_index_master_only"),
                      regions=[dict(kind=r.get("kind"), texels=r.get("texels"),
                                    boxes=r.get("boxes") or r.get("box") or r.get("rects"),
                                    blocks8=len(r.get("blocks8") or []) or None) for r in (p.get("regions") or [])],
                      rendered=[])
            if not pr["words_sha_ok"] or not pr["crc_proven"]:
                issue(f"S{st} {name} {t}: words sha_ok={pr['words_sha_ok']} crc_proven={pr['crc_proven']}")
            later.update(r["key"] for r in p.get("renderable_later") or [])
            hold.update(p.get("palette_hold_keys") or [])
            for rk in p.get("rendered_keys") or []:
                key = rk["key"]
                pal = key.split("-")[1]
                se = static["keys"].get(key) or {}
                kd = sd / "keys"
                cp, kp = kd / f"{key}.clut.bin", kd / f"{key}.words.bin"
                cb = cp.read_bytes() if cp.is_file() else b""
                kw = kp.read_bytes() if kp.is_file() else b""
                rec = dict(key=key, clut_xy=rk.get("clut_xy"), confidence=rk.get("confidence"), palette_hold=rk.get("palette_hold"),
                           static_key=dict(present=bool(se), kind=se.get("kind"), depth=se.get("depth"),
                                           confidence=se.get("confidence"), pair_count=se.get("pair_count"),
                                           pal_candidates_at_position=se.get("pal_candidates_at_position"),
                                           pal_source=se.get("pal_source"), clut_xy=se.get("clut_xy"),
                                           pal_all_zero=se.get("pal_all_zero")),
                           clut_crc_proven=bool(cb) and crc(cb) == pal, clut_sha256=sha_b(cb) if cb else None,
                           clut=clut_stats(cb) if cb else None, key_words_identical_to_page=kw == wb,
                           in_gate_list=(key in gate_keys) if gate_keys is not None else None, files={})
                if se and se.get("clut_xy") != rk.get("clut_xy"):
                    issue(f"S{st} {key}: manifest clut_xy {rk.get('clut_xy')} != static {se.get('clut_xy')}")
                if not rec["clut_crc_proven"]:
                    issue(f"S{st} {key}: CLUT CRC not proven from static keys/{key}.clut.bin")
                if not rec["key_words_identical_to_page"]:
                    issue(f"S{st} {key}: static key words differ from the page source words")
                for fk in ("png_2048", "png_1024"):
                    fr = rk.get(fk) or {}
                    fp = d / fr.get("path", "?")
                    v = fr.get("validation") or {}
                    rec["files"][fk] = dict(path=str(fp), exists=fp.is_file(), bytes=fp.stat().st_size if fp.is_file() else None,
                                            manifest_sha256=fr.get("sha256"), size=v.get("size"),
                                            lane_centre_class_mismatch=v.get("centre_class_mismatch"),
                                            alpha_values=v.get("alpha_values"), centre_classes_stamped=fr.get("centre_classes_stamped"))
                    if not fp.is_file():
                        issue(f"S{st} {name} {key} {fk}: missing {fp}")
                pr["rendered"].append(rec)
                S["selected_keys"].setdefault(key, []).append(name)
            set_rec["pages"][t] = pr
        S["sets"][name] = set_rec
    S["unique_selected_keys"] = len(S["selected_keys"])
    if S["unique_selected_keys"] != S["expected_keys"]:
        issue(f"S{st}: {S['unique_selected_keys']} unique selected keys != readiness {S['expected_keys']}")
    S["alternatives"] = {k: v for k, v in S["selected_keys"].items() if len(v) > 1}
    S["gate_list"] = dict(path=str(CHK / f"S{st}-gate-keys.txt"), n=len(gate_keys or []),
                          equal_to_selected=sorted(gate_keys or []) == sorted(S["selected_keys"]))
    ll = set(later_list or [])
    S["renderable_later_n"] = len(later)
    S["renderable_later_list"] = dict(n=len(ll), equal=ll == later, only_in_manifests=sorted(later - ll)[:20], only_in_list=sorted(ll - later)[:20])
    hl = set(hold_list or [])
    S["palette_hold_n"] = len(hold)
    S["palette_hold_list"] = dict(n=len(hl), equal=hl == hold, only_in_manifests=sorted(hold - hl)[:40], only_in_list=sorted(hl - hold)[:40])
    S["renderable_later"] = sorted(later)
    S["palette_hold"] = sorted(hold)
    return S


def panorama(static):
    pano = json.loads(PANO.read_text(encoding="utf-8"))
    P = dict(status_path=str(PANO), status_sha256=sha_f(PANO), status=pano.get("status"), owner=pano.get("owner"), stages={})
    for st in (4, 5):
        sd = static[st]["dir"]
        wb = (sd / "textures/05E1881C.words.bin").read_bytes()
        te = static[st]["tex"].get("05E1881C") or {}
        ks = sorted((e for e in static[st]["keys"].values() if e["key"].startswith("05E1881C-")), key=lambda e: -(e.get("pair_count") or 0))
        rows = []
        for e in ks:
            cp = sd / "keys" / f"{e['key']}.clut.bin"
            cb = cp.read_bytes() if cp.is_file() else b""
            rows.append(dict(key=e["key"], clut_xy=e.get("clut_xy"), depth=e.get("depth"), kind=e.get("kind"), confidence=e.get("confidence"),
                             pair_count=e.get("pair_count"), tex_member=e.get("tex_member"), pal_all_zero=e.get("pal_all_zero"),
                             pal_candidates_at_position=e.get("pal_candidates_at_position"),
                             clut_crc_proven=bool(cb) and crc(cb) == e["key"][9:], clut=clut_stats(cb) if cb else None))
        status_list = pano["keys"].get(f"stage{st}_nonzero_likely") or []
        chk = [x.split("-")[-1] for x in (lines(CHK / f"S{st}-05E1881C-keys.txt") or [])]
        nonzero = [r["key"][9:] for r in rows if not r["pal_all_zero"]]
        P["stages"][st] = dict(words_sha256=sha_b(wb), crc_proven=crc(wb) == "05E1881C",
                               static_members=sorted({s_.get("member") for s_ in te.get("sources", [])}),
                               keys=rows, static_keys=len(rows), nonzero_static=len(nonzero), status_nonzero=len(status_list),
                               status_equal=sorted(nonzero) == sorted(status_list),
                               checklist_n=len(chk), checklist_equal=sorted(chk) == sorted(status_list))
    P["byte_identical_across_stages"] = P["stages"][4]["words_sha256"] == P["stages"][5]["words_sha256"]
    named = [str(p) for s in ("w7-stage4", "w7-stage5") for p in (COMFY / s).rglob("*05E1881C*") if p.is_file()]
    P["files_named_05E1881C_under_w7_stage4_5"] = named
    P["frozen_deliverable_exists"] = any("\\frozen\\" in n or "/frozen/" in n for n in named)
    for v in ("v1", "v2"):
        m = json.loads((COMFY / f"w7-stage5/frozen/s5-world-3-1-{v}/manifest.json").read_text(encoding="utf-8"))
        P[f"s5_world_{v}_reference"] = m.get("shared_pages_referenced_not_built")
    return P


def duerer_8bpp(static):
    s5 = static[5]
    by_sha = {}
    for t in s5["tex"]:
        p = s5["dir"] / f"textures/{t}.words.bin"
        if p.is_file() and p.stat().st_size == 32768:
            by_sha.setdefault(sha_f(p), []).append(t)
    dm = json.loads((COMFY / "w7-stage5/frozen/s5-duerer-armour-v2/manifest.json").read_text(encoding="utf-8"))
    E = dict(key_rule="runtime key of a depth-1 draw: CRC32 (LE words) of 128 VRAM columns x 256 rows from the texpage x "
                      "(windows-x64/psxrecomp/runtime/src/hd_native_page.h: hd_page_hash width 64<<depth); 8bpp CLUT = 256 words of one CLUT row",
             regions={}, depth1_page_keys=[])
    for t in ("1F11EE57", "BFC445B0", "3D108041"):
        p = dm["pages"][t]
        for r in p.get("regions") or []:
            if r.get("kind") != "native-8bpp-pending":
                continue
            b8 = r.get("blocks8") or []
            us, vs = [b[0] for b in b8], [b[1] for b in b8]
            u0, u1, v0, v1 = min(us) * 8, max(us) * 8 + 7, min(vs) * 8, max(vs) * 8 + 7
            x = p["page_xy"][0]
            E["regions"][t] = dict(page_xy=p["page_xy"], member=p.get("member"), blocks8=len(b8), texels=r.get("texels"),
                                   bbox_4bpp_texels=[u0, v0, u1, v1], bbox_words=[u0 // 4, v0, u1 // 4, v1],
                                   as_8bpp_texpage_here=dict(texpage_x=x, u=[(u0 // 4) * 2, (u1 // 4) * 2 + 1], v=[v0, v1]),
                                   as_8bpp_texpage_one_page_left=dict(texpage_x=x - 64, u=[128 + (u0 // 4) * 2, 128 + (u1 // 4) * 2 + 1], v=[v0, v1]),
                                   rule=r.get("rule"))
    kd = s5["dir"] / "keys"
    for e in sorted(s5["keys"].values(), key=lambda e: (e["page_xy"][0], e["key"])):
        if e.get("depth") != 1 or e.get("kind") != "page" or e["page_xy"][1] != 0 or not (320 <= e["page_xy"][0] <= 768):
            continue
        wb = (kd / f"{e['key']}.words.bin").read_bytes()
        cb = (kd / f"{e['key']}.clut.bin").read_bytes()
        rows = [wb[r * 256:(r + 1) * 256] for r in range(256)]
        left = b"".join(rw[:128] for rw in rows)
        right = b"".join(rw[128:] for rw in rows)
        E["depth1_page_keys"].append(dict(key=e["key"], tex_member=e.get("tex_member"), page_xy=e["page_xy"], clut_xy=e.get("clut_xy"),
                                          pair_count=e.get("pair_count"), confidence=e.get("confidence"), pal_all_zero=e.get("pal_all_zero"),
                                          pal_candidates_at_position=e.get("pal_candidates_at_position"), pal_source=e.get("pal_source"),
                                          words_bytes=len(wb), tex_crc_proven=crc(wb) == e["key"][:8], clut_crc_proven=crc(cb) == e["key"][9:],
                                          left_half_4bpp_tex=by_sha.get(sha_b(left)), right_half_4bpp_tex=by_sha.get(sha_b(right)),
                                          clut=clut_stats(cb)))
    return E


def main():
    try:
        import psutil
        me = psutil.Process()
        me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
        me.cpu_affinity([me.cpu_affinity()[-1]])
    except Exception as e:  # noqa: BLE001
        print("priority not lowered:", e, file=sys.stderr)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = OUT / stamp
    rd.mkdir(parents=True, exist_ok=False)
    shutil.copy2(Path(__file__), rd / Path(__file__).name)
    rsha = sha_f(READINESS)
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    res = dict(run=stamp, owner="claude-einhander-s45", tasks=["EIN-S4-WHOLE-CELL-20261114", "EIN-S5-WHOLE-CELL-20261114"],
               readiness=dict(path=str(READINESS), sha256=rsha, sha_ok=rsha == READINESS_SHA), stages={}, issues=[],
               status="DATA ONLY; read-only on every stage lane and static export; no PNG decode")
    issue = res["issues"].append
    static = {}
    for st in (4, 5):
        sd = STATIC / f"stage{st}"
        static[st] = dict(dir=sd, keys={e["key"]: e for e in json.loads((sd / "keys.json").read_text(encoding="utf-8"))},
                          tex={e["tex"]: e for e in json.loads((sd / "textures.json").read_text(encoding="utf-8"))})
        lane = next(s for s in readiness["stages"] if s["stage"] == st)
        res["stages"][st] = stage_map(st, lane, static[st], issue)
    res["panorama_05E1881C"] = panorama(static)
    res["duerer_8bpp"] = duerer_8bpp(static)
    out = rd / "source-map.json"
    out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for st, S in res["stages"].items():
        print(f"S{st}: unique selected {S['unique_selected_keys']}/{S['expected_keys']} alternatives {list(S['alternatives'])} "
              f"later {S['renderable_later_n']} (list equal {S['renderable_later_list']['equal']}) hold {S['palette_hold_n']} "
              f"(list equal {S['palette_hold_list']['equal']}) gate_list_equal {S['gate_list']['equal_to_selected']}")
    P = res["panorama_05E1881C"]
    print("panorama byte-identical", P["byte_identical_across_stages"], "frozen deliverable", P["frozen_deliverable_exists"],
          {st: (v["static_keys"], v["nonzero_static"], v["status_equal"], v["checklist_equal"]) for st, v in P["stages"].items()})
    for k in res["duerer_8bpp"]["depth1_page_keys"]:
        print("8bpp", k["key"], k["tex_member"], k["page_xy"], k["clut_xy"], "pairs", k["pair_count"], "zero", k["pal_all_zero"],
              "L", k["left_half_4bpp_tex"], "R", k["right_half_4bpp_tex"], "crc", k["tex_crc_proven"], k["clut_crc_proven"])
    print("issues", len(res["issues"]))
    for i in res["issues"]:
        print("  ", i)
    print("run", stamp, "source-map.json", sha_f(out))


if __name__ == "__main__":
    main()
