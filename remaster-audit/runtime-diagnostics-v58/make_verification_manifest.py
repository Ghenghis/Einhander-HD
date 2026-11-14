#!/usr/bin/env python3
"""Bind the frozen v58 frame-phase-ring package to the exact texts and reports that checked it (claude-einhander).
Documentation only: hashes files and cross-checks them; it reruns no test, compiler or game.
Writes verification-manifest.json."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = Path("C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112")
BUILD = E / "sampling-build-v58-frame-phases"
R1 = E / "display58-phases-pbo-on-r1/hd-on_rewind-on"
BEGIN, END = "/* FRAME_PHASE_RING BEGIN", "/* Present-classification ring"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def ref(p, **extra):
    p = Path(p)
    return dict(path=p.as_posix(), sha256=sha(p), bytes=p.stat().st_size, **extra)


def main():
    checks, m = {}, {}
    receipt = json.loads((HERE / "patch-receipt.json").read_text(encoding="utf-8"))
    m["frozen_sources"] = {}
    for name in ("main.cpp", "gpu_gl_renderer.c", "debug_server.c", "frame_phase_ring.h"):
        r = receipt[name]
        new = ref(HERE / "new" / name)
        row = dict(new=new, receipt_new_sha256=r["new_sha256"])
        checks[f"{name}: new file == receipt"] = new["sha256"] == r["new_sha256"]
        if "base" in r:
            row["base"] = ref(r["base"])
            checks[f"{name}: base file == receipt"] = row["base"]["sha256"] == r["base_sha256"]
            row["diff"] = ref(HERE / "diffs" / (name + ".diff"))
            checks[f"{name}: diff == receipt"] = row["diff"]["sha256"] == r["diff_sha256"]
        built = BUILD / name
        if built.exists():
            row["root_build_copy"] = ref(built)
            checks[f"{name}: root v58 build copy == frozen"] = row["root_build_copy"]["sha256"] == new["sha256"]
        m["frozen_sources"][name] = row
    build_json = (BUILD / "build.json").read_text(encoding="utf-8")
    checks["root build.json lists all 4 frozen hashes"] = all(
        receipt[n]["new_sha256"] in build_json for n in ("main.cpp", "gpu_gl_renderer.c", "debug_server.c", "frame_phase_ring.h"))
    m["root_build"] = dict(build_json=ref(BUILD / "build.json"), executable=ref(BUILD / "Einhander_Recompiled.exe"),
                           first_build_rejected_dir=(BUILD / "first-build-rejected").as_posix())
    checks["root executable is c2c386bd"] = m["root_build"]["executable"]["sha256"].startswith("c2c386bd")
    m["receipts"] = dict(r2=ref(HERE / "patch-receipt.json"), r1_collision=ref(HERE / "patch-receipt-r1-collision.json",
                         note="r1 debug_server.c declared s_fp_ring, colliding with the existing fingerprint ring"))

    src = (HERE / "new" / "debug_server.c").read_text(encoding="utf-8").replace("\r\n", "\n")
    block = src[src.index(BEGIN):src.index(END)]
    m["host_test"] = dict(
        extracted_block=dict(sha256=hashlib.sha256(block.encode("utf-8")).hexdigest(), chars=len(block),
                             from_file="new/debug_server.c", begin_marker=BEGIN, end_marker=END),
        compiled_copies={})
    for tag in ("actual-cap8", "actual-defaultcap"):
        inc = HERE / "work" / tag / "ring_extracted.inc"
        if inc.exists():
            m["host_test"]["compiled_copies"][tag] = ref(inc)
            checks[f"host test {tag} compiled the frozen block"] = inc.read_text(encoding="utf-8") == block
    m["host_test"].update(
        test_driver=ref(HERE / "test_frame_phase_ring.c"), runner=ref(HERE / "run_host_test.py",
        note="contains the mutant list and the EXPECTED_DECLS symbol fixture"), derive=ref(HERE / "derive_phases.py"),
        report=ref(HERE / "host-test.json"),
        preserved_failed_report=ref(HERE / "host-test-r2-scanner-false-positive.json",
                                    note="scanner counted locals/call sites as declarations; superseded, kept unchanged"))
    ht = json.loads((HERE / "host-test.json").read_text(encoding="utf-8"))
    checks["host-test.json passed"] = ht["passed"] is True
    checks["host-test scan control detects r1 s_fp_ring"] = ht["symbol_scan_control_detects_s_fp_ring"] is True
    m["syntax_check"] = dict(
        script=ref(HERE / "syntax_check.py", note="current version; adds an optional TU filter"),
        r2_report=ref(HERE / "syntax-check.json", scope="debug_server.c only: the one TU changed r1 -> r2"),
        r1_report=ref(HERE / "syntax-check-r1-collision.json",
                      scope="all 3 TUs at r1; main.cpp and gpu_gl_renderer.c byte-identical in r2 (clean); "
                            "its debug_server.c failure is the s_fp_ring collision",
                      produced_by_script_sha256="5954435bf8d8ae9c5c2b4ab559c3e6c333906a4e5c1caab7f045af12fc2773ec"))
    s2 = json.loads((HERE / "syntax-check.json").read_text(encoding="utf-8"))
    checks["r2 syntax debug_server.c clean"] = s2["passed"] is True and s2["files"]["debug_server.c"]["patched_exit"] == 0
    s1 = json.loads((HERE / "syntax-check-r1-collision.json").read_text(encoding="utf-8"))
    checks["r1 syntax main/renderer clean"] = all(s1["files"][n]["patched_exit"] == 0 and not s1["files"][n]["new_build_diagnostics"]
                                                  and not s1["files"][n]["new_wall_diagnostics"] for n in ("main.cpp", "gpu_gl_renderer.c"))
    old = json.loads((HERE / "patch-receipt-r1-collision.json").read_text(encoding="utf-8"))
    checks["main/renderer/header unchanged r1 -> r2"] = all(old[n]["new_sha256"] == receipt[n]["new_sha256"]
                                                            for n in ("main.cpp", "gpu_gl_renderer.c", "frame_phase_ring.h"))
    m["generator"] = ref(HERE / "make_frame_phase_patch.py")
    m["handoff_doc"] = (HERE / "HANDOFF.md").as_posix()
    if (R1 / "world-flypast-proof.json").exists():
        p = json.loads((R1 / "world-flypast-proof.json").read_text(encoding="utf-8"))
        m["live_attempts"] = [dict(run="display58-phases-pbo-on-r1", proof=ref(R1 / "world-flypast-proof.json"),
                                   verdict="REJECTED by the require_foreground focus gate; no performance verdict",
                                   errors=p["errors"], timed_observations=len(p["observations"]),
                                   started_utc=p["started_at_utc"], ended_utc=p["ended_at_utc"],
                                   port_closed=p.get("close", {}).get("port_closed"),
                                   title_phase_reply={k: v for k, v in p["phase_at_title"].items() if k != "rows"})]
    m["documentation_corrections"] = [
        "last_open may be 0 or 1: the r1 title reply had last_open 0, because the debug server also answers outside "
        "an open vblank cycle. Consumers exclude any open row; do not require last_open == 1. The frozen header and "
        "handler comments say '1 is expected', which overstates this; source is unchanged to keep the frozen hashes."]
    m["checks"] = checks
    m["all_checks_pass"] = all(checks.values())
    m["scope"] = "Hash binding and cross-checks only. No test, compiler or game was rerun to make this manifest."
    (HERE / "verification-manifest.json").write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(all_checks_pass=m["all_checks_pass"], failed=[k for k, v in checks.items() if not v]), indent=1))


if __name__ == "__main__":
    main()
