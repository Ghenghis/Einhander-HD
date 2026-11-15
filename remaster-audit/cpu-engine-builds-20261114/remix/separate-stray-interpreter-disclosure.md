# Incident: stray ungranted interpreter invocation (claude-einhander), 2026-11-14

**What:** a read-only Bash tool call meant to read the PR7-1-2200 receipt accidentally contained an empty heredoc that
invoked an interpreter. It ran outside any grant and outside the fa5 Job envelope. This was my error.

**Exact command** (single Bash tool call, Git Bash; cwd was the session worktree root):

```text
cat "C:/Users/Admin/AppData/Local/Temp/claude/e5fad2775628cc35/1c56db97-2f5d-4f18-aece-e2a77dbf7a70/tasks/bc43qo4po.output"; R=/c/github/Einhander/.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/remix-probe-r5/runs; python3 - 2>/dev/null <<'EOF' || true
EOF
grep -E '"(child_pid|child_create_time|wrapper_pid|wrapper_create_time|child_exit_code|wrapper_exit|elapsed_s|start_utc|end_utc|system_cpu_pct|free_gib|peak_job_memory_bytes|peak_process_memory_bytes|child_absent|job_empty|tree_absent|declined|timeout_killed)"|descendants' $R/PR7-1-2200-envelope.json; ls -la $R/PR7-1-2200 $R/PR7-1-2200/* 2>&1 | head -30
```
(verbatim, as recorded in the TaskStop result for task bgk4b1e1a)

The heredoc body was empty. `python3` resolves to `C:\Python314\python3.exe` (`Get-Command python3`).

**Known facts:**
- **Start:** shortly after 22:03:12.78Z, when the granted PR7 run finished. The exact start time is UNKNOWN.
- **Behaviour:** the tool call did not complete within the harness's 120 s limit. The harness moved it to background
  task `bgk4b1e1a`, and the call printed nothing beyond the earlier `cat` output.
- **Stop:** I stopped task `bgk4b1e1a` with TaskStop at about 22:05:4xZ; TaskStop reported success.
- **Afterwards:** a process listing at 22:05:54Z showed no `python3.exe` image.
- **Effect:** no script or arguments were given, and no file was written by it, as far as known.

**Unknown (explicitly):**
- the PID of the stray `python3.exe` (and of its bash parent);
- its creation time;
- its exit code;
- whether it exited before TaskStop or was terminated by it;
- its CPU affinity and priority, which was not set: it was not under a Job.

**Not inferred:** PID 40752 (python.exe, parent 26944, empty command line, created 22:05:53Z, absent at 22:06:09Z)
is an unrelated, unowned process. Nothing is inferred about it, and it was not stopped by me.

**Remedy:** no inline interpreters in read-only commands. Reads use cat/grep/sed/sha256sum or PowerShell cmdlets only.
