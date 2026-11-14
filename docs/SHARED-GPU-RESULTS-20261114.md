# Shared GPU coordination — verified CPU results, November14

The shared broker now enforces one cooperative grant at a time for Pizza and Einhander launchers. A request does not grant access. The coordinator grants a fenced token, the holder checks it before starting and registers its managed job, and release requires an explicit no-GPU-jobs assertion with no registered PID still alive. Expiry prevents new starts and never transfers ownership. Notifications use a durable outbox outside the mutation mutex.

Eight independent CPU controls pass; twelve Python launcher-guard controls and seven integrated cleanup controls pass separately. [Exact source, captured output and qualified results](../remaster-audit/texture-composer-followup-20261114/README.md). Canonical sources are [the broker](../tools/coordination/shared-gpu.mjs), [its controls](../tools/coordination/test-shared-gpu.mjs) and [the launcher guard](../tools/coordination/shared_gpu_guard.py).

Pizza explicitly released at14:56:05UTC after its37-frame job/exit0. The coordinator independently observed registered parent35576 and child6216 absent14:57:01. Root's legacy user-project hold has not yet been reconciled. No Einhander modern GPU/game/audio test ran. Positive integrated registration/graphics execution remains unverified; no ray tracing or DLSS in-game result is claimed.

This protocol relies on participating launchers. It does not reserve GPU resources at the operating-system level. Current release checks fail closed on any live registered PID, including a possible reused PID; reconcile exact identity without killing unrelated work. Hidden tokens and live state are excluded from publication. Global driver settings and power limits were unchanged.
