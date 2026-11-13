# Stage-relative controller qualification

The later enemy-aware prototype replaces timed movement with read-only native
draw-source clusters, target tracking, vertical aiming and incoming-threat
response. Its closed 180-second MkIII run acquired targets, fired, equipped an
ASP pod and made evasive moves. The 90-second still shows a native score of
18,980. It lost lives (counter 03 to 01), used no Continue, and did not clear the
stage. [Actual results and continuous 32-second preview](media/gallery/stage1-robin-targeting-results.json)
are retained with packet-content and timestamp verification.

![Unassisted Robin targeting prototype](media/gallery/stage1-robin-targeting.mp4)

This footage uses v32's aligned firing policy. The subsequent continuous-main
gun and automatic-craft refinements are separate experiments. Forty controller
tests pass, but neither those tests nor this footage qualify normal installation,
complete threat coverage or a stage clear. The following failed timing-policy
trials remain part of the evidence history.

The subsequent automatic-craft/continuous-main test recognized MkIII and closed
cleanly after 180 seconds, with life counter 01. Its recorded gameplay averaged
48.50 guest frames/s and accumulated 1,589,453 output-starved sample frames.
Performance failed; the candidate remains uninstalled. That run differs in
combat and host conditions and does not isolate the cause of its slower pacing.

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
