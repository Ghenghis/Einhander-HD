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

[Actual twelve-second game-output audio](media/gallery/stage1-transition-audio-failed.wav)
is now available from the following failed diagnostic. It is exact contiguous
48kHz stereo callback PCM, including the real starvation, copied after timing
measurement. The run averaged 59.4888 guest frames/s and accumulated 38,195
starved output frames in 120 seconds. It used the opt-in framebuffer-bracket
experiment, private render preference 9 and rewind off. No same-binary bracket
control or normal-settings acceptance is claimed.
[Audio provenance and results](media/gallery/stage1-runtime-audio-results.json)
include sample offsets and PCM hashes. These earlier tests used private render
preference 9. They do not represent the user's normal preference 2.

The [normal-settings controls](media/gallery/stage1-normal-settings-audio-results.json)
now cover the same v37 executable and frozen artwork at preference 2. Each ran
for 120 seconds after City with no recording, source dumping or measurement
screenshots, with the disclosed timer-only aid and no firing:

- Rewind on, depth50, interval15 / FMV interval4: **59.7900fps; 10,640 starved sample frames**.
- Rewind on, depth50, interval15 / FMV interval15: **59.9177fps; 2,892 starved sample frames**.
- Rewind off: **58.4351fps; 121,451 starved sample frames**.

All closed with exit0, errors[] and closed debug ports. This was one ordered
series with different initial buffer fill and route timing; it does not prove a
causal benefit from either cadence. Disabling rewind did not remove the symptom.
The near-60fps baseline average concealed seconds near 51–52fps around elapsed
107–110s. Actual successful readback deltas were one, zero and zero. XA stayed
active during ordinary depth15 gameplay without additional MDEC decoding, so
XA alone is not proof of a movie or frequent successful rewind snapshots.

Exact contiguous twelve-second callback PCM excerpts are available for
[normal rewind](media/gallery/stage1-normal-rewind4-audio.wav),
[cadence15](media/gallery/stage1-normal-rewind15-audio.wav) and
[rewind off](media/gallery/stage1-normal-rewind-off-audio.wav). Each begins at
the host sample index observed at/after elapsed104s. They are copied after
measurement with no effects, retiming or resampling. Callback PCM is not hardware
loopback and cannot establish device-driver continuity. **Audio remains failing.**

Next: acquire the actual gameplay code that replaces boot-text RAM, check its
execution evidence and exact-byte cache admission, then compare a compiled
candidate with the control. Rendering submission remains a separate target.
Native FMV playback, ordinary combat and sustained audible acceptance are open.
