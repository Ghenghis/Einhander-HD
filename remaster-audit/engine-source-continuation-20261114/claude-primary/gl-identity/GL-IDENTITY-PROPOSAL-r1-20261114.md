# GL adapter identity: proposal r1 (claude-einhander). Written 2026-11-14, tool clock 19:34:45Z

Status: SOURCE ONLY. Nothing in this proposal was compiled or run.

This supersedes the r0 document `GL-IDENTITY-PROPOSAL-20261114.md` (bcc75017…, kept read-only).
- r0's header times "~19:35Z" were **wrong guesses**: the tool clock read 19:29Z when r0 was written. Every time
  in r1 comes from a tool clock.
- The r0 **patches are unchanged and remain the proposal.** Root accepted their source at msg_7634d703.
- r1 adds:
  - the GL-backend gate caveat;
  - an explicit first-only scope;
  - a pure-CPU fixture that tests the patch's own bytes.

## Formal pins (sha256)

| Item | Path (owner dir = remaster-audit/claude-einhander-primary) | sha256 |
|---|---|---|
| canonical base | windows-x64/psxrecomp/runtime/src/gpu_gl_renderer.c | 92d080578d2a3d734160deae1d67ae186b08f4e9f7ca2d5ecdd3d5344b37d03c |
| v68 base (frozen; never modified) | remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v68-recorder-reserve-r1/src/gpu_gl_renderer.c | 9a878ca4cf74d7c45a43b0308d5820243728a3df3a51a2a01e34d05cdbcfc487 |
| patch vs canonical (r0, accepted) | gl-identity/gl-identity.canonical-92d08057.r0.patch | 42690420aefb2de4f48b98420903a3587564cc63802ddcb4849798b2e9244ac3 |
| patch vs v68, for a NEW v69 copy (r0, accepted) | gl-identity/gl-identity.v68-9a878ca4.r0.patch | 2f603398d7971bca206328dcfe64ebadf5896445055d12388ba1477f051e7538 |
| canonical + patch (scratch, not published) | — | b68d8cbd2ef74e046a77067a9a19425ed5748989694dc6546f28eb58d7c366b8 |
| v68 + patch (scratch, not published) | — | 6caee7b65b9d61f1f2a96bef6fd8c92c6cdcf7e9b76883dce735322d9d88c82a |
| fixture test (new) | gl-identity/fixture/test_gl_identity.r0.c | 0ec4ad0133f7c2d8553897170019a5dc19d82340da5037c16aece83bed9da646 |
| fixture builder (new) | gl-identity/fixture/build_gl_identity_fixture.r0.py | 4c488ecf5575c001492e168b336e99d513a7be2b7a35f77725ec8ceec3adb88d |

## Scope statements

**Model, not device.** The line reports the model string the GL driver gives for the context it created. For example,
it separates a 3090 Ti from a 3060. It is not a physical identity: no UUID, no PCI bus. Two cards of the same model
look identical.

**First context only.**
- `gl_identity_capture()` is guarded by `s_gl_id_captured`.
- It runs once, at the first successful context creation (single call site, `main.cpp:13281`).
- If a future change recreated the GL context, the identity would NOT be re-read, and the line would describe
  only the first context. Today no second call site exists (grep of `runtime/src`).

**Logged before the pipeline is known to work.**
- The capture runs before `load_modern_gl()` and `init_gpu_raster()`.
- A host that then falls back to software therefore still prints a 3090 Ti identity line.
- The model string alone is never evidence that GL rendering is active.

## Required launch gate: the model string is necessary, not sufficient

A runner gate that wants "the game rendered on the 3090 Ti through GL" must require all of these, fail-closed:

1. Exactly one `psxrecomp: GL identity ... truncated=0` line in `stdout.log`, whose renderer contains the granted
   model token.
2. A `psxrecomp: GL GPU pipeline ready (` line (`gpu_gl_renderer.c:4935` or `:4939`, emitted at the end of a
   successful `init_gpu_raster`).
3. No `psxrecomp: GL pipeline init failed` line (`:5003`, the software fallback).
4. Actual GL present-sequence advancement after the title, taken from evidence the runner already collects.
   - Root names the exact field. I did not verify which existing RPC exposes a GL present counter, so I do not
     assert one here.

## Pure-CPU fixture (no GL; run only under a grant naming the CPU)

`build_gl_identity_fixture.r0.py --cpu N --out-root DIR` does the following.

**extract**, in-process:
- verifies both patch pins;
- requires exactly 2 hunks;
- hunk 1's added lines must start with the identity comment and contain `gl_identity_capture`;
- hunk 2 must only add `    gl_identity_capture();`;
- the canonical and v68 blocks must be byte-equal;
- writes them unchanged to `gl_identity_extracted.inc` and records that file's sha.

The code under test is the patch's own bytes, never retyped.

**compile:**
`clang++ -x c -std=c11 -Wall -Wextra -Werror -I <out> executed-test.c -o test-gl-identity.exe`
(the clang 22.1.8 mingw toolchain path already used by the r5–r7 builders), 45 s cap.

**run:** `test-gl-identity.exe fixture-result.json fixture-stdout.txt`, 10 s cap. It must exit 0 with 15 checks,
`passed:true` and `gl_used:false`.

Test cases. Copy, 9:
- NULL → `?`;
- empty → `?`;
- plain ASCII;
- `"` `\` 0x01 0x7F and UTF-8 bytes each become `?`;
- an all-non-printable string keeps its length;
- a space is kept;
- 127 characters → not truncated;
- 128 → cut to 127 with truncated=1;
- 4096 → cut to 127 with truncated=1.

Capture, 6, with `glGetString` stubbed:
- the exact single stdout line;
- exactly 3 queries;
- a second call makes no further query and prints nothing (first-only);
- the captured flag is set;
- the cached renderer is unchanged after the stub changes.

Process rules: each step is one child at BelowNormal with affinity N, with exit codes checked. All outputs are
under `DIR/<stamp>` and nothing outside.

**Not covered by the fixture:**
- a syntax check of the full patched renderer, which needs the SDL and runtime include tree. That belongs to root's
  private v69 build step.
- real driver strings;
- any GL behaviour.

## v69 integration rule (unchanged from r0)

- Apply the v68 patch to a NEW v69 copy of the frozen v68 `src/`.
- Never overwrite v68, and never substitute the canonical renderer for it, since that would drop v68's private delta.
- No new header dependency.

## Checks actually performed for r1

- `sha256sum` of every file listed in the pins table.
- `grep` for the pipeline-ready and fallback log lines (`:4935`, `:4939`, `:5003`).
- Nothing was compiled or executed. The fixture has not been run.
