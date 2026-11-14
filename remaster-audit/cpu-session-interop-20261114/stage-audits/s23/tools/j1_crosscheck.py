"""J1 (claude-einhander-s23): independent numpy cross-check of the strict class audit + sampled fringe metric
for the 39+39 selected Stage 2/3 keys. PIXEL JOB: run only inside a granted CPU slot.

  python -I j1_crosscheck.py <run_dir> <budget_seconds> [stage]

Resumable: results append to <run_dir>/rows.jsonl (fsync per file); files already present are skipped, so a run that
stops at its budget continues on the next grant. Below-normal priority, single process, no threads beyond numpy's.
Inputs: s23 selection map (pinned below), original Claude's audit result e28553ba (for comparison only), frozen
manifests/words/PNGs (read only). Output only inside <run_dir>.
"""
import json
import os
import sys
from datetime import datetime, timezone

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s23lib as L  # noqa: E402

SEL = L.S23 + "/runs/selection-20261114T133254Z/selection-map.json"
SEL_SHA = "f29ff130d3f2d087e95a90cfebe7892415cf480af3cc3718723f4594b7256250"
DLL_RES = L.ROOT + "/remaster-audit/claude-backlog/class-mip/later-stages-audit/runs/20261114T133157Z/result.json"
DLL_SHA = "e28553ba28ed676bca68021efd364ac78a9da0fff76daeff565c87b8a62ca7a1"
BASE = {"2": L.ROOT + "/remaster-audit/comfy-authoring/w7-stage2/frozen", "3": L.ROOT + "/remaster-audit/comfy-authoring/w7-stage3/frozen"}
FIELDS = ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px", "cells_bad", "pinhole_cells", "nonclass_px")


def page_sources(stage):
    out = {}
    d = BASE[stage]
    for name in sorted(os.listdir(d)):
        mp = f"{d}/{name}/manifest.json"
        if not os.path.exists(mp):
            continue
        m = json.load(open(mp, encoding="utf-8"))
        for tex, pg in (m.get("pages") or {}).items():
            w = pg.get("words") if isinstance(pg, dict) else None
            if isinstance(w, dict) and w.get("path") and tex not in out:
                out[tex] = dict(path=w["path"], sha256=w.get("sha256"), rect=pg.get("vram_rect_words"), from_set=name)
    return out


def norm(p):
    return os.path.normcase(os.path.normpath(p.replace("/", os.sep)))


def main(run_dir, budget_s, only_stage=None):
    pri = L.below_normal()
    b = L.Budget(float(budget_s))
    os.makedirs(run_dir, exist_ok=True)
    rows_p = run_dir + "/rows.jsonl"
    done = {r["path"] for r in L.read_jsonl(rows_p)}
    sel_sha, dll_sha = L.sha256_file(SEL), L.sha256_file(DLL_RES)
    assert sel_sha == SEL_SHA, ("selection map changed", sel_sha)
    assert dll_sha == DLL_SHA, ("audit result changed", dll_sha)
    sel = json.load(open(SEL, encoding="utf-8"))
    dll = {norm(r["path"]): r for r in json.load(open(DLL_RES, encoding="utf-8"))["rows"] if "path" in r}
    L.append_jsonl(run_dir + "/sessions.jsonl", dict(start_utc=datetime.now(timezone.utc).isoformat(), pid=os.getpid(),
                                                     below_normal=pri, budget_s=float(budget_s), already_done=len(done),
                                                     tool_sha256=L.sha256_file(os.path.abspath(__file__)),
                                                     lib_sha256=L.sha256_file(os.path.dirname(os.path.abspath(__file__)) + "/s23lib.py")))
    words_cache, n_new, stopped = {}, 0, False
    for st in ("2", "3"):
        if only_stage and st != only_stage:
            continue
        src = page_sources(st)
        for key, kr in sel["stages"][st]["keys"].items():
            folder = kr["selected_folder"]
            m = json.load(open(f"{BASE[st]}/{folder}/manifest.json", encoding="utf-8"))
            ke = m["keys"][key]
            tex = kr["tex"]
            for fk, f in kr["files"].items():
                path = f"{BASE[st]}/{folder}/{f['path']}"
                if path in done:
                    continue
                if b.left() < 20:
                    stopped = True
                    break
                if tex not in words_cache:
                    s_ = src[tex]
                    idx, wsha, crc_ok = L.load_words(s_["path"], s_["rect"], tex)
                    words_cache[tex] = (idx, wsha, crc_ok, s_)
                idx, wsha, crc_ok, s_ = words_cache[tex]
                c = L.clut_words(ke["clut"]["words_hex"])
                ncls = L.clut_classes(c)[idx]
                png_sha = L.sha256_file(path)
                rgba = L.load_rgba(path)
                s = rgba.shape[1] // ncls.shape[1]
                v = L.validate(rgba, ncls, s)
                fr = L.sampled_fringe(rgba)
                d = dll.get(norm(path))
                cmp = None
                if d and "v2" in d:
                    cmp = {k: dict(np=v[k], dll=d["v2"][k], equal=v[k] == d["v2"][k]) for k in FIELDS}
                rec = dict(stage=int(st), key=key, file=fk, path=path, png_sha256=png_sha, png_sha_matches_map=png_sha == f.get("sha256_actual"),
                           words=dict(path=s_["path"], sha256=wsha, sha_ok=wsha == s_["sha256"], crc_proven=crc_ok),
                           scale=s, np=v, sampled_fringe=fr, dll_compare=cmp,
                           all_equal=(all(x["equal"] for x in cmp.values()) if cmp else None),
                           strict_pass_np=all(v[k] == 0 for k in ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px")) and v["nonclass_px"] == 0,
                           utc=datetime.now(timezone.utc).isoformat())
                L.append_jsonl(rows_p, rec)
                n_new += 1
                print(key, fk, "strict", rec["strict_pass_np"], "equal", rec["all_equal"], "r5", v["r5_fringe_px"],
                      "fringe_p95", fr.get("err_p95"), flush=True)
            if stopped:
                break
        if stopped:
            break
    rows = L.read_jsonl(rows_p)
    summary = dict(updated_utc=datetime.now(timezone.utc).isoformat(), rows=len(rows), expected=156 if not only_stage else 78,
                   complete=(len(rows) >= 156), new_this_session=n_new, stopped_on_budget=stopped,
                   strict_pass_np=sum(1 for r in rows if r["strict_pass_np"]),
                   dll_all_equal=sum(1 for r in rows if r["all_equal"]), dll_rows_missing=sum(1 for r in rows if r["dll_compare"] is None),
                   mismatching=[[r["key"], r["file"], {k: x for k, x in r["dll_compare"].items() if not x["equal"]}] for r in rows
                                if r["dll_compare"] and not r["all_equal"]][:40],
                   png_hash_drift=[[r["key"], r["file"]] for r in rows if not r["png_sha_matches_map"]],
                   inputs=dict(selection_map=SEL_SHA, dll_result=DLL_SHA))
    tmp = run_dir + "/summary.json.tmp"
    json.dump(summary, open(tmp, "w", encoding="utf-8"), indent=1)
    os.replace(tmp, run_dir + "/summary.json")
    L.append_jsonl(run_dir + "/sessions.jsonl", dict(end_utc=datetime.now(timezone.utc).isoformat(), new=n_new, stopped_on_budget=stopped))
    print(json.dumps({k: summary[k] for k in ("rows", "complete", "strict_pass_np", "dll_all_equal", "stopped_on_budget")}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
