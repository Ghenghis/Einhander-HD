#!/usr/bin/env python3
"""s45: regenerate s45/README.md = tools/README-head.md + a sha256 table of every s45 file (except README, DLL, PNG,
provenance copies inside run folders, and the superseded tools/w7m-r0-unused)."""
import hashlib
from pathlib import Path

S = Path("C:/github/Einhander/remaster-audit/parallel-stages-20261114/s45")


def main():
    head = (S / "tools/README-head.md").read_text(encoding="utf-8")
    rows = []
    for p in sorted(S.rglob("*")):
        rel = p.relative_to(S).as_posix()
        if not p.is_file() or p.name == "README.md" or p.suffix in (".dll", ".png") or rel.startswith("tools/w7m-r0-unused/"):
            continue
        if p.parent.name.startswith("2026") and p.suffix in (".c", ".h", ".py") and not rel.startswith("tools/"):
            continue
        rows.append(f"| `{rel}` | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |")
    txt = (head + "| file | sha256 |\n|---|---|\n" + "\n".join(rows) +
           "\n\nRun folders also hold provenance copies of the tool, class_mip.c/.h and the compiled DLL; "
           "`tools/w7m-r0-unused/` is the superseded, never-used first merge.\n")
    (S / "README.md").write_text(txt, encoding="utf-8")
    print(len(rows), "files;", hashlib.sha256((S / "README.md").read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
