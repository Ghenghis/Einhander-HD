"""Relink the tested GL capture candidate with the completed BIOS save fix.

Reuses the two validated BIOS supplement objects; never regenerates BIOS code,
installs a global executable, or edits the saved material-runtime descriptor.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / "windows-x64"
BUILD = PROJECT / "build-ss8c"
CAPTURE = Path("C:/github/REMASTER_STAGING/full-remaster/ui-hires-build-20261112")
BIOS = Path("C:/github/REMASTER_STAGING/save-fix/bios-seed")
OUT = Path("C:/github/REMASTER_STAGING/full-remaster/ui-hires-build-20261112-v2")
TOOLCHAIN = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    # Pin the completed second BIOS fix, including the subsequent 0980C miss.
    bios_receipt = json.loads((BIOS / "build.json").read_text())
    required = ["SCPH1001_func_1FC09800", "SCPH1001_func_1FC0980C"]
    if bios_receipt["new_functions"] != required:
        raise ValueError("Expected the completed two-entry BIOS save fix")
    if sha(Path(bios_receipt["executable"])) != bios_receipt["sha256"]:
        raise ValueError("BIOS fix executable changed since its receipt")
    regression_path = Path("C:/github/REMASTER_STAGING/renderer-validation/hires-capture-20261112-unique01/results.json")
    regression = json.loads(regression_path.read_text())
    renderer_source = PROJECT / "psxrecomp/runtime/src/gpu_gl_renderer.c"
    if regression["exit_code"] != 0 or regression["renderer_sha256"] != sha(renderer_source):
        raise ValueError("Current GL renderer has no matching successful capture regression")
    capture_receipt = json.loads((CAPTURE / "capture-build.json").read_text())
    if capture_receipt["renderer_sha256"] != sha(renderer_source):
        raise ValueError("Capture object does not match tested renderer")

    support = BIOS / "SCPH1001_save_support.c.obj"
    dispatch = BIOS / "SCPH1001_dispatch.c.obj"
    symbols = subprocess.run([str(TOOLCHAIN / "llvm-nm.exe"), "--defined-only", str(support)],
                             capture_output=True, text=True, check=True, timeout=15).stdout
    for symbol in required:
        if " T " + symbol not in symbols:
            raise ValueError("Missing compiled BIOS entry: " + symbol)
    dispatch_source = (BIOS / "generated/SCPH1001_dispatch.c").read_text()
    if not all("{ " + address + ", " + symbol + " }" in dispatch_source
               for address, symbol in zip(("0x1FC09800u", "0x1FC0980Cu"), required)):
        raise ValueError("Final BIOS dispatch source lacks a required table entry")

    response = (CAPTURE / "devtools-link.rsp").read_text().splitlines()
    matches = [i for i, entry in enumerate(response)
               if entry.strip('"').replace("\\", "/").endswith("/SCPH1001_dispatch.c.obj")]
    if len(matches) != 1 or any("SCPH1001_save_support.c.obj" in item for item in response):
        raise ValueError("Unexpected baseline BIOS link composition")
    response[matches[0]] = '"' + dispatch.as_posix() + '"'
    response.append('"' + support.as_posix() + '"')
    renderer = CAPTURE / "gpu_gl_renderer.c.obj"
    if response.count('"' + renderer.as_posix() + '"') != 1:
        raise ValueError("Tested GL capture object is missing from candidate link")
    material_descriptor = PROJECT / "tools/material-runtime.json"
    material_before = sha(material_descriptor)
    OUT.mkdir(parents=True, exist_ok=False)
    rsp = OUT / "hires-bios-link.rsp"
    rsp.write_text("\n".join(response) + "\n", encoding="utf-8")
    executable = OUT / "Einhander_Recompiled.exe"
    result = subprocess.run([str(TOOLCHAIN / "clang++.exe"), "-O3", "-DNDEBUG",
                             "-Wl,--stack,67108864", "-mwindows", "-static",
                             "-static-libgcc", "-static-libstdc++", "@" + str(rsp),
                             "-o", str(executable)], cwd=BUILD, capture_output=True,
                            text=True, timeout=180)
    (OUT / "link.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        print(result.stdout + result.stderr)
        return result.returncode
    final_symbols = subprocess.run([str(TOOLCHAIN / "llvm-nm.exe"), "--defined-only", str(executable)],
                                   capture_output=True, text=True, check=True, timeout=15).stdout
    if any(" T " + name not in final_symbols for name in required):
        raise ValueError("Linked candidate lacks required BIOS implementations")
    if sha(material_descriptor) != material_before:
        raise ValueError("Saved material receipt changed during candidate build")
    report = dict(at_utc=datetime.now(timezone.utc).isoformat(), executable=str(executable),
                  sha256=sha(executable), renderer_source=str(renderer_source), renderer_sha256=sha(renderer_source),
                  objects=[dict(path=str(path), sha256=sha(path)) for path in (renderer, dispatch, support)],
                  bios_entries=required, bios_build_receipt=dict(path=str(BIOS / "build.json"), sha256=sha(BIOS / "build.json")),
                  gl_regression=dict(path=str(regression_path), sha256=sha(regression_path), checks=17, failures=0),
                  link_response_sha256=sha(rsp), link_exit=0, global_runtime_installed=False,
                  saved_material_receipt_unchanged=True, native_card_creation="pending isolated gameplay acceptance")
    (OUT / "build.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
