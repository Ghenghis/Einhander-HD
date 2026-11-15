# Class ownership rules v2: revision after the first real-data review (claude-einhander, 2026-11-14)

This supersedes the R2/R4 definitions in `DESIGN.md` section 2. The rest of `DESIGN.md` still applies (source facts, R1,
R5, M1–M5). `proto/` (v1) and its runs are kept as delivered. v2 lives in `proto-v2/`, `runs-v2/`, `runs-f6-v2/` and
`repairs-v2/`.

## Why the change
- The first repair candidate (`repairs/20261114T094851Z-95A3-w2-atlas-plus-kpanel`, review
  `22D9BF19-00A1D33C.png`) **squared off an authored round edge**.
- The authored disc edge lies slightly *inside* the blocky native silhouette. The cutout sliver between the two reaches
  native cutout territory by **chaining through neighbouring cells**.
- v1 R4 demanded a native cell of that class directly adjacent to the component's own cell, so it called the sliver an
  island and the repair filled it. **That would damage legitimate authored contours.** v1 also flagged thin authored
  strokes at junctions for the same reason.
- The v1 real-data counts (`runs-f6/20261114T094311Z`: 602 violating keys, 66,445 pinhole cells) are therefore an **upper
  bound** and are superseded by the v2 run.

## v2 rules
A pixel is **deviant** when its class X differs from the native class C of its own cell.

| Rule | Statement | Rationale |
|---|---|---|
| R1 centre | pixel `floor((i + 0.5)·s)` of every cell has class C | point-mode authority; unchanged |
| **R2 displacement** | a deviant pixel's centre lies within **s/2** (Euclidean) of a native cell of class X | a sub-native contour may move a native class boundary by at most half a native texel; anything deeper changes what the native texture shows |
| **R4 connectivity** | a deviant pixel's class-X component, 4-connected **across cells**, reaches a non-deviant class-X pixel | islands are errors; contours that chain through neighbouring cells are not |
| R3 (diagnostic) | uniform native 3×3 but the pixel differs | implied by R2 |
| R5 cutout RGB | as v1 | |

**Repair v2:** R1/R2/R4 violators take their cell's native class.
- It **iterates until clean** (at most 8 passes): removing a displaced channel can strand a blob that is then an island.
- It reports `passes` and `residual_violations`.
- RGB of pixels that stay visible is never changed.

**What v2 still flags:**
- pinholes: a cell cutout or recoloured more than half a texel from any native boundary of that class, with only the
  centre stamped;
- islands and specks;
- foreign classes;
- topology changes, such as a transparent gap carved between two natively joined opaque strokes.

## Fixtures (`runs-v2/20261114T095451Z`: 7,379 checks, 12/12 mutants)
- **F1b inset disc:** an authored inset of 0 px or 2 px is accepted with 0 islands. The 6 px reported at a 2 px inset are
  blocky-corner geometry. An inset of 7 px (> s/2) is flagged (505 px displaced).
- **F1c:** a blob that is legal by distance, fed only through a displaced channel, needs exactly 2 repair passes, and ends
  clean.
- **F2:** the fixture was restricted to its valid domain. The v1 fixture contained two v2-correct flags: image-corner cells
  with no native cutout neighbour inside s/2, and a hairline crossing a diagonal stroke, which carved a gap.
- **Minify:** pixel-count variance under a sub-pixel pan:

  | Scale | Current | Proposed |
  |---|---:|---:|
  | 4× | 720.6 | 0.25 |
  | 8× | 1001.7 | 0.25 |
  | 12× | 119.5 | 32.7 |

  With current sampling the stroke vanishes in some frames (minimum 0 pixels at 8× and 12×); with the proposed sampling it
  never does (minimum 30 or more).
- F3 seam, F4 palette and F5 fringe are unchanged.
- **New mutants:** the s/2 bound relaxed to s; connectivity disabled; connectivity blind to class; repair limited to one
  pass.
