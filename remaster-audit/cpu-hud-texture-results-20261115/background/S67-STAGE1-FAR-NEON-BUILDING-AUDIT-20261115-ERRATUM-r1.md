# Erratum r1 to S67-STAGE1-FAR-NEON-BUILDING-AUDIT-20261115.md (`4f39c1c3…`, kept frozen)

Per root msg_229dbeb4. Each correction below supersedes the wording of the original. All findings stay metadata-only.

1. **K-panel page counts.** The original said three pages were identical and then that the third differed. Corrected: in class-mip `runs-f6-v2/20261114T095517Z/result.json` (`c7dd79d6…`), only the staged `f17632…` and the authored K-panel-v1 page2048 `791c01a8…` report identical page-level counts (r2 displaced 82,158 px, r3 uniform-bad 35,294 px). livepack-classfix-v2 `8d4c7aee…` reports different counts (r2 82,285 px, r3 35,367 px). All three are WHOLE-CELL VIOLATION.

2. **Page-level failure is not attributed to any region.** Whole-page counts do NOT establish that the failure lies outside K, nor which named ROI fails. The original's statement that these counts are "dominated by regions outside K" is withdrawn. Likewise, the original's labels "FAILED" for C, D, F, L, T, U and X/Y mean only that the **whole-page result recorded for the key** is a WHOLE-CELL VIOLATION. Whether the failure lies **inside** each named region is **UNMEASURED** until a region-scoped measure exists.
   - It remains true that staging `791c01a8` alone would not clear the recorded whole-page failure.
   - K's region fidelity is unknown.

3. **95A3BCF8-7589E98F.** "Cannot render" is withdrawn. The native game already drew this key 4 times. What is blocked is offline HD authoring and the native-class audit, because the source CLUT has not been captured. No palette may be invented.

4. **Scope of "no ACCEPTED-LOOK".** This applies only to the subset audited here, and means no **recorded, qualified** live look acceptance was found. It says nothing about other art, and nothing about whether users perceive an improvement.

5. **H24 facades.** The census's "user-approved" may refer to a different image, style or version than the H24 `live_visual_accepted: false` record. Which exact claim belongs to which version is **UNKNOWN**; the original's assertion of a same-scope contradiction is withdrawn.

All other content is unchanged. Next: the per-ROI measurement recipe and its inputs (in progress), source only, with no CPU/GPU run until a fresh grant.
