"""One real OS scheduling readback for the separately reviewed normal-game Job."""
import datetime as dt
import json
import sys
from pathlib import Path
import psutil

out = Path(sys.argv[1]).resolve()
base = Path(__file__).resolve().parent
if not out.is_relative_to(base) or out.exists():
    raise SystemExit("Output must be new and inside this owned source packet")
me = psutil.Process()
observed = {
    "utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    "pid": me.pid,
    "creation_time": me.create_time(),
    "cpu_affinity": sorted(me.cpu_affinity()),
    "priority": int(me.nice()),
    "scope": "Scheduling readback only; no GPU, game or UI",
}
observed["ok"] = observed["cpu_affinity"] == list(range(16)) and observed["priority"] == 32
with out.open("x", encoding="utf-8") as f:
    json.dump(observed, f, indent=2)
    f.write("\n")
print(json.dumps(observed), flush=True)
raise SystemExit(0 if observed["ok"] else 1)
