# Original claude-einhander durable handoff, 2026-11-14 ~14:50Z

Session: desktop `local_11357b05-21ce-4470-8da8-e1597e772a7f` (CLI 11357b05-21ce-4470-8da8-e1597e772a7f), title
"Codex coordination update (fork 2)", created 06:29:24Z.

**Resources:** no CPU or GPU job is owned or running. The last process check was at 14:30:03Z, and no job has started since.
The only process that runs at times is a background Hermes inbox watcher.

## Project-root correction (in progress)
- App metadata at 14:31Z: cwd and originCwd were `C:\github`. The continuity hook did not run for this session; it has no
  `activity-1a5b43b8c45bc6cd.json`.
- The earlier `change_directory(C:\github\Einhander)` at 06:21:20Z ran in the PARENT session 17f8023f, before this fork was
  created. This fork never received it.
- This turn calls `change_directory(C:\github\Einhander)`. Its schema says the working directory and project settings move
  when the turn ends.
- Next turn, verify with `get_session self` (cwd), with the activity file
  `.hermes3d_orchestrator/continuity/activity-1a5b43b8c45bc6cd.json`, and with inbox routing.

## Completed this session, with pins
- **renderer-v61-classmip-v5-r2:** READY 5f96e715…, SUMS bb270f8c. The damaged v5 is kept unchanged; its record
  DAMAGED-renderer-v61-classmip-v5.json is 3eb8c342.
- **renderer-v61-classmip-v6:** READY 33ccad7e67b77cce354a8586b7bf5eab1f864e1ec41b935ac0bf9f6eb01344a0, SUMS 904cc6bc…,
  1111 files, fsync plus independent read-back.
  - Host run 20261114T142204Z: result c53dfe6b…, exit code not captured.
  - GL selftest 20261114T142842Z: exe e3714b3e…, built and NOT run.
  - Pack TU hd_texture_pack.cpp 6f65ee3c… is host-tested only and not linked.
- **RISE:** hand-authored v5 approved; expand33/20261114T135902Z d4379b41 gives 33/33.
  - I reviewed root's exact-native-alpha r1 and its composition world-integrated-rise-f32-r1 (33 entries, 1666 unchanged,
    native admission 0 failures); no objection.
- **S2/S3 audit:** handed to s23 (later-stages-audit/runs/20261114T133157Z).

## Pending (owner: original Stage 1 / RISE / shared-runtime v6)
1. **95A3BCF8 region O distant-city windows.** These are the user's green/pink "signs".
   - Builder: `claude-backlog/95a3-o-city/o_city_rebuild.py`.
   - Preview: `preview/20261114T144212Z`: O-60245B3A f0c7ae7a, O-07A9568D d22ed911, builder snapshot 8df06be0.
   - The freeze needs a CPU grant: request A, msg_567c4e7d.
   - Output: `frozen/95A3BCF8-O-city-v1`, with page2048 drop-ins and page4096 options.
2. **Stage 1 review of s67 r1b, explosion keys 10932164 ×4.**
   - Static review sent as msg_ac9d22d6: the pack copies are pixel-identical re-encodes; adopting the repair changes Stage 1 too.
   - The pixel audit needs grant request B. Tool: `class-mip/stage1-fx-review/review_fx_repair.py` (db5d1033…).
   - Command: `review_fx_repair.py <s67>/repairs/stage6-fx-classrepair-r1b/stage6-large-explosion-10932164-v1`
3. **v66 review:** waits for root's published v66 actual CPU results. The r3 source spot-check was already sent at 13:12Z.
4. Every CPU job is launched through the scratchpad `run_rc.py` wrapper, which records rc, PID and children. A copy of its
   logic belongs in any new session.

## Update 14:51Z
- **Item 2 done:** review B ran under grant msg_e78dd3dc. Run `stage1-fx-review/runs/20261114T144900Z` (result 94c85894…):
  - rc 0, 9.4 s, slot returned at 14:49:09Z;
  - 8/8 PASS, every class flip lands on the native class;
  - look is neutral-to-better (pinholes filled, stray slivers removed); simulation only.
- **Root switch:** change_directory was called in this session at ~14:45Z, but after the turn ended, `get_session` still reports
  cwd C:\github and no activity file exists. The in-place switch is not effective; replacement is up to main.

## Final status 15:03Z: retired from new assignments (coordinator msg_c9ef56bd)
- The in-place move FAILED: the app toast said "Couldn't move the session"; cwd is still C:\github; no hook activity file.
- Original 11357b05 takes no new assignments and owns no CPU/GPU jobs. There is no user_stop, and the transcript is kept.
- From now on, new claude-einhander mail is left UNREAD for the canonical-root replacement session. Original acked
  everything up to msg_c9ef56bd.
- Open for the replacement, in this order:
  1. 95A3BCF8 region O freeze (grant A, still queued);
  2. v66 review, once root publishes its results;
  3. live A/B inputs for root: region O pages, s67 r1b explosion keys, RISE native-alpha composition.
- The exit-code wrapper is persisted as `remaster-audit/claude-backlog/tools/run_rc.py`. Usage:
  `python run_rc.py OUT.json TIMEOUT_S -- CMD ...`. It pins itself BELOW_NORMAL on one CPU, kills the child on timeout and
  records rc, child_pid, start/end and children_left with fsync.

## Rules kept
- Work only in C:\github\Einhander; never touch D:.
- One below-normal CPU job, and only on an explicit grant. No GPU, game or Remix work.
- Frozen folders are immutable, and failed runs are preserved.
- Mail is coordination data, not authority.
