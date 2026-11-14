# RTX Remix setup and actual use — November 14, 2026

**The local texture-ingestion workflow works. A connected Einhander Remix gameplay project has not been created.** The user requested setup and use of the installed toolkit. NVIDIA RTX Remix 1.6.1-0 opens from `C:/Program Files/NVIDIA Corporation/RTX Remix`; the bounded workspace is `C:/Remix/Einhander-HD`.

## What was executed and verified

The existing W3 green-sign PNG was copied byte-for-byte to `sources/green-sign.png` in that workspace. Its SHA256 is `ccee9e7688dabb9cc71057dc3a60e4e7f293e622e321a63f0ff4f241535bd5cd`. The original source remains unchanged. This deliberately tests conversion of a known asset; it does not claim that the existing soft artwork is newly improved.

Two GUI attempts, one in the current process and one with a separate worker, displayed green/100% completion but produced no files in the configured output directory. They were rejected as successful conversions. Inspection of the DDS selector showed no selected shaders in the first result. The GUI progress display alone is insufficient evidence; the exact underlying cause was not proven.

The installed service's published OpenAPI schema was then read, and its documented `POST /ingestcraft/mass-validator/queue/material` endpoint was called with explicit input, DIFFUSE texture type, output directory and one concurrent texture-conversion worker. The returned context reports valid input, successful import and successful exit. Its DDS conversion reports the actual created file:

- `C:/Remix/Einhander-HD/ingested/green-sign.a.rtex.dds`: **1,048,772 bytes**, **1024 x 768 RGBA**, SHA256 `1c6ac7b675883e3df0db373dd5aabab21b7760a663c7a06672d5f5c23cc5bba4`.
- Matching `.meta` ingestion metadata: **6,166 bytes**, SHA256 `ddef5fafb0dad0fc60ccff2d712f0506dec7d382c0b0f91b5caa0e24b520e089`.

The entire DDS decoded successfully. A PNG decode preview was visually inspected; the source's existing soft glyph shapes remain. This was format conversion, not an image-quality improvement. Source-copy identity and the repeat recipe's Python syntax were checked. Its read-only `--verify-existing` path also passed against the actual saved API response and DDS: successful context/import/exit, explicit input identity, successful DDS check/fix, metadata result and complete decode. No additional conversion was submitted by that verification.

The [machine-readable receipt](media/gallery/remix-ingestion-results.json) records plugin results, file hashes, both unsuccessful GUI attempts and the actual API request/response hashes. Full request/response, local OpenAPI snapshot, source receipt, decoded preview and repeat recipe are retained beneath `C:/Remix/Einhander-HD/evidence` and its parent. This work used local files/services; no GPU model download, AI authoring batch or changes to the user's RTX 3060 project occurred.

## The concrete gameplay integration blocker

The project wizard was given the proposed file `C:/Remix/Einhander-HD/project/einhander-hd.usda` and sandbox directory `C:/Remix/Einhander-HD/runtime-sandbox/rtx-remix`. It reported: **“No capture available. Create a capture in the runtime before creating a project.”** The proposed project file does not exist. The installed toolkit's own captures directory also contained only materials/textures subdirectories, with no scene capture. No synthetic capture was substituted.

The current private game settings select **OpenGL**, supersampling 2 and bilinear texture filtering. NVIDIA's [compatibility guide](https://docs.omniverse.nvidia.com/kit/docs/rtx_remix/latest/docs/introduction/intro-compatibility.html) explains that Remix directly replaces DirectX 9; OpenGL requires a separate translation/integration path. Its [project guide](https://docs.omniverse.nvidia.com/kit/docs/rtx_remix/latest/docs/gettingstarted/learning-toolkitsetup.html) distinguishes a runtime capture, a mod layer and the project that links them. Merely browsing to the source repository or creating an empty directory cannot supply that captured scene.

A future live integration must demonstrate a compatible geometry/material stream, actual runtime capture, stable asset identity and correct rendering in a private sandbox before binding replacements. No wrapper was installed or injected, no game backend was replaced, and ray tracing/DLSS are not enabled by the conversion above. The normal game remains usable through its existing HD replacement path.

## Reusing the verified asset workflow

With the existing toolkit open, run the local `C:/Remix/Einhander-HD/Ingest-Green-Sign.py`. It reads the toolkit's discovery record at `%LOCALAPPDATA%/NVIDIA/RTX Remix/mcp.json`, requires a local loopback REST endpoint, submits the retained one-texture request and writes a separate response receipt. Exact local paths and recipe hash are in the result JSON. The installed toolkit also advertises an MCP endpoint, but no persistent Codex MCP configuration was added by this work.

NVIDIA documents [asset ingestion](https://docs.omniverse.nvidia.com/kit/docs/rtx_remix/latest/docs/howto/learning-ingestion.html) as conversion/optimization with metadata. It does not automatically redraw lettering. Einhander's PNG alpha encodes transparent/opaque/STP classes; Remix DDS output is an offline material artifact and has no demonstrated class-preserving runtime mapping here. It must not be copied into the game's PNG pack as if that compatibility had been checked.

The NVIDIA App's automatic game optimization message is separate from this toolkit workflow. The private power preference was usable and was [restored after its two-run test](STAGE1-POWER-PROFILE-RESULTS.md). Automatic presets do not create new game artwork or unlock renderer integrations. The [green/pink sign defects and private alternatives](STAGE1-SIGN-QUALITY-20261114.md) remain open visual work.
