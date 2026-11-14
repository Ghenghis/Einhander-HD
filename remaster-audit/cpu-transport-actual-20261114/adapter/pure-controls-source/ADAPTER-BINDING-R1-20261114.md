# Audited adapter binding r1: fixes for root review msg_ca94c6d0 (claude-einhander-support)

- Task: EIN-SUPPORT-AUDIT-BINDING-R1-20261114 (queue: EIN-SUPPORT-BINDING-STUB-R2-20261114).
- Status: **AUTHORED, NOT EXECUTED.** No import, compile, socket, process or test. Only hashing and
  `git diff --no-index` were run.
- Preserved unchanged:
  - r0: guard 1ac7895a, collector d1b72132, controls 52275a7a, note 1f311edb;
  - canonical guard 9e6ca815 and collector c457b58e. The canonical n=1 prohibition is unchanged.

## Files (new)
| file | sha256 | bytes |
|---|---|---|
| `unassisted_command_guard_adapter_r1.py` | 05f7f7d17767714734bb1510b0d0da09107389595ff116fec83230ef9bb3bcee | 20713 |
| `owned_gl_adapter_observation_audited_r1.py` | 9f4550930ee5a980b89c62b00c6dcea966ccf10ff4f93036d8c5726993723b9c | 22883 |
| `controls_binding_r1.py` (41 cases) | 5e88fb9e33a7a774210011c44e7de2a5042b2b78a85d0d4ca9873890f5431371 | 35603 |
| `guard_adapter_r1.vs-9e6ca815.diff` (**0 removed lines**; byte prefix re-verified) | e26935fa004c45e21bd5f8b609cd5056d4e9c1072dc7d43515a18fedafc919fe | 16361 |
| `guard_adapter_r1.vs-r0.diff` | debc48fb02fd3c8972b27ead6c152353aaeb4f4deac0571de5c3b89c6b44706f | 17449 |
| `collector_audited_r1.vs-r0.diff` | 64a1717fa2317fea82572d7d2c98fdad3885a4585eb6b422c742ec77a3a42678 | 9476 |
| `collector_audited_r1.vs-c457b58e.diff` | 9650fe162348c91f190a787cd5f9d2684d2341d85f90b45419c7926bb1a1796e | 17000 |
| `controls_binding_r1.vs-r0.diff` | e48897d7e7890138bbd0d92a0b92f42898e473b1296735a96067ead10aa3daa6 | 16333 |

## The five review items and their fixes
1. **Exact audited binding.**
   - `_write_exclusive` now serializes first, writes **binary** `'xb'` with fsync, and returns the SHA-256 of the
     exact bytes. With no newline translation, the digest equals the file bytes.
   - The ledger keeps per-intent records: intent_id, sequence (counted from written intents), endpoint, identity, peer,
     intent_sha256, receipt_sha256 and state.
   - `audit_commands_adapter` returns `adapter_records`: the exact ordered records with the digests of the file bytes
     it read.
   - `finish()` requires `adapter_records == ledger.audit_records()` (ids, order, owner, endpoint, peer and both
     digests), ids == the sample ids == the ledger ids, and both receipts completed.
   - Control **B18**: replacing the whole directory with two self-consistent, same-owner records under OTHER UUIDs
     still audits clean, but `finish` fails.
2. **Re-check after the durable intent.**
   - Immediately before send, the collector checks deadline > 0, then the retained owned identity, then the deadline
     again.
   - On failure an AdapterEvidenceError is raised, `finally` writes a `transport_failed` receipt with `sent: false`,
     and nothing is sent.
   - Controls: **B19** (slow intent: `before_send` + 0.2 s with RPC 0.1 s) and **B20** (identity changes on the
     post-intent lookup).
3. **Cleanup contract.**
   - `cleanup_verdict(record, expected_pid, expected_identity)`: cleanup() must RETURN exactly
     `{owned_pid, owned_identity, identity_absent, tree_absent, method}`.
   - `owned_pid` must be an int equal to `process.pid`. `owned_identity` must equal the observed identity when one was
     obtained (otherwise None, or the same pid). `identity_absent` and `tree_absent` must be exactly True, and
     `method` a non-empty str.
   - `passed` requires the status `proven`. The observation alias is dropped before cleanup.
   - Controls: **B21a** (False), **B21b** (identity not absent), **B21c** (missing key), **B21d** (wrong pid),
     **B16** (raised), **B5** (success), **B15** (construction failure, still proven).
4. **Strict types.**
   - Exact ints everywhere (`type is int`, so bool and float are rejected) for ports, pids, family and sequence, via
     `_endpoint` and `_identity` inside `_peer`.
   - `decoded` must be exactly True if present. `reply_sha256` must be 64 lowercase hex. `error` must be a str.
   - Controls: **B22a** decoded=1 and **B22b** a non-hex sha are refused by the ledger. **B22c** (decoded int) and
     **B22e** (float port 47001.0) are refused by the audit. **B22d**: a bool pid True is not accepted as owned pid 1.
5. **Outer scope and unreceipted intents.**
   - `_audit_adapter_record` validates against the **outer** report; there is no override. An adapter record under a
     non-adapter outer report is an error (**B23**).
   - Every unreceipted adapter intent is now an **audit error** (**B24**). `finish` also requires
     `adapter_unreceipted == []`.

The r0 cases B1-B17 are carried over, re-pinned to r1 and using `fake_popen()` (Popen.__new__ with `pid` set, so no
process exists).

## Not covered
- The real `_owned_identity` and `_listener` logic (see the owned-stub probe r2, 06f7a44a).
- Any real game, GPU or socket.

## Command, only under a fresh grant naming a CPU after root review
`python -B -I controls_binding_r1.py --out <new dir> --cpu <c>`. Under 1 s, one core.
