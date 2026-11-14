# Installed Remix SDK qualification

Private x64 API-table probe, November 14, 2026. The official0.6.11 header is pinned to NVIDIA dxvk-remix commit42b54bbe2a9280f7720e5b64415c78aa3e15224f with its license notice preserved. The compiled probe loads the explicit installed vendor DLL using restricted DLL search, asks for the API table, checks required scene functions and unloads. It does not call renderer Startup, render geometry, create a project/capture or inject the game.

Actual compile and default CPU-layout probe: exit0. Actual installed-library initialization: result0/exit0, required scene API and external-swapchain function present. This proves an available direct SDK route; gameplay geometry/camera/material transport remains unfinished. Binary and DLL remain local. The recorded build command describes this machine, not a portable clean-checkout engine build.

For the same local prerequisites, compile `remix_sdk_probe.cpp` with the recorded x64 compiler and run without arguments for a CPU layout check or with `--initialize` for API-table qualification. The fixed vendor path and DLL hash are recorded; a different installed runtime requires fresh qualification. Do not interpret this as full dependency/security/release acceptance.
