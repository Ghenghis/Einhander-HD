"""Verify the composed candidate with the actual HD library and hidden GL.

This reads the candidate/base assets and writes only its own probe artifacts.
No game, bridge, installation or visible helper window is started.
"""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "windows-x64/psxrecomp/runtime"
STAGE = ROOT / "remaster-audit/dev-center-evidence/greif-native-admission-20261112"
PACK = STAGE / "composed-pack"
OUT = ROOT / "remaster-audit/verification/greif-native-admission"
COMPILER = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    provenance = json.loads((STAGE / "manifest.json").read_bytes())
    composition = json.loads((PACK / "composition.json").read_bytes())
    base_links = 0
    for row in composition["files"]:
        target = PACK / "einhander-texture-replacements" / row["name"]
        if "bytes" in row and target.stat().st_size != row["bytes"]:
            raise ValueError("Composed asset size mismatch: " + row["name"])
        if row["origin"] == "immutable base hardlink":
            if not target.samefile(Path(row["path"])):
                raise ValueError("Base link identity mismatch: " + row["name"])
            base_links += 1
    for row in provenance["files"]:
        target = PACK / "einhander-texture-replacements" / (row["key"] + ".png")
        if sha(target) != row["png_sha256"]:
            raise ValueError("Candidate PNG hash mismatch: " + row["key"])
    if len(composition["files"]) != 1024 or base_links != 964 or len(provenance["files"]) != 60:
        raise ValueError("Unexpected composed candidate accounting")
    OUT.mkdir(parents=True, exist_ok=True)
    keys = OUT / "expected-keys.txt"
    keys.write_text("\n".join(row["key"] for row in provenance["files"]) + "\n", encoding="ascii")
    executable = OUT / "test_greif_native_admission.exe"
    source = ROOT / "remaster-audit/test_greif_native_admission.cpp"
    arguments = [str(COMPILER), "-std=c++17", "-O2", "-static", "-I" + str(RUNTIME / "include"),
                 str(source), str(RUNTIME / "src/hd_texture_pack.cpp"),
                 "-lopengl32", "-lgdi32", "-luser32", "-o", str(executable)]
    compiled = subprocess.run(arguments, capture_output=True, text=True, timeout=60)
    (OUT / "compile.log").write_text(compiled.stdout + compiled.stderr, encoding="utf-8")
    if compiled.returncode:
        print(compiled.stdout + compiled.stderr)
        return compiled.returncode
    tested = subprocess.run([str(executable), str(PACK), str(keys), str(STAGE / "sources")],
                            capture_output=True, text=True, timeout=35)
    (OUT / "result.log").write_text(tested.stdout + tested.stderr, encoding="utf-8")
    report = json.loads(tested.stdout)
    report.update(compile_exit=compiled.returncode, test_exit=tested.returncode,
        base_links_independently_verified=base_links, greif_png_hashes_verified=60,
        composition_sha256=sha(PACK / "composition.json"), provenance_sha256=sha(STAGE / "manifest.json"),
        executable_sha256=sha(executable), scope="Actual HD pack index, async PNG decoder, exact source1555 RGB/alpha/STP comparison and hidden OpenGL upload/readback; no game draw or visual quality claim",
        sources=[dict(path=str(path), sha256=sha(path)) for path in
                 [source, RUNTIME / "src/hd_texture_pack.cpp", RUNTIME / "include/hd_texture_pack.h", Path(__file__)]])
    (OUT / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key not in ("files", "sources")}, indent=2))
    return tested.returncode


if __name__ == "__main__":
    raise SystemExit(main())
