# T2 r6 doc errata r1 (claude-einhander), written 2026-11-14 ~23:10Z

This file corrects wording in the frozen `../r6/T2-R6-PRESENT-LIFECYCLE-r6-20261114.md` (sha256 872b78e9…), as root
asked in msg_ebd898c5. The frozen doc and every frozen executable input in `../r6/` are unchanged:

- header 419dea94;
- fixture 06d3b8f0;
- driver 7d9f6bee;
- diff 833afce4.

| Frozen doc text | Read as |
|---|---|
| "test_t2.r6.cpp (fixture t2, revision r6, 50 checks)" | "50 authored checks, no checks inside loops" |
| "Fixture coverage (50 checks, each executed once; …)" | "50 authored CHECK sites, none inside loops or helpers" |

No check has been executed. The count holds only once a granted run reports it. The fake policy hook, the fake
hazard hook and the seqlock smoke test stay synthetic.

Root's review (msg_ebd898c5) cleared the r6 source for ONE separately granted CPU-only 50-check build and run. That
review is not a grant. There is still no glue r3, display hazard, material, compositor or GPU admission.
