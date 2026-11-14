# Recorder reserve correction and rebuilt menu file evidence

The engine source now reserves a JSON record and up to768 bytes per remaining capture mark. Under high draw/byte pressure, optional draw rows and source sidecars may no longer consume that reserved space. This improves evidence completeness; it is not a claim of smoother gameplay or remastered audio.

## Actual CPU reproduction and source integration

The exact original renderer adapter plus unchanged capture/sampler/event headers reproduces missing mark rows:8/8 dropped in S1 and S2,4/8 in S3 and2/2 under byte pressure. The patch drops none in seven tested scenarios and passes seven synthetic boundary states. Four mutants are detected independently: off-by-one loses a row, missing byte reserve loses marks, missing subtraction guard wraps, static reservation wastes exhausted-event capacity. Actual outer exit0,11.011s onCPU15 BelowNormal,31 JobObject processes total/0active, tree absent. Canonical inputs remain unchanged during that test. No GPU, game or native3MiB event files are written; event blobs are accounted, and real JSON rows are written. Full source-sidecar IO is not modelled.

Root applies the minimal patch against exact3ffdf13f baseline. Git apply produces CRLF, so the first raw target-SHA assertion fails after applying; raw bytes and failure are preserved. Root then independently verifies normalized bytes equal the exact reviewed e12716f9 target before writing those LF bytes. No semantic correction is hidden in normalization. Native Claude independently source-reviews the patch without a blocker.

Minor limits remain: event_reserved_bytes status reports binary reservation and omits up toremaining_events*768 mark-line bytes; record_cap_skips now includes soft reserve skips; impossible custom record/event budgets can still lack room for every mark, and limits validation has not been tightened. Default5000/8 and planned20000/3 budgets are feasible. No universal guarantee for impossible budgets is claimed.

## Actual private engine build

New v68 freezes160 source/header files, compiles only gpu_gl_renderer.c and links retained v67r3 objects. Compiler/link elapsed2.709s; bounded child31992 exit0/3.992s, outer0/5.170s, eight JobObject processes/0active and tree absent. Independent readback checks160 source pins and155 linked-input records; only the renderer object differs. The compiler dependency file proves the new header was used. EXE SHA2565c1436ff778701d981410da61046aca60c0da60215a5f724523197b58199dfaa. This is not a clean full-source rebuild, installed release or live-qualified runtime. The first readback's basename-only map falsely conflated two different crc32 objects; its failed verifier is preserved, and the passing readback compares exact path/hash records.

The original-source replay bundle contains all five pinned host inputs, original harness/script/patch and exact expected variant headers. Root actually runs isolated --prepare-only and reproduces all six tested header hashes without changing current engine source. --run is supplied for a future separately granted replay and was not executed by that wrapper. Copy the bundle to a fresh writable workspace; do not execute inside immutable published evidence. No game assets, binaries or SDK are required for this CPU harness beyond the separately installed compiler.

## Actual repaired menu file readback

Fresh v5 runs A/B/C build79+25+14=118 runtime files in70.97/72.01/65.63s on oneCPU BelowNormal. Each exits0, no forced kill, no child left; measured peaks266.8/266.3/241.8MiB. Final summary e124d0e8 lists72 units and118 primary-class passes. Root independently verifies1183 hashes: all708 variant PNG references, the118 summary member candidate/noR5/native words/CLUT references and three run reports; zero case-insensitive output-path duplicates.54 CLUT sources are explicitly pinned under C:/github/REMASTER_STAGING; no D: reads. This readback does not replay the class algorithm or accept appearance. Twelve competing cross-folder entries still need a visual choice; no menu candidate is integrated or installed.

Old72/72 and118/118 summaries remain INVALID; this new result does not repair old overwritten outputs. Original source/reports/failures remain immutable.41 pack units,51 substantial-error units, roughly1400 out-of-census PNGs, interaction tests and live HUD/menu appearance remain open.

## Remaining texture and runtime gates

Root views the real cage preview and approves correctness-only: topology, native brightness/void/alpha are restored, but texel stepping remains and this is not finished HD artwork. CG1 exits0/1.104s. CG2 freeze exits1 because copying a read-only builder carries the attribute into its durability pass; the partial v1 has no READY/SHA256SUMS and is preserved/unusable. New r1 changes the copy operation and adds a read-only-source test. CG3 declines atCPU60.8%, no test/freeze child, no retry. A later fresh CG3 batch is pending, not a result here. A disclosed ungranted broad hash scan beforeCG1 is an author-reported compliance failure, not an approved resource operation or overall compliancePASS.

The separate unassisted runner's12 CPU safety cases pass in the previous packet, but native follow-up review finds default-path query/menu omissions and a missing focus sample. Root is correcting those with an independent fake-transport route test; no functional/live qualification is claimed. Existing partial/failing evidence stays available. Source capture, full process watchdog/adapter checks and any live launch remain gated.

RTX3090Ti remains user-reserved through at least18:37:05UTC; later starts still need a fresh broker grant.3060 was not used. Last actual modern Remix output/lifecycle remains FAILED. No GPU/game/audio test runs in this packet. Normal mini-boss/audio acceptance, realistic skins/selectors, complete background/sign/ship/HUD coverage,4K fidelity, working Remix scene/camera/material transport and RT/DLSS, all seven stages and release/rollback remain incomplete.

Only source, reports and hashes are published. Generated PNGs, executable/object/DLL/SDK payloads, ROM/BIOS/cards, user state and live fenced tokens remain private. Build receipts include private file identities and exact commands rather than distributing the runtime.
