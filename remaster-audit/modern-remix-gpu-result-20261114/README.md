# Modern Remix GPU probe — actual failure, November 14

The private API0.16.1/OpenGL probe ran on the RTX3090Ti at16:33:12–16:33:53UTC and FAILED. It created a small320x180 nonactivating window and submitted32 synthetic frames. This is a diagnostic test, not the game or a remaster release.

Startup, material/mesh/camera/draw, Submit, InteropInfo and Present returned0. The initial owned OpenGL readback contained57,600 magenta pixels, so the basic readback control passed. The actual target adapter was independently observed. These successes do not prove that submitted geometry rendered.

All three scene samples (frames7/23/31, offsets-2/0/+2) have exactly the same SHA2568b329bbf0b37386cd7f8094766a953d89287b83a5a7b3aef400ff2dc364727a2, zero green pixels and no expected projected triangle. They have zero fallback-magenta pixels, so this is not the old fallback-magenta result. Independent image oracles reject all three. No successful moving geometry, image synchronization, ray-traced gameplay or DLSS acceptance is established.

Mesh/material destruction returned0, but Shutdown entered and exceeded its15-second internal deadline. The child exited30 after40.159s; the managed wrapper exited1 after41.681s. The independent45-second parent termination watchdog was not used. The probe result records lifecycle_passed=false. SDK log capability notices are not evidence those features are integrated or usable in-game. The log also reports a late swapchain initialization and undisposed common device objects; their causal role requires source review rather than assumption.

Cleanup is verified: child34664 and managed parent38504 are absent, both nonce resource markers were released, and the shared broker was explicitly released at16:35:17UTC, revision10, event10767db9-5854-49c9-ba59-9dbb3cfc1502. No automatic expiry takeover, unrelated process kill or global driver/power change occurred. CPU texture jobs may resume under the coordinator's two-job limit. Root continues CPU-only diagnosis; a further GPU attempt requires a fresh reviewed plan and grant.

## Exact execution and preserved prestart failure

The first official grant, revision5, expired unused during context recovery. No graphics process or execution directory was created under it. Root explicitly released it (revision6), requested again and committed a fresh grant (revision8), immediately executing the reviewed parent. The grant's empty owned-heavy process inventory and CPU20%/74GiB gate are recorded. The wrapper independently sampled CPU15.6% before launch, used CPU15 and BelowNormal priority, and passed a fenced token locally without logging it.

Executed command: python -X utf8 run_modern_gl_probe.py --run-after-explicit-user-release, through the reviewed wrapper. Actual parent creation time1794673991.948414 and the child command, source/DLL/executable SHA256 pins, frame oracles and process/cleanup checks are in the raw reports. Parent source d545a7de7ef220e1c30eadb69eef3aa12f64db60861c40d56df485f4d36ea122; EXE3911f74c0e380f9358d32f529ee1de440b709bdf8fec93b1ef4ea12a91643d1d; private DLL a8365272734cf5541e3600aeacb445c0fd102187dc3a167495a56809ce5891d9.

## What remains

Investigate actual output/readback synchronization, geometry submission/camera conventions, initialization readiness and shutdown ownership using source and these failed logs. Do not relax the image oracle or count API return codes as visual success. World geometry/camera/material transport, actual in-game RT/DLSS, texture ROI composition/live acceptance, complete skins/HUD/menu interactions, audio/listening/performance and all seven stages remain unfinished. No game/audio test, installation or whole-project completion is claimed here.

Six actual native Claude sessions now have registered owner/checkpoint routing; the dated roster records the UI/support additions. Their source and art work continues independently. A bounded metadata monitor was renewed, but proves monitoring only. Earlier immutable packets and failed evidence remain unchanged.

The packet is a source/report subset. SDK DLL/JAR, executable, cache, sentry payloads, generated images, live grant tokens/private broker files, ROM/BIOS, native game data and user state are excluded and retained locally where applicable. Image hashes are published. SOURCE-MAP binds every copied source/report to its local provenance. SHA256SUMS binds packet bytes.
