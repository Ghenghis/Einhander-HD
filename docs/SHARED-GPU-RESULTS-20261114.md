# Shared GPU coordination — verified CPU results, November14

## Actual modern GPU result —16:35UTC

The private modern Remix probe ran on3090Ti and FAILED: three identical outputs with zero expected triangle pixels; Shutdown exceeded its15-second deadline, child exit30/40.159s, wrapper exit1/41.681s. Startup/frame return codes and the initial GL readback pass do not establish rendering. Both processes are absent, markers removed and shared grant explicitly released revision10. [Actual evidence and remaining work](../docs/MODERN-REMIX-GPU-RESULT-20261114.md).

Root continues CPU-only diagnosis/publication; bounded Claude texture/HUD work resumes. No game/audio test, installed runtime, RT/DLSS gameplay or full remaster acceptance is claimed. Six native sessions are registered. Metadata monitor PID37252 ends17:06:21.828UTC and proves monitoring only. Earlier dated checkpoints below are historical.

The shared broker now enforces one cooperative grant at a time for Pizza and Einhander launchers. A request does not grant access. The coordinator grants a fenced token, the holder checks it before starting and registers its managed job, and release requires an explicit no-GPU-jobs assertion with no registered PID still alive. Expiry prevents new starts and never transfers ownership. Notifications use a durable outbox outside the mutation mutex.

Eight independent CPU controls pass; twelve Python launcher-guard controls and seven integrated cleanup controls pass separately. [Exact source, captured output and qualified results](../remaster-audit/texture-composer-followup-20261114/README.md). Canonical sources are [the broker](../tools/coordination/shared-gpu.mjs), [its controls](../tools/coordination/test-shared-gpu.mjs) and [the launcher guard](../tools/coordination/shared_gpu_guard.py).

Pizza explicitly released at14:56:05UTC after its37-frame job/exit0. The coordinator independently observed registered parent35576 and child6216 absent14:57:01. Root's legacy user-project hold has not yet been reconciled. No Einhander modern GPU/game/audio test ran. Positive integrated registration/graphics execution remains unverified; no ray tracing or DLSS in-game result is claimed.

This protocol relies on participating launchers. It does not reserve GPU resources at the operating-system level. Current release checks fail closed on any live registered PID, including a possible reused PID; reconcile exact identity without killing unrelated work. Hidden tokens and live state are excluded from publication. Global driver settings and power limits were unchanged.
