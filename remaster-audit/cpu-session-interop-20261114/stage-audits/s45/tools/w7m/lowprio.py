#!/usr/bin/env python3
"""lane-s5 freeze-safety wrapper: run a lane script at BELOW-NORMAL priority (psutil nice), one job at a time.

    python -I -B lowprio.py <script.py> [args...]

Refuses to start while CPU-QUIET or GPU-RESERVED exists (coordinator rule for heavy jobs). The wrapped script keeps
calling gpu_queue.cpu_yield() itself (that one only waits on CPU-QUIET).
"""
import runpy
import sys
from pathlib import Path

import psutil

CA = Path('C:/github/Einhander/remaster-audit/comfy-authoring')
for marker in ('CPU-QUIET', 'GPU-RESERVED'):
    if (CA / marker).exists():
        sys.exit(marker + ' is set: not starting')
p = psutil.Process()
p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
script = sys.argv[1]
sys.argv = sys.argv[1:]
sys.path.insert(0, str(Path(script).resolve().parent))
print('lowprio: priority', p.nice(), 'running', Path(script).name, flush=True)
runpy.run_path(script, run_name='__main__')
