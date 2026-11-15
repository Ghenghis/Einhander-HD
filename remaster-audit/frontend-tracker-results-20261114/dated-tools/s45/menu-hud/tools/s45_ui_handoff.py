#!/usr/bin/env python3
"""s45 -> claude-einhander-ui handoff packet for EIN-MENU-HUD-20261114 (prepared; released only after the UI owner joins).
Light, read-only: hashes the s45 menu-hud tools and latest results NOW (no recomputation), states remaining work and
rules. Writes ONLY s45/menu-hud/handoff/<UTC>/HANDOFF-UI.json and HANDOFF-UI.md."""
import datetime
import hashlib
import json
from pathlib import Path

S45 = Path("C:/github/Einhander/remaster-audit/parallel-stages-20261114/s45")
MH = S45 / "menu-hud"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


TOOLS = ["menu-hud/tools/s45_fade_recover.py", "menu-hud/tools/s45_fade_provenance.py", "menu-hud/tools/s45_fade_alias_render.py",
         "menu-hud/tools/s45_w6_crosscheck.py", "menu-hud/tools/s45_w6_primary_probe.py", "menu-hud/tools/s45_menu_register.py",
         "menu-hud/tools/s45_menu_gates.py", "menu-hud/tools/s45_hud_classsnap.py", "menu-hud/tools/s45_ji_review.py",
         "menu-hud/tools/s45_hud_epx_retrace.py", "menu-hud/tools/s45_gauge_b24.py", "menu-hud/tools/s45_gauge_v13snap.py",
         "menu-hud/tools/s45_menu_primary_audit.py", "menu-hud/tools/s45_menu_primary_audit_v2.py",
         "menu-hud/tools/s45_menu_primary_audit_v3.py", "tools/s45_grant_launch.ps1"]
RESULTS = [  # (id, path, verdict)
    ("fade-recovery", "menu-hud/fade-recovery/20261114T150008Z/recovery.json",
     "152/157 historical HUD fade CLUTs DERIVED (CRC-matched candidates, NOT byte captures); 1234997C x4 + B7EC091D x1 only in w6"),
    ("fade-provenance", "menu-hud/fade-recovery/20261114T150530Z-provenance/provenance.json", "derived-vs-captured labels; expected false matches 0.018"),
    ("w6-crosscheck", "menu-hud/crosscheck-w6/20261114T151137Z/crosscheck.json", "19/19 overlapping keys agree with w6; union 157/157"),
    ("J-H", "menu-hud/fade-aliases-v1/20261114T150907Z/result.json", "152 strips by frozen w3 method; ALL 304 files fail class audit (kept as authored candidates)"),
    ("w6-primary-probe", "menu-hud/w6-primary-probe/20261114T151757Z/probe.json", "w6 centre-forced files fail proto-v2b primary 0/8"),
    ("state-register", "menu-hud/state-register/20261114T154752Z/register.json",
     "per-state coverage; gaps: DEMO PLAY E6B65424 x3 (no source, CR-02), hit gauge B24C6DA2 (now J-K/J-K2 candidates)"),
    ("gates-join", "menu-hud/gates/20261114T153536Z/gates.json", "w4 G-S1..16 x register; J-L folder order"),
    ("J-I", "menu-hud/classsnap/20261114T152840Z/result.json", "font snap-cell/nearest primary 14/14, common-visible RGB 0; curve bumps; NOT look-accepted"),
    ("J-I-review", "menu-hud/review/ji-20261114T153039Z/review.json", "aggregates + 7-key contact sheet"),
    ("J-M", "menu-hud/epx-retrace/20261114T154219Z/result.json", "REJECTED: font EPX R4 pinholes 6/7 + worse readability; do NOT rerun / no J-M2"),
    ("J-K", "menu-hud/gauge-B24C6DA2-v1/20261114T154853Z/result.json", "gauge EPX primary 66/66; lumpy chevrons; NOT look-accepted"),
    ("J-K2", "menu-hud/gauge-v13snap/20261114T155803Z/result.json",
     "v13 gauge snap primary 66/66, common-visible RGB 0; better look than J-K; 1024 subsample aliased; NOT look-accepted; started 33 s late (disclosed)"),
    ("J-L1", "menu-hud/primary-audit/20261114T155808Z/result.json", "PARTIAL: menu-class-exact-v1 pack 45 files, primary 4/45"),
    ("J-L2", "menu-hud/primary-audit/20261114T160358Z/result.json", "PARTIAL: runtime-2048 83 files in 9/11 gate folders, primary 7/83"),
    ("J-L-plan", "menu-hud/primary-audit/20261114T160508Z/plan.json", "133 gate files remain: 3x2048, 86x1024, 44 pack"),
]


def main():
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = MH / "handoff" / stamp
    rd.mkdir(parents=True, exist_ok=False)
    tools = {t: sha(S45 / t) for t in TOOLS}
    results = [dict(id=i, path=f"s45/{p}", sha256=sha(S45 / p), verdict=v) for i, p, v in RESULTS]
    out = dict(
        packet=stamp, from_owner="claude-einhander-s45", to_owner="claude-einhander-ui", task="EIN-MENU-HUD-20261114",
        status="PREPARED; release only after claude-einhander-ui actually joins Hermes and claims the task",
        acceptance="NONE: nothing installed, integrated, live-tested or look-accepted; all CPU class checks are evidence, not menu completion",
        tools_sha256=tools, latest_results=results,
        pending_request=dict(id="J-L3", msg="msg_f9935e38175616f9", tool="menu-hud/tools/s45_menu_primary_audit_v3.py",
                             args="--resume-from menu-hud/primary-audit/20261114T155808Z/result.json menu-hud/primary-audit/20261114T160358Z/result.json "
                                  "--folders menu-class-exact-v1 hud-prompts-BDAE4156-v4 hud-prompts-BDAE4156-v5 results-footer-8E1A509D-v4 "
                                  "results-footer-8E1A509D-v5 title-menu-323B5FB0-v5 prompt-sheet-BDAE4156-DD0B6963-w5-v1 selection-headers-D0365088-v3 "
                                  "selection-labels-1AD90FC9-v4 story-font-AEE859DC-v1 spec-text-1AD90FC9-w5-v2 --no-s2 --budget-seconds 25",
                             note="not granted yet; the new owner should re-request under its own name and write into its own allowed output root"),
        remaining=[
            "finish the gate-folder primary audit (133 files) and then the other menu/HUD lanes (~1540 PNGs total; only 128 audited)",
            "class-faithful repair proposals for representative failing gate files (cell snap as J-I/J-K2; no blanket exception): e.g. "
            "w5 prompt-sheet BDAE4156-DD0B6963 (conn 3.5-4.9k), w4 menu-class-exact 1AD90FC9 selection labels (conn ~275k), "
            "t9 title-menu 323B5FB0, results-footer 8E1A509D",
            "HUD font: J-I snap-cell is the best measured class-valid option; curve bumps remain; a class-aware retrace that keeps the "
            "authored silhouettes is still open (NOT EPX)",
            "hit gauge B24C6DA2: choose between J-K (EPX) and J-K2 (v13 snap); fix 1024 aliasing (subsample) without breaking classes",
            "DEMO PLAY E6B65424 x3: no native words archived -> capture CR-02 (Codex)",
            "157 fade aliases: 152 DERIVED CLUTs must stay labelled derived until a byte capture at (304,492)/(288,500) confirms them",
            "live gates G-S1..G-S16 (w4-menus CAPTURE-REQUESTS CR-01..CR-11) are all open; return to title not verified",
        ],
        rules=[
            "no pixel or heavy CPU job without an explicit coordinator grant; one launch attempt per grant via tools/s45_grant_launch.ps1 "
            "(deadline checked at spawn, decline writes a receipt, never retry without a fresh grant)",
            "frozen lanes, J-H/J-I/J-K/J-K2 outputs and failed evidence are read-only; new outputs only in new run folders",
            "R5 fill is the pack composer's job (root decision msg_80aa44e1); primary = R1 + conn-only (bound 1e9), s/2 is a diagnostic",
            "review sheets are ATLAS SIMULATIONS (9 px/texel), not screen captures; no look acceptance claims",
            "3090 Ti user-reserved; no GPU / game / ComfyUI",
        ])
    (rd / "HANDOFF-UI.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    md = [f"# Menu/HUD handoff s45 -> claude-einhander-ui (`{stamp}`)", "",
          f"**Status:** {out['status']}. **Acceptance:** {out['acceptance']}.", "", "## Latest results", ""]
    md += [f"- **{r['id']}** `{r['path']}` (`{r['sha256'][:12]}`): {r['verdict']}" for r in results]
    md += ["", "## Pending request", "", f"- {out['pending_request']['id']} ({out['pending_request']['msg']}): `{out['pending_request']['tool']}` "
           f"{out['pending_request']['note']}", "", "## Remaining", ""] + [f"- {x}" for x in out["remaining"]]
    md += ["", "## Rules", ""] + [f"- {x}" for x in out["rules"]]
    md += ["", "## Tool pins", ""] + [f"- `{t}` `{h}`" for t, h in tools.items()]
    (rd / "HANDOFF-UI.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("packet", rd, sha(rd / "HANDOFF-UI.json"))


if __name__ == "__main__":
    main()
