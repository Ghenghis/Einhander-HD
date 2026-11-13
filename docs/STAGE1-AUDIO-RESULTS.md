# Audio and stutter remain unresolved

November 13, 2026. The user reports extreme stuttering, jitter and bad audio.
The production release is not accepted. Changing the correction limit alone
did not resolve the live starvation counters.

[Actual same-source comparison](media/gallery/stage1-audio-correction-results.json)
uses two freshly compiled actual-main executables and the same 170-second
timer-assisted, no-fire route, without recording, source dumps or measurement
screenshots. The 0.5% leg averaged 59.2760 guest frames/s and accumulated 71,713
output-starved sample frames; the 1% leg averaged 59.2738 and accumulated 73,707.
Both closed with exit 0, no recorded errors and closed debug ports. These counters
are sample frames, not the number of audible gaps. The pair was sequential and
had different initial buffer fill; it does not establish a causal improvement
or regression from changing the cap.

The synthetic bridge test improved at 1% for a steady 59.4342-equivalent producer:
starvation fell from 17,815 sample frames to zero. Both caps still starved during
an injected 300ms producer stall. Target/prefill 180ms, ring 280ms, the 32-tap
resampler, 75ms control low-pass and 0.75-percentage-point-per-second slew were
unchanged. A synthetic pass is not actual-game audible acceptance.

Work continues on quiet interval-level profiling of guest stalls, HD source
matching/drawing, decode and readback, followed by guest/pacer/overlay/provider
attribution. Recorder-heavy Robin footage is not a recorder-off pacing result.
Audio playback verification and sustained normal gameplay remain required.

The subsequent same-executable filter-state-cache experiment also failed to
resolve starvation. Over 120 seconds after City, cache off averaged 59.0831
guest frames/s with 61,619 starved output frames; cache on averaged 59.1636
with 66,846. Mean HD draw cost was 2.2291ms versus 2.0620ms per guest frame,
and the enabled path skipped 723,129 redundant sampler-state updates. This is
insufficient. Initial fill differed (158.3 versus 196.5ms), and this single
ordered pair does not establish a causal overall improvement. The earlier
control overlapped competing motion jobs and is preserved but excluded.

The next checks isolate repeated framebuffer-state changes, interpreted overlay
gaps, the Greif approach/arrival/fire windows and native FMV playback. The quiet
120/170-second route clock starts after City, not at application boot. Actual
device-rate game callback audio will be retained for audible review; silent
footage and synthetic audio probes do not qualify it.
