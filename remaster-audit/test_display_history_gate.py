"""Compile the runtime's actual gate; false/off must never enable GPU readback."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class DisplayHistoryGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = next((p for name in ("clang", "cc", "gcc") if (p := shutil.which(name))), None)
        if compiler is None:
            raise unittest.SkipTest("A C compiler is required to execute the runtime gate")
        source_path = Path(__file__).resolve().parents[1] / "windows-x64/psxrecomp/runtime/src/debug_server.c"
        source = source_path.read_text(encoding="utf-8")
        signature = "static int disp_ring_capture_enabled(void)"
        gate = signature + source.split(signature, 1)[1].split("static void disp_ring_capture(void)", 1)[0]
        cls.directory = tempfile.TemporaryDirectory(prefix="ein-display-history-")
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        fixture = root / "gate.c"
        fixture.write_text('#include <stdlib.h>\n#include <string.h>\n#include <stdio.h>\n' + gate + '\nint main(void) { printf("%d\\n", disp_ring_capture_enabled()); return 0; }\n', encoding="utf-8")
        cls.executable = root / ("gate.exe" if os.name == "nt" else "gate")
        subprocess.run([compiler, "-std=c11", "-O2", str(fixture), "-o", str(cls.executable)],
                       check=True, capture_output=True, text=True, timeout=30)

    def test_only_exact_one_enables_continuous_readback(self):
        for value in (None, "", "0", "1", "false", "off", "no", "true", "yes", "01", " 1", "1 ", " 0"):
            with self.subTest(value=value):
                environment = dict(os.environ)
                environment.pop("PSX_DISPLAY_RING", None)
                if value is not None:
                    environment["PSX_DISPLAY_RING"] = value
                output = subprocess.check_output([str(self.executable)], env=environment, text=True, timeout=5)
                self.assertEqual("1" if value == "1" else "0", output.strip())


if __name__ == "__main__":
    unittest.main()
