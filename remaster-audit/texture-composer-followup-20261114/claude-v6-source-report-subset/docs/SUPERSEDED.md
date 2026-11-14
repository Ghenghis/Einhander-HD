# frozen/renderer-v61-classmip-v1 is SUPERSEDED (kept unchanged)

Root review msg_6dc79298 (2026-11-14T11:05Z) found two defects in v1. Neither was caught by my tests:
1. `hdcm_build_level` shifted by L (`s >> L`, `1 << L`) before bounding L. L >= 32 is undefined behaviour in C.
2. The upload loop counted a level as uploaded after `glTexImage2D` without verifying it. A failed or OOM upload could
   leave a partial chain marked admitted, with MAX_LEVEL active.

Also (msg_2918e6db): `run_host.py` exited 0 even when its verdict was FAIL (host-console-2.log).

v2 fixes all three and is frozen separately as renderer-v61-classmip-v2. v1's READY/SHA256SUMS stay as written.
