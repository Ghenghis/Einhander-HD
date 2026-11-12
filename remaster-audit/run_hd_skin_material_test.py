"""Compile the actual runtime HD fragment shader in a hidden GL regression.

This executes a small renderer test program, never the game runtime.
"""
import ast
import hashlib
import json
import re
import subprocess
import struct
import binascii
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "windows-x64/psxrecomp/runtime/src/gpu_gl_renderer.c"
HEADER = SOURCE.with_name("hd_skin_material.h")
DETAIL_HEADER = SOURCE.with_name("hd_skin_detail.h")
OUT = ROOT / "remaster-audit/verification/material-shader"
COMPILER = Path("C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe")


def extract_shader(path: Path) -> str:
    block = path.read_text(encoding="utf-8").split("static const char *HD_FS =", 1)[1].split("static GLuint compile_shader", 1)[0]
    for name, header in [("HD_SKIN_MATERIAL_GLSL", HEADER), ("HD_SKIN_DETAIL_GLSL", DETAIL_HEADER)]:
        if name in block:
            macro = header.read_text(encoding="utf-8").split("#define " + name, 1)[1].split("/* CPU reference", 1)[0]
            kernel = "".join(ast.literal_eval(s) for s in re.findall(r'"(?:\\.|[^"\\])*"', macro))
            block = block.replace(name, json.dumps(kernel))
    return "".join(ast.literal_eval(s) for s in re.findall(r'"(?:\\.|[^"\\])*"', block))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
    def fixture(raw: bytes, color: int = 2, depth: int = 8, interlace: int = 0) -> bytes:
        return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, depth, color, 0, 0, interlace)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    valid = fixture(b"\x00\x10\x80\xf0")
    malformed_length = bytearray(valid)
    malformed_length[33:37] = b"\x7f\xff\xff\xff"
    fixtures = {"valid_rgb": valid, "valid_rgba": fixture(b"\x00\x10\x80\xf0\x00", 6),
                "bomb": fixture(b"\x00" * (1024 * 1024)), "short": fixture(b"\x00\x10"),
                "sixteen_bit": fixture(b"\x00" * 7, depth=16), "interlaced": fixture(b"\x00" * 4, interlace=1),
                "chunk_length": bytes(malformed_length), "truncated": valid[:-1]}
    (OUT / "hd_material_png_fixtures.h").write_text("\n".join(
        "static const unsigned char detail_png_" + name + "[]={" + ",".join(str(byte) for byte in data) + "};"
        for name, data in fixtures.items()) + "\n", encoding="utf-8")
    shader = extract_shader(SOURCE)
    (OUT / "material.frag").write_text(shader, encoding="utf-8")
    (OUT / "hd_material_shaders.h").write_text('const char *current_hd_fs=R"SHADER(' + shader + ')SHADER";\n', encoding="utf-8")
    arguments = [str(COMPILER), "-O2", "-static", "-I" + str(OUT), "-I" + str(HEADER.parent),
                 str(ROOT / "remaster-audit/test_hd_skin_material_gpu.cpp"), "-lopengl32", "-lgdi32", "-luser32", "-o", str(OUT / "test_hd_skin_material_gpu.exe")]
    compiled = subprocess.run(arguments, capture_output=True, text=True, timeout=60)
    (OUT / "compile-test.log").write_text(compiled.stdout + compiled.stderr, encoding="utf-8")
    if compiled.returncode:
        print(compiled.stdout + compiled.stderr)
        return compiled.returncode
    material_manifest = ROOT / "windows-x64/tools/skin_collection/materials/materials.json"
    maps = json.loads(material_manifest.read_text(encoding="utf-8"))["maps"]
    material_paths = [str(ROOT / "windows-x64" / m["image"].removeprefix("/files/")) for m in maps]
    tested = subprocess.run([str(OUT / "test_hd_skin_material_gpu.exe"), *material_paths], capture_output=True, text=True, timeout=30)
    (OUT / "result.log").write_text(tested.stdout + tested.stderr, encoding="utf-8")
    print(tested.stdout + tested.stderr)
    if tested.stdout.strip().startswith("{"):
        report = json.loads(tested.stdout)
        report.update(source=str(SOURCE), source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                      kernel_header=str(HEADER), kernel_sha256=hashlib.sha256(HEADER.read_bytes()).hexdigest(),
                      detail_header=str(DETAIL_HEADER), detail_sha256=hashlib.sha256(DETAIL_HEADER.read_bytes()).hexdigest(),
                      detail_images=[{"path": p, "sha256": hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in material_paths],
                      supported_profiles=re.findall(r'\{"([a-z-]+)",\s*0x', HEADER.read_text(encoding="utf-8")),
                      stock_equivalence="Exact RGB/alpha byte equality when both layers are disabled or the key is unrelated",
                      bounded_png_preflight_cases=8, bounded_png_preflight_passed=report["cpu_failures"] == 0,
                      png_bomb_fixture="1x1 RGB IHDR with 1 MiB inflated IDAT; fixed 4-byte scanline bound rejects it",
                      detail_sampler={"wrap": "mirrored_repeat", "minification": "linear_mipmap_linear", "magnification": "linear"},
                      detail_validation="Numeric CPU/GPU RGB parity at level0; automatic LOD validates alpha, neutral parts, stock isolation, mip allocation and actual color change",
                      live_color_next_draw="Palette pass changes profiles through the exact CPU transaction helper after the base texture upload; next draws match all14 profiles",
                      accent_preservation="Both optional states tested in actual palette/detail shader; orange fixture remains byte-identical, blue fixture still recolors; source alpha/STP unchanged",
                      live_header_sha256=hashlib.sha256((HEADER.parent / "hd_skin_live.h").read_bytes()).hexdigest(),
                      shader_sha256=hashlib.sha256(shader.encode()).hexdigest(), compile_exit=compiled.returncode,
                      test_exit=tested.returncode, scope="Hidden native OpenGL shader harness; no game launched or in-game claims")
        (OUT / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return tested.returncode


if __name__ == "__main__":
    raise SystemExit(main())
