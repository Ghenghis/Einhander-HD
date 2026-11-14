#!/usr/bin/env python3
"""Freeze one renderer-v61-classmip version into frozen/<name>/ (exist_ok=False; never overwrites) with SHA256SUMS
and READY.json (claude-einhander). Copies docs, sources, evidence, the passing host run, the built (NOT run) GL
selftest, and optional extra run folders. Refuses a host run whose verdict is not "pass".
Usage: freeze_version.py NAME HOST_RUN SELFTEST_RUN [--extra DIR ...] [--supersedes TEXT] [--limit TEXT ...]"""
import argparse
import datetime
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = ["DESIGN-V4.md", "DESIGN-V3.md", "DESIGN-V2.md", "DESIGN.md", "FAILED-RUNS.md"]
SRC = ["hd_class_mips.inc", "make_patch.py", "run_host.py", "test_hd_class_mips.c", "hdcm_tool.c", "glue_harness.c",
       "gl_selftest_classmips.c", "build_selftest.py", "ab_targets.py", "freeze_version.py"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("host_run")
    ap.add_argument("selftest_run")
    ap.add_argument("--extra", action="append", default=[])
    ap.add_argument("--supersedes", default="")
    ap.add_argument("--limit", action="append", default=[])
    a = ap.parse_args()
    hrd = HERE / "runs" / a.host_run
    hr = json.loads((hrd / "result.json").read_text(encoding="utf-8"))
    assert hr.get("verdict") == "pass", "only a passing host run is frozen"
    F = HERE / "frozen" / a.name
    F.mkdir(parents=True, exist_ok=False)
    (F / "docs").mkdir()
    (F / "src").mkdir()
    for f in DOCS:
        if (HERE / f).exists():
            shutil.copy2(HERE / f, F / "docs" / f)
    for f in ("SUPERSEDED.md", "REJECTED-PERFORMANCE.md"):
        if (HERE / "frozen" / f).exists():
            shutil.copy2(HERE / "frozen" / f, F / "docs" / f)
    for f in SRC:
        shutil.copy2(HERE / f, F / "src" / f)
    shutil.copytree(HERE / "evidence", F / "evidence")
    shutil.copytree(hrd, F / "host-run" / a.host_run)
    shutil.copytree(HERE / "selftest" / a.selftest_run, F / "selftest" / a.selftest_run)
    for e in a.extra:
        src = HERE / e
        shutil.copytree(src, F / "extra" / src.name)
    sums = [f"{sha(p)}  {p.relative_to(F).as_posix()}" for p in sorted(x for x in F.rglob("*") if x.is_file())]
    (F / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    s = hr["steps"]
    patch = next(v for k, v in s.items() if k.endswith("-patch"))
    comp = next(v for k, v in s.items() if k.endswith("-compile"))
    glue = next((v for k, v in s.items() if k.endswith("-glue")), {})
    side = next((v for k, v in s.items() if k.endswith("-sidecars")), {})
    st = json.loads((HERE / "selftest" / a.selftest_run / "build.json").read_text(encoding="utf-8"))
    ready = dict(
        name=a.name, owner="claude-einhander", supersedes=a.supersedes,
        frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        status="PRIVATE; default OFF; patched COPY of the frozen v61 renderer only; NOT linked, NOT run, NO GPU used by "
               "claude; root owns link/live/GPU/GitHub",
        v61_input=dict(path=patch["v61_src"], sha256=patch["v61_sha256"]),
        patched_tu=dict(path=f"host-run/{a.host_run}/patched/gpu_gl_renderer.c", sha256=patch["patched_sha256"],
                        lines=patch["lines_out"], insertions=[r["name"] for r in patch["receipts"]],
                        include_sha256=sha(F / "host-run" / a.host_run / "patched/hd_class_mips.inc"),
                        obj_sha256=comp["patched"]["obj_sha256"], control_obj_sha256=comp["control"]["obj_sha256"],
                        new_warning_kinds=comp["new_warning_kinds"], builder_in_runtime_tu=comp.get("builder_in_patched_tu")),
        admission=dict(index=side.get("index"), bytes=side.get("index_bytes"), negatives=side.get("negatives")),
        host=dict(run=a.host_run, verdict=hr["verdict"], checks=hr["checks"], result_sha256=sha(hrd / "result.json"),
                  fixture_checks=s["1-fixtures"]["checks"], mutants=s["2-mutants"]["caught"],
                  glue_cases=[dict(mode=c["mode"], control=c["control"], rc=c["rc"], checks=c["checks"], timing=c["timing"])
                              for c in glue.get("cases", [])],
                  glue_mutants=glue.get("glue_mutants_caught"),
                  tool_timing_ms={x["key"]: dict(preload_verify=x["preload_verify_ms"], draw_admit=x["draw_thread_admit_ms"])
                                  for x in side.get("sidecars", []) if x.get("written")}),
        selftest=dict(run=a.selftest_run, exe=f"selftest/{a.selftest_run}/gl_selftest_classmips.exe",
                      sha256=sha(F / "selftest" / a.selftest_run / "gl_selftest_classmips.exe"), compile_rc=st["compile_rc"],
                      readme=f"selftest/{a.selftest_run}/README-ROOT.md",
                      run_by="root on GPU only after the user explicitly returns the 3090; NOT run by claude"),
        known_limits=a.limit, failed_runs="docs/FAILED-RUNS.md - every failure kept in place",
        sha256sums=sha(F / "SHA256SUMS.txt"), files=len(sums))
    (F / "READY.json").write_text(json.dumps(ready, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(dict(name=a.name, files=len(sums), sha256sums=ready["sha256sums"], ready_sha256=sha(F / "READY.json"),
                          patched=patch["patched_sha256"], obj=comp["patched"]["obj_sha256"], selftest=ready["selftest"]["sha256"]),
                     indent=1))


if __name__ == "__main__":
    main()
