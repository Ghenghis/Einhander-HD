#!/usr/bin/env python3
"""s45 menu/HUD: light review of J-I (menu-hud/classsnap/20261114T152840Z). Read-only on the run.
(1) numerical aggregates per variant x size over the 7 keys (primary / s2 / R1..R5 / conn / class changes / STP flips /
    common-visible RGB changes / newly-visible colour vs native); (2) per-key silhouette change vs the authored file
    (visible-mask XOR px and IoU) and vs native nearest; (3) one contact sheet of the glyph region (strip x 192..255, the
    upper-font area the fade aliases draw) for all 7 keys: native nearest | authored | snap-cell | snap-nearest, cropped
    from the run's own review sheets (an ATLAS SIMULATION at 9 px/texel, not an actual screen capture).
Light: one CPU (not 13/15), below normal. Writes ONLY s45/menu-hud/review/ji-<UTC>/."""
import datetime
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

S45 = Path("C:/github/Einhander/remaster-audit/parallel-stages-20261114/s45")
RUN = S45 / "menu-hud/classsnap/20261114T152840Z"
MET = ("r1_centre_bad", "r2_displaced_px", "r3_uniform_bad_px", "r4_island_px", "r5_fringe_px", "s2_viol_px", "conn_viol_px")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rng(xs):
    xs = [x for x in xs if x is not None]
    return [min(xs), max(xs), round(float(np.mean(xs)), 2)] if xs else None


def main():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([c for c in me.cpu_affinity() if c not in (13, 15)][:1])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "menu-hud/review" / f"ji-{stamp}"
    rd.mkdir(parents=True, exist_ok=False)
    r = json.loads((RUN / "result.json").read_text(encoding="utf-8"))
    agg, per_key = {}, []
    for size in ("2048", "1024"):
        au = [row["variants"][size]["authored"] for row in r["rows"]]
        agg[f"authored/{size}"] = dict(primary_pass=sum(a["primary_pass"] for a in au), s2_pass=sum(a["s2_strict_pass"] for a in au),
                                       **{m: rng([a[m] for a in au]) for m in MET})
        for var in ("snap-cell", "snap-nearest"):
            vs = [row["variants"][size][var] for row in r["rows"]]
            agg[f"{var}/{size}"] = dict(
                primary_pass=sum(v["after"]["primary_pass"] for v in vs), s2_pass=sum(v["after"]["s2_strict_pass"] for v in vs),
                **{m: rng([v["after"][m] for v in vs]) for m in MET},
                became_visible=rng([v["became_visible"] for v in vs]), became_cutout=rng([v["became_cutout"] for v in vs]),
                stp_opaque_flips=rng([v["stp_opaque_flips"] for v in vs]),
                common_visible_rgb_changed=rng([v["visible_rgb_changed_on_common_visible"] for v in vs]),
                newly_visible_vs_native_mean=rng([v["newly_visible_vs_native_mean"] for v in vs]),
                newly_visible_vs_native_p95=rng([v["newly_visible_vs_native_p95"] for v in vs]))
    for row in r["rows"]:
        for size in ("2048", "1024"):
            v = row["variants"][size]
            with Image.open(v["input"]) as im:
                a = np.asarray(im.convert("RGBA"))
            out = {}
            for var in ("snap-cell", "snap-nearest"):
                with Image.open(RUN / v[var]["output"]) as im:
                    b = np.asarray(im.convert("RGBA"))
                va, vb = a[..., 3] > 0, b[..., 3] > 0
                out[var] = dict(visible_xor_px=int((va ^ vb).sum()), visible_iou=round(float((va & vb).sum() / max(1, (va | vb).sum())), 4),
                                alpha_changed_px=int((a[..., 3] != b[..., 3]).sum()))
            per_key.append(dict(key=row["key"], size=size, source=row["source"], **out))
    # contact sheet: glyph area x 192..255 of each run review sheet (9 px/texel, 4 tiles of 72 px + 16 px label each)
    tiles = []
    for row in r["rows"]:
        sh = Image.open(RUN / "review" / f"{row['key']}-hud-sim.png").convert("RGB")
        tiles.append((row["key"], sh.crop((192 * 9, 0, 256 * 9, sh.height))))
    W = 64 * 9
    sheet = Image.new("RGB", (W * len(tiles) + 8 * (len(tiles) - 1), tiles[0][1].height + 18), (0, 0, 0))
    dr = ImageDraw.Draw(sheet)
    for i, (k, t) in enumerate(tiles):
        sheet.paste(t, (i * (W + 8), 18))
        dr.text((i * (W + 8) + 4, 3), k, fill=(255, 255, 255))
    sheet.save(rd / "ji-glyph-area-contact.png")
    out = dict(run=stamp, owner="claude-einhander-s45", task="EIN-MENU-HUD-20261114", reviewed=str(RUN / "result.json"),
               reviewed_sha256=sha(RUN / "result.json"), tool_sha256=sha(Path(__file__)),
               note="review sheets are ATLAS SIMULATIONS (9 px/texel), not actual screen captures; no look/live acceptance",
               receipt=dict(cmd_pid=34692, python_pid=24144, affinity=[13], wall_s=2.83, outer_exit=0, killed=False, peak_ws_mib=75.6,
                            processes_left=0, log="menu-hud/J-I.log"),
               aggregates=agg, silhouette_change=per_key,
               contact_sheet=dict(path="ji-glyph-area-contact.png", sha256=sha(rd / "ji-glyph-area-contact.png")))
    (rd / "review.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    for k, v in agg.items():
        print(k, json.dumps(v))
    for p in per_key:
        print(p["key"], p["size"], "cell", p["snap-cell"], "near", p["snap-nearest"])
    print("run", rd.name, sha(rd / "review.json"))


if __name__ == "__main__":
    main()
