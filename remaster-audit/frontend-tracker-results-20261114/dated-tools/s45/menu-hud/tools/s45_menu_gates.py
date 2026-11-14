#!/usr/bin/env python3
"""s45 menu/HUD (EIN-MENU-HUD-20261114): join of the EXISTING w4-menus acceptance gates (LEDGER.md "Per-state ledger",
gates G-S1..G-S16, capture requests CR-01..CR-11) with the s45 state register, to order the J-L primary-policy audit by gate.
It restates no gate. Per ledger state section it extracts the keys named, the gate ids and text, the
"Integrated"/"Observed"/"Defects" lines (verbatim, truncated), the CR rows naming those gates, and from the register the
frozen folders that carry each key. Folders are then ranked by how many gates depend on them -> J-L batch order.
Light, read-only (text/JSON). One CPU (not 13/15), below normal. Writes ONLY s45/menu-hud/gates/<UTC>/."""
import collections
import datetime
import hashlib
import json
import re
from pathlib import Path

CA = Path("C:/github/Einhander/remaster-audit/comfy-authoring")
S45 = Path("C:/github/Einhander/remaster-audit/parallel-stages-20261114/s45")
LEDGER = CA / "w4-menus/LEDGER.md"
CRS = CA / "w4-menus/CAPTURE-REQUESTS.md"
REG = S45 / "menu-hud/state-register/20261114T152157Z/register.json"
KEY = re.compile(r"\b([0-9A-F]{8}-[0-9A-F]{8})\b")
GATE = re.compile(r"G-S\d+")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    import psutil
    me = psutil.Process()
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    me.cpu_affinity([c for c in me.cpu_affinity() if c not in (13, 15)][:1])
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rd = S45 / "menu-hud/gates" / stamp
    rd.mkdir(parents=True, exist_ok=False)
    led = LEDGER.read_text(encoding="utf-8")
    part = led[led.index("## Per-state ledger"):]
    nxt = re.search(r"\n## (?!#)", part[5:])
    part = part[:nxt.start() + 5] if nxt else part
    secs = re.split(r"\n(?=### )", part)[1:]
    reg = json.loads(REG.read_text(encoding="utf-8"))
    by_key = {}
    for st in reg["states"]:
        for r in st["rows"]:
            by_key[r["key"]] = r
    cr_rows = {}
    for line in CRS.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\| (CR-\d+) \| ([^|]*)\|", line)
        if m:
            cr_rows[m.group(1)] = dict(state=m.group(2).strip(), gates=sorted(set(GATE.findall(line))), keys=sorted(set(KEY.findall(line))))
    states, folder_gates = [], collections.defaultdict(set)
    for sec in secs:
        title = sec.splitlines()[0].lstrip("# ").strip()
        keys = sorted(set(KEY.findall(sec)))
        gates = sorted(set(GATE.findall(sec)), key=lambda g: int(g[3:]))

        def grab(label):
            m = re.search(r"^- " + label + r"[^\n]*(?:\n  [^\n]*)*", sec, re.M)
            return re.sub(r"\s+", " ", m.group(0))[2:400] if m else None
        rows = []
        for k in keys:
            r = by_key.get(k, {})
            for f in r.get("delivered_in", []):
                for g in gates:
                    folder_gates[f].add(g)
            rows.append(dict(key=k, delivered_in=r.get("delivered_in", []), legacy_v13=r.get("legacy_v13_pack"),
                             gl_submitted_live=r.get("gl_submitted_live"), in_register=bool(r)))
        crs = sorted(c for c, v in cr_rows.items() if set(v["gates"]) & set(gates))
        states.append(dict(state=title, gates=gates, capture_requests=crs, keys=rows,
                           keys_with_frozen_candidate=sum(1 for r in rows if r["delivered_in"]),
                           integrated_line=grab("Integrated"), observed_line=grab("Observed"), defects_line=grab("Defects"),
                           gate_text={g: re.sub(r"\s+", " ", m.group(0))[:500] for g in gates
                                      for m in [re.search(r"\*\*Gate " + g + r":\*\*[^\n]*(?:\n  [^\n]*)*", sec)] if m},
                           class_policy_status="pending J-L (proto-v2b primary not yet run on these folders)"))
    order = sorted(folder_gates.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    plan = [dict(folder=f, gates=sorted(g, key=lambda x: int(x[3:]))) for f, g in order]
    out = dict(run=stamp, owner="claude-einhander-s45", task="EIN-MENU-HUD-20261114",
               note="join only: gates/CRs are w4-menus' own; delivered = frozen candidate (not installed / not accepted)",
               inputs={str(LEDGER): sha(LEDGER), str(CRS): sha(CRS), str(REG): sha(REG)}, tool_sha256=sha(Path(__file__)),
               capture_requests=cr_rows, states=states, j_l_folder_order=plan)
    (rd / "gates.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    md = [f"# Menu / HUD gates join `{stamp}` (s45)", "",
          "Gates and capture requests are w4-menus' own (`comfy-authoring/w4-menus/LEDGER.md`, `CAPTURE-REQUESTS.md`).",
          "This only joins them with the s45 register and orders the J-L class-policy audit. Delivered = frozen candidate.", "",
          "| ledger state | gates | capture requests | keys | with frozen candidate | class policy |", "|---|---|---|---|---|---|"]
    for s in states:
        md.append(f"| {s['state']} | {', '.join(s['gates']) or '-'} | {', '.join(s['capture_requests']) or '-'} | {len(s['keys'])} | "
                  f"{s['keys_with_frozen_candidate']} | pending J-L |")
    md += ["", "## J-L audit order (frozen folders by number of dependent gates)", ""]
    md += [f"- `{p['folder']}`: {', '.join(p['gates'])}" for p in plan]
    (rd / "GATES.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    for s in states:
        print(f"{s['state'][:50]:50} gates {','.join(s['gates']):14} CR {','.join(s['capture_requests']):14} keys {len(s['keys']):3} cand {s['keys_with_frozen_candidate']}")
    print("J-L order:", [(p["folder"], len(p["gates"])) for p in plan[:14]])
    print("run", stamp, sha(rd / "gates.json"))


if __name__ == "__main__":
    main()
