# Full 24-room facade: actual in-game results

Tested November 12, 2026, 5:22–5:25 PM Arizona time (November 13, 00:22–00:25 UTC). Run: `h24-v2-4096-r1`, Windows OpenGL recompiled runtime.

The full 4096 × 4096 H24 v2 master reached the running game. The entry video and two adjacent internal stills show its varied room interiors on front and angled building faces. This establishes visible integration of the candidate. Final visual approval remains open: the saved proof records `live_visual_accepted: false`.

## Watch the actual footage

[![Play the H24 entry fly-past](media/gallery/h24-front-angle.png)](https://github.com/Ghenghis/Einhander-HD/raw/refs/heads/main/docs/media/gallery/h24-fly-past-entry.mp4)

- [Entry fly-past — 6.00 seconds](https://github.com/Ghenghis/Einhander-HD/raw/refs/heads/main/docs/media/gallery/h24-fly-past-entry.mp4). The target building enters from the right. The dark faces contain the new interiors; the bright blue-window sections use other mappings.
- [Middle recording — 6.00 seconds](https://github.com/Ghenghis/Einhander-HD/raw/refs/heads/main/docs/media/gallery/h24-fly-past-middle.mp4). Subsequent city gameplay from the same run; additional H24 visibility is not established.
- [Later recording — 5.95 seconds](https://github.com/Ghenghis/Einhander-HD/raw/refs/heads/main/docs/media/gallery/h24-fly-past-later.mp4). Further city gameplay from the same run; additional H24 visibility is not established.

These are three separate, byte-identical copies of the original captures, with gaps between recordings. They are silent H.264 recordings of the actual 1280 × 960 game window, captured with FFmpeg `gdigrab`. No synthesized frames, retiming, upscaling or continuous-traversal claim is added. Game turbo was explicitly queried as disabled before evidence capture; the route used no fast-forward and configured rewind off.

**Assistance disclosure:** a private player-invulnerability countdown aid was active, with a 180-second lease. The run records 614 successful one-byte writes to that timer and no lives writes, stage jumps or state loads. The helper stopped after about 124 seconds, without forcibly clearing the live timer. This is assisted visual-review footage. It is not evidence of unassisted survival or gameplay balance.

## Full-resolution stills

Each still is a separate synchronous internal OpenGL readback at 2880 × 2160. Public PNGs use lossless compression with identical decoded pixels; no crop or resize was applied. Their frames bracket or follow the video and are not asserted to be exact video frames.

### Target entry, frames 5800–5802

![H24 facade entering at the right of the city view](media/gallery/h24-entry.png)

### Front and angled faces, frames 6080–6084

![Photographic H24 rooms on dark facade faces beside remaining blue-window mappings](media/gallery/h24-front-angle.png)

### Subsequent city view, frames 7692–7694

![Middle city view from the same assisted session; additional H24 visibility is unverified](media/gallery/h24-middle.png)

### Later city view, frames 8890–8893

![Later city view from the same assisted session; additional H24 visibility is unverified](media/gallery/h24-later.png)

## What the test establishes

- Preparation verification checked all 1,195 PNG keys: 1,194 parent keys were unchanged, and the one facade replacement preserved categorical native alpha. The run used the full frozen 24-room master at 4096 × 4096.
- The recorded native route passed title, fighter selection, weapon selection and City gates before the facade test. User memory cards were not mounted.
- The renderer submitted exact-region replacement key `52F33418-5E9B9AC3` at frame 5742 with a 4096 × 4096 replacement. A draw receipt alone is not visibility proof; the entry footage and the adjacent stills supply the visual evidence.
- The photographic rooms and dark structural bands are visible on front and angled faces. Adjacent blue-window sections remain different mappings, so this is partial building/scene coverage.
- The saved run contains no top-level errors. Input was released and capture stopped. The quit command returned `emu busy or frozen`; the subsequent process-close check reported the debug port closed. The quit reply is not described as a successful graceful shutdown.

## What remains open

The six-second entry clip is a short approach view. It does not show a complete close-to-distant traversal or establish readability of every one of the 24 authored rooms. The middle and later recordings primarily show other buildings and do not extend the exact-key visibility result. Seams, repeated placements, all palette variants and final realism still need review.

The windows use static interior/reflection artwork on existing geometry. This test does not establish view-dependent reflections, room parallax or a PBR renderer. The experimental facade motion-sampling mode was disabled.

FFprobe counted 270 frames in the 6.00-second entry file, 256 in the 6.00-second middle file, and 268 in the 5.95-second later file. Their average encoded rates are about 45.0, 42.7 and 45.0 fps. Normal game-speed settings do not establish stable real-time renderer cadence. Window recording adds load; performance, hitching and continuous audio acceptance remain open. No audio stream was recorded.

## Evidence and provenance

[Machine-readable results and artifact hashes](media/gallery/h24-in-game-results.json) preserve selected facts from the saved run and hashes of the private source receipts. [Gallery provenance](media/gallery/provenance.json) identifies each public asset, original source and pixel-preserving encoding. Private launch configuration, disc paths, saves, runtime binaries and replacement packs are excluded.

This publication verifies and packages an existing run; it does not claim a new game run was executed while preparing these results.
