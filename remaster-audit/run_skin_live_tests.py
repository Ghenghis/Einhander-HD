"""Native tests for the exact live renderer API and debug command handler.

The exported API block is compiled against CPU renderer-state fixtures. This
does not create a commercial game process or a graphics context.
"""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "windows-x64/psxrecomp/runtime"
OUT = ROOT / "remaster-audit/verification/material-live"
COMPILER = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    renderer = RUNTIME / "src/gpu_gl_renderer.c"
    text = renderer.read_text(encoding="utf-8")
    api = text[text.index("int gl_renderer_skin_profile_count(void)"):text.index("static GLuint hd_tex_object")]
    (OUT / "hd_skin_live_renderer_api.h").write_text(api, encoding="utf-8")
    arguments = [str(COMPILER), "-O2", "-static", "-I" + str(OUT), "-I" + str(RUNTIME / "src"),
                 "-I" + str(RUNTIME / "include"), str(ROOT / "remaster-audit/test_skin_live_command.cpp"),
                 "-o", str(OUT / "test_skin_live_command.exe")]
    compiled = subprocess.run(arguments, capture_output=True, text=True, timeout=60)
    (OUT / "compile.log").write_text(compiled.stdout + compiled.stderr, encoding="utf-8")
    if compiled.returncode:
        print(compiled.stdout + compiled.stderr)
        return compiled.returncode
    tested = subprocess.run([str(OUT / "test_skin_live_command.exe")], capture_output=True, text=True, timeout=30)
    (OUT / "result.log").write_text(tested.stdout + tested.stderr, encoding="utf-8")
    if tested.stdout.strip().startswith("{"):
        report = json.loads(tested.stdout)
        assert report["sample_get"]["ready"] and not report["sample_get"]["applied"]
        assert report["sample_set"]["applied"] and report["sample_set"]["generation"] == 1
        assert report["sample_set"]["player"]["profile"] == "neon-circuit"
        assert report["sample_set"]["enemy"]["profile"] == "crimson-regalia"
        assert len(report["sample_get"]["supported_profiles"]) == report["profiles_including_stock"]
        assert report["sample_maximum_set"]["diagnostic_max_keys_per_channel"] == 128
        for channel in ("player", "enemy"):
            maximum = report["sample_maximum_set"][channel]
            assert maximum["diagnostic_scope"] and maximum["key_count"] == 128
            assert len(maximum["keys"].split(",")) == 128 and len(maximum["keys"]) == 2303
        sources = [renderer, RUNTIME / "src/debug_server.c", RUNTIME / "src/hd_skin_live.h",
                   RUNTIME / "src/hd_skin_live_debug.h", RUNTIME / "include/gpu_gl_renderer.h"]
        report.update(compile_exit=compiled.returncode, test_exit=tested.returncode,
                      scope="Exact exported API/handler with native CPU state fixtures; no game or GL context launched",
                      sources=[{"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sources])
        (OUT / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items() if key not in ("sample_get", "sample_set", "sample_maximum_set", "sources")}, indent=2))
    else:
        print(tested.stdout + tested.stderr)
    return tested.returncode


if __name__ == "__main__":
    raise SystemExit(main())
