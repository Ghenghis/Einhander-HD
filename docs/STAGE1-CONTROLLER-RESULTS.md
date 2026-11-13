# Stage-relative controller qualification

November 13, 2026. **The latest bounded ordinary-input attempt did not clear
Stage 1.** It used two visually verified Continues and stopped at the third
verified prompt, after about 481 seconds. No invincibility, RAM writes, state
loads, stage jumps or turbo were used.

[Actual trial results and sampled policy history](media/gallery/stage1-controller-results.json)

The opt-in `stage_lane` experiment follows fresh source-matched hull geometry,
uses measured stage/checkpoint timing and anchors Greif sweeps to its native
draw clock. Every move is a finite controller pulse. Continue confirmations
require three increasing native prompt frames, followed by positive lives and
a fresh hull before control restarts.

Two earlier attempts remain excluded. The first stopped at 92 seconds after
the inherited forty-poll hull-absence limit. The next exposed a camera/clipping
gap incorrectly treated as a death, while the native life counter stayed
unchanged. It stopped at 135 seconds. The corrected policy requires an observed
native life loss before changing checkpoints. Its input-released absence wait
has both a 720-guest-frame age bound and a 15-second host bound; replies without
a usable clock retain the forty-poll limit.

Twenty-five controller checks pass, including camera gaps, actual life losses,
Continue retention, stale/reversed clocks and bounded recovery without blind
movement. The third live attempt exercised recovery and survived the first
measured Greif volley pair on one life, but subsequent bursts still killed it.
Its later movement schedule remains unqualified. Passing guard tests and
surviving one encounter interval do not establish a successful stage policy.

Stage clear, boss/post-boss progression and later stages remain open. The next
controller work needs measured threat response rather than further treating
the failed fixed movement schedule as completed acceptance.
