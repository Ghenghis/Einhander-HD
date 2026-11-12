"""Compile the combined GL capture/title admission renderer into a private build.

Retains the completed two-entry BIOS save fix and never updates shared runtime
descriptors. The required real-GL capture report must match the current source.
"""
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "windows-x64"
BUILD = PROJECT / "build-ss8c"
BASELINE = Path("C:/github/REMASTER_STAGING/full-remaster/ui-hires-build-20261112-v2")
OUT = Path("C:/github/REMASTER_STAGING/full-remaster/ui-hires-build-20261112-v3")
TOOLS = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def windows_args(command):
    count = ctypes.c_int()
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
    values = parse(command, ctypes.byref(count))
    try:
        return [values[i] for i in range(count.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(values)


def run(arguments, label):
    result = subprocess.run(arguments, cwd=BUILD, capture_output=True, text=True,
                            timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
    (OUT / (label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    print(label, "exit", result.returncode, flush=True)
    if result.returncode:
        print(result.stdout + result.stderr)
        raise SystemExit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-report", required=True, type=Path)
    parser.add_argument("--title-report", required=True, type=Path)
    args = parser.parse_args()
    source = PROJECT / "psxrecomp/runtime/src/gpu_gl_renderer.c"
    source_digest = sha(source)
    capture = json.loads(args.capture_report.read_text())
    if capture.get("exit_code") != 0 or capture.get("renderer_sha256") != source_digest:
        raise ValueError("A successful GL capture regression for the current renderer is required")
    if not args.title_report.is_file():
        raise ValueError("Title admission regression receipt is required")
    title = json.loads(args.title_report.read_text())
    if (title.get("source_sha256") != source_digest or not title.get("tests") or
            any(row.get("exit") != 0 for row in title["tests"])):
        raise ValueError("Title admission regression receipt reports a failure")
    helper = PROJECT / "psxrecomp/runtime/src/hd_visible_uv.h"
    helper_digest = sha(helper)
    baseline = json.loads((BASELINE / "build.json").read_text())
    if baseline.get("bios_entries") != ["SCPH1001_func_1FC09800", "SCPH1001_func_1FC0980C"]:
        raise ValueError("Completed BIOS save support is missing")
    for row in baseline["objects"]:
        if sha(row["path"]) != row["sha256"]:
            raise ValueError("Baseline object changed: " + row["path"])
    material = PROJECT / "tools/material-runtime.json"
    material_before = sha(material)
    OUT.mkdir(parents=True, exist_ok=False)
    original_command = Path("C:/github/REMASTER_STAGING/stage01_city/evidence/renderer-build-command.txt").read_text()
    compile_args = windows_args(original_command)
    if Path(compile_args[0]).name.lower() == "ccache.exe":
        compile_args = compile_args[1:]
    compile_args = [value.replace("D:/Games/Einhander/windows-x64/", PROJECT.as_posix() + "/") for value in compile_args]
    renderer = OUT / "gpu_gl_renderer.c.obj"
    compile_args[compile_args.index("-o") + 1] = str(renderer)
    compile_args[compile_args.index("-MF") + 1] = str(renderer) + ".d"
    compile_args[-1] = str(source)
    run(compile_args, "compile-renderer")
    if sha(source) != source_digest or sha(helper) != helper_digest:
        raise ValueError("Renderer changed during compile")
    response = (BASELINE / "hires-bios-link.rsp").read_text().splitlines()
    matching = [i for i, value in enumerate(response)
                if value.strip('"').replace("\\", "/").endswith("/gpu_gl_renderer.c.obj")]
    if len(matching) != 1:
        raise ValueError("Expected one renderer object in BIOS-fixed baseline link")
    response[matching[0]] = '"' + renderer.as_posix() + '"'
    rsp = OUT / "hires-title-bios-link.rsp"
    rsp.write_text("\n".join(response) + "\n", encoding="utf-8")
    executable = OUT / "Einhander_Recompiled.exe"
    run([str(TOOLS / "clang++.exe"), "-O3", "-DNDEBUG", "-Wl,--stack,67108864", "-mwindows", "-static",
         "-static-libgcc", "-static-libstdc++", "@" + str(rsp), "-o", str(executable)], "link")
    if sha(material) != material_before:
        raise ValueError("Saved material runtime descriptor changed during build")
    report = dict(at_utc=datetime.now(timezone.utc).isoformat(), executable=str(executable), sha256=sha(executable),
                  renderer_source=str(source), renderer_sha256=source_digest,
                  visible_uv_header=dict(path=str(helper), sha256=helper_digest),
                  objects=[dict(path=str(renderer), sha256=sha(renderer))] + [row for row in baseline["objects"] if "SCPH1001" in row["path"]],
                  bios_entries=baseline["bios_entries"],
                  baseline_build_receipt=dict(path=str(BASELINE / "build.json"), sha256=sha(BASELINE / "build.json")),
                  capture_regression=dict(path=str(args.capture_report.resolve()), sha256=sha(args.capture_report)),
                  title_regression=dict(path=str(args.title_report.resolve()), sha256=sha(args.title_report)),
                  link_exit=0, link_response_sha256=sha(rsp), global_runtime_installed=False,
                  saved_material_receipt_unchanged=True, gameplay_acceptance="pending isolated candidate launch")
    (OUT / "build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
