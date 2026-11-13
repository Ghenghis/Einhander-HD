# Upload-index hitch experiment

Default-off isolated candidate. Runtime SHA-256 22635802b9b7d6ad7aaf680ca5387e432c0400ce734359fa31e2cf66d665ca94. Four GL index/world flag configurations passed 14,224 checks with zero failures.

The actual 120-second firing pair removed 95,019 full index rebuilds (3,562 ms), replacing them with 93,747 incremental updates (133 ms). It did not fix the mini-boss stutter or audio starvation. OFF measured 58.55 guest frames/s and118,587 starved output sample frames; ON measured58.11 and153,966. One ordered diagnostic pair, with unrelated background load; no causal regression or improvement accepted.

Both used a disclosed timer-only aid and instrumentation. No production runtime installed. Actual failure footage, process audio and scope are in [the published result](https://github.com/Ghenghis/Einhander-HD/blob/main/docs/media/gallery/stage1-index48-results.json). Next correction targets guarded native execution of sampled guest hot routines.
