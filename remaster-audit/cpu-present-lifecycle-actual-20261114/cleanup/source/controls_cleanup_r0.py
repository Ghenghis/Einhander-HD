#!/usr/bin/env python3
"""Pure controls for OwnedProcessHolder / owned_process_cleanup_r0.py 8aff5a5a (claude-einhander-support,
EIN-SUPPORT-OWNED-CLEANUP-HOLDER-2254).

AUTHORED, NOT EXECUTED. Run only under a fresh grant naming a CPU, for example inside envelope r1:
  python -B -I controls_cleanup_r0.py --out <new dir> --cpu <granted cpu>

Doubles ONLY: a fake process table (FakeProc / fake psutil) and a fake Popen whose poll/kill/wait operate on a scenario
dict. NOTHING real is created, killed, connected or run. No real process is ever stopped. The cleanup module is
executed from the exact bytes that were hashed. The holder's cleanup() contract is exercised through its RETURN record
and recorded facts; the OS behaviour it models (real PID absence, real Job emptiness) is NOT exercised here and needs a
granted run of the real stub/envelope.

Exit codes: 0 = exactly EXPECTED_CASES recorded and all ok; 1 = any failure; 2 = pins, usage, flags or affinity."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import types
from pathlib import Path

import psutil

ROOT = Path('C:/github/Einhander/remaster-audit')
BINDING = Path('C:/github/Einhander/.claude/worktrees/goofy-babbage-872e5d/remaster-audit/claude-einhander-support/adapter-binding')
ID_GUARD = ROOT / 'gl_adapter_identity_guard.py'
VAR_GUARD = BINDING / 'unassisted_command_guard_adapter_r1.py'
AUD_COLLECTOR = BINDING / 'owned_gl_adapter_observation_audited_r1.py'
CLEANUP = BINDING / 'owned_process_cleanup_r0.py'
PINS = {ID_GUARD: 'c78300cbe563fd8861be25898d3ab2fd88ffb919c0877b0acaa3ec1de1b3eb08',
        VAR_GUARD: '05f7f7d17767714734bb1510b0d0da09107389595ff116fec83230ef9bb3bcee',
        AUD_COLLECTOR: '9f4550930ee5a980b89c62b00c6dcea966ccf10ff4f93036d8c5726993723b9c',
        CLEANUP: '8aff5a5a44a1bdc63e3e65731366f10d40a5e160d8b7e77fb99d97199ea88d84'}
EXPECTED_CASES = 14
OWNED, FOREIGN, CHILD = 5000, 6000, 5001
CT = 1731700000.5


def sha(data):
    return hashlib.sha256(data).hexdigest()


def outcome(fn):
    try:
        return 'pass', fn()
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as exc:  # noqa: BLE001 - classified per case
        return 'raise', exc


def describe(status, value):
    return f'{type(value).__name__}: {str(value)[:200]}' if status == 'raise' else 'returned'


def exec_module(name, path, data):
    mod = types.ModuleType(name)
    mod.__file__ = str(path)
    sys.modules[name] = mod
    exec(compile(data, str(path), 'exec'), mod.__dict__)
    return mod


# ---- fake process table -------------------------------------------------------------------------------------
class NoSuchProcess(Exception):
    pass


class FakeError(Exception):
    pass


class AccessDenied(FakeError):
    pass


class FakeProc:
    def __init__(self, pid, reg):
        self.pid, self._reg = pid, reg

    def _ctime(self, entry):
        seq = entry.get('ctime_seq')
        if seq:
            return seq.pop(0) if len(seq) > 1 else seq[0]
        return entry['ctime']

    def create_time(self):
        entry = self._reg.get(self.pid)
        if entry is not None and entry.get('access_denied'):
            raise AccessDenied(self.pid)
        if entry is None or not entry['alive']:
            raise NoSuchProcess(self.pid)
        return self._ctime(entry)

    def children(self, recursive=False):
        entry = self._reg.get(self.pid)
        if entry is None or not entry['alive']:
            raise NoSuchProcess(self.pid)
        return [FakeProc(c, self._reg) for c in entry.get('children', [])
                if self._reg.get(c, {}).get('alive')]

    def kill(self):
        entry = self._reg.get(self.pid)
        if entry is not None:
            entry['alive'] = False


def fake_psutil(reg):
    return types.SimpleNamespace(
        Process=lambda pid: FakeProc(pid, reg),
        pid_exists=lambda pid: bool(reg.get(pid, {}).get('alive')),
        NoSuchProcess=NoSuchProcess, Error=FakeError, AccessDenied=AccessDenied,
        BELOW_NORMAL_PRIORITY_CLASS=16384)


class PsutilShim:
    """Installs a fake psutil on the cleanup module only; always restored."""
    def __init__(self, mod, reg):
        self.mod, self.reg = mod, reg

    def __enter__(self):
        self.saved = self.mod.psutil
        self.mod.psutil = fake_psutil(self.reg)
        return self

    def __exit__(self, *exc):
        self.mod.psutil = self.saved
        return False


def fake_popen(pid, reg, *, running, stoppable=True):
    """A REAL subprocess.Popen instance (for isinstance) whose poll/kill/wait use a scenario dict only; the closures
    never capture the Popen, so the holder's weakref guard can see it released."""
    process = subprocess.Popen.__new__(subprocess.Popen)
    process.pid = pid
    process.returncode = 0
    process._child_created = False                 # makes Popen.__del__ a no-op
    state = {'running': running}

    def poll(_state=state):
        return None if _state['running'] else 0

    def kill(_state=state, _reg=reg, _pid=pid, _stop=stoppable):
        if _stop:
            _state['running'] = False
            entry = _reg.get(_pid)
            if entry is not None:
                entry['alive'] = False

    def wait(timeout=None, _state=state):
        if _state['running']:
            raise subprocess.TimeoutExpired('owned', timeout)
        return 0

    process.poll, process.kill, process.wait = poll, kill, wait
    return process


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--cpu', type=int, required=True)
    a = ap.parse_args()
    own = Path(__file__).read_bytes()
    if not sys.flags.isolated or sys.flags.optimize:
        print('refusing: run with python -B -I and without -O', file=sys.stderr)
        return 2
    blobs = {p: p.read_bytes() for p in PINS}
    got = {str(p): sha(b) for p, b in blobs.items()}
    bad = [str(p) for p in PINS if got[str(p)] != PINS[p]]
    if bad:
        print(json.dumps(dict(pin_mismatch=bad, got=got)), file=sys.stderr)
        return 2
    me = psutil.Process()
    allowed = sorted(me.cpu_affinity())
    if a.cpu not in allowed:
        print(f'refusing: --cpu {a.cpu} not in allowed affinity {allowed}', file=sys.stderr)
        return 2
    me.cpu_affinity([a.cpu])
    me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    res = dict(schema='support-owned-cleanup-controls-r0', pins=got, controls_sha256=sha(own), cpu=a.cpu,
               allowed_affinity=allowed, python=sys.version, psutil=psutil.__version__, cases=[],
               started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               note='process doubles only; no real process created, killed or run; models the holder RETURN contract, '
                    'not real OS absence')
    try:
        exec_module('gl_adapter_identity_guard', ID_GUARD, blobs[ID_GUARD])
        exec_module('unassisted_command_guard_adapter_r1', VAR_GUARD, blobs[VAR_GUARD])
        exec_module('owned_gl_adapter_observation_audited_r1', AUD_COLLECTOR, blobs[AUD_COLLECTOR])
        cleanup = exec_module('owned_process_cleanup_r0', CLEANUP, blobs[CLEANUP])
        run_all(cleanup, out, res)
    except Exception as exc:  # noqa: BLE001 - recorded, never a pass
        res['fatal'] = f'{type(exc).__name__}: {exc}'
    res['elapsed_s'] = round(time.monotonic() - started, 3)
    res['case_count'] = len(res['cases'])
    res['expected_cases'] = EXPECTED_CASES
    res['all_ok'] = ('fatal' not in res and res['case_count'] == EXPECTED_CASES
                     and all(c.get('ok') is True for c in res['cases']))
    payload = json.dumps(res, indent=1, allow_nan=False, ensure_ascii=True, default=str) + '\n'
    with (out / 'result.json').open('x', encoding='utf-8') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    print(json.dumps(dict(all_ok=res['all_ok'], case_count=res['case_count'], fatal=res.get('fatal'),
                          failed=[c['case'] for c in res['cases'] if c.get('ok') is not True])))
    return 0 if res['all_ok'] else 1


def run_all(cleanup, out, res):
    Holder = cleanup.OwnedProcessHolder
    audited = sys.modules['owned_gl_adapter_observation_audited_r1']

    def case(name, fn):
        row = dict(case=name, ok=False)
        res['cases'].append(row)
        try:
            ok, detail = fn()
            row.update(ok=bool(ok), detail=detail)
        except Exception as exc:  # noqa: BLE001 - a broken oracle is a failure
            row['why'] = f'{type(exc).__name__}: {exc}'

    def reg(**owned):
        base = dict(alive=True, ctime=CT, children=[])
        base.update(owned)
        return {OWNED: base}

    def job(n):
        return lambda: n

    # H1: clean owned exit, no descendants, Job 0 -> identity and tree absent.
    def h1():
        r = reg(alive=False)
        with PsutilShim(cleanup, r):
            holder = Holder(fake_popen(OWNED, r, running=False), job_active_processes=job(0))
            rec = holder.cleanup(deadline_s=0.5)
        ok = (rec['owned_pid'] == OWNED and rec['owned_identity'] == [OWNED, CT]
              and rec['identity_absent'] is True and rec['tree_absent'] is True
              and holder.facts['popen_aliases_released'] is True
              and holder.facts['retained_handle_exited'] is True
              and set(rec) == {'owned_pid', 'owned_identity', 'identity_absent', 'tree_absent', 'method'})
        return ok, json.dumps(rec, default=str)
    case('H1_clean_exit_no_descendants_identity_and_tree_absent', h1)

    # H2: owned still running with one descendant; both killed and proven absent; Job 0.
    def h2():
        r = reg(running_ok=True, children=[CHILD])
        r[OWNED]['alive'] = True
        r[CHILD] = dict(alive=True, ctime=CT + 1, children=[])
        with PsutilShim(cleanup, r):
            holder = Holder(fake_popen(OWNED, r, running=True), job_active_processes=job(0))
            rec = holder.cleanup(deadline_s=0.5)
        f = holder.facts
        ok = (rec['identity_absent'] is True and rec['tree_absent'] is True
              and f.get('signaled') is True and f.get('descendants_signaled') == [CHILD]
              and f['descendants_recorded'] == [[CHILD, CT + 1]]
              and all(f['descendants_absent'].values()))
        return ok, json.dumps(f.get('descendants_absent'), default=str)
    case('H2_running_descendant_killed_and_absent_tree_absent', h2)

    # H3: everything absent but the qualified Job still reports active -> tree NOT absent (fail closed).
    def h3():
        r = reg(alive=False)
        with PsutilShim(cleanup, r):
            holder = Holder(fake_popen(OWNED, r, running=False), job_active_processes=job(2))
            rec = holder.cleanup(deadline_s=0.5)
        return (rec['identity_absent'] is True and rec['tree_absent'] is False
                and holder.facts['job_active_processes'] == 2), json.dumps(rec, default=str)
    case('H3_nonzero_job_active_tree_not_absent', h3)

    # H4: no Job readback callable -> tree cannot be proven absent.
    def h4():
        r = reg(alive=False)
        with PsutilShim(cleanup, r):
            holder = Holder(fake_popen(OWNED, r, running=False), job_active_processes=None)
            rec = holder.cleanup(deadline_s=0.5)
        return (rec['identity_absent'] is True and rec['tree_absent'] is False
                and holder.facts['job_active_processes'] is None), json.dumps(rec, default=str)
    case('H4_missing_job_readback_tree_not_absent', h4)

    # H5: AccessDenied on the owned identity is NOT proof of absence (fail closed).
    def h5():
        r = reg(alive=True)
        with PsutilShim(cleanup, r):
            holder = Holder(fake_popen(OWNED, r, running=False), job_active_processes=job(0))
            r[OWNED]['access_denied'] = True            # flips after construction
            rec = holder.cleanup(deadline_s=0.2)
        return (rec['identity_absent'] is False and rec['tree_absent'] is False), json.dumps(rec, default=str)
    case('H5_access_denied_not_absent_fail_closed', h5)

    # H6: a reused PID (different creation time) counts as absent.
    def h6():
        r = reg(alive=True, ctime=CT + 99)              # same pid, different ctime than construction
        with PsutilShim(cleanup, r):
            holder = Holder(fake_popen(OWNED, r, running=False), job_active_processes=job(0))
            holder.create_time = CT                      # construction observed CT; registry now CT+99
            rec = holder.cleanup(deadline_s=0.5)
        return (rec['owned_identity'] == [OWNED, CT] and rec['identity_absent'] is True
                and rec['tree_absent'] is True), json.dumps(rec, default=str)
    case('H6_reused_pid_different_ctime_is_absent', h6)

    # H7: an external alias of the owned Popen is still held -> absence NOT proven.
    def h7():
        r = reg(alive=False)
        kept = fake_popen(OWNED, r, running=False)
        with PsutilShim(cleanup, r):
            holder = Holder(kept, job_active_processes=job(0))
            rec = holder.cleanup(deadline_s=0.5)
        ok = (holder.facts['popen_aliases_released'] is False and rec['identity_absent'] is False
              and rec['tree_absent'] is False)
        return ok, f"aliases_released={holder.facts['popen_aliases_released']}"
    case('H7_retained_external_alias_not_absent', h7)

    # H8: owned process does not stop within the deadline -> retained handle not exited -> not absent.
    def h8():
        r = reg(alive=True)
        with PsutilShim(cleanup, r):
            holder = Holder(fake_popen(OWNED, r, running=True, stoppable=False), job_active_processes=job(0))
            rec = holder.cleanup(deadline_s=0.3)
        return (holder.facts['retained_handle_exited'] is False and rec['identity_absent'] is False
                and rec['tree_absent'] is False), json.dumps(rec, default=str)
    case('H8_stuck_process_retained_handle_not_exited_not_absent', h8)

    # H9: a descendant whose creation time changed between record and kill is NEVER stopped.
    def h9():
        r = reg(running=True, children=[CHILD])
        r[OWNED]['alive'] = True
        r[CHILD] = dict(alive=True, ctime_seq=[CT + 1, CT + 2, CT + 2], children=[])  # record, kill-check, poll
        with PsutilShim(cleanup, r):
            holder = Holder(fake_popen(OWNED, r, running=True), job_active_processes=job(0))
            rec = holder.cleanup(deadline_s=0.5)
        f = holder.facts
        ok = (CHILD not in (f.get('descendants_signaled') or [])
              and f['descendants_recorded'] == [[CHILD, CT + 1]]
              and f['descendants_absent'].get(f'{CHILD}:{CT + 1}') is True)
        return ok, json.dumps(dict(signaled=f.get('descendants_signaled'), absent=f.get('descendants_absent')),
                              default=str)
    case('H9_reused_descendant_pid_never_killed', h9)

    # H10: construction requires a real retained Popen.
    def h10():
        st, val = outcome(lambda: Holder('not-a-popen', job_active_processes=None))
        return st == 'raise' and type(val) is TypeError, describe(st, val)
    case('H10_requires_retained_popen', h10)

    # H11: the Job readback must be callable.
    def h11():
        r = reg(alive=False)
        with PsutilShim(cleanup, r):
            st, val = outcome(lambda: Holder(fake_popen(OWNED, r, running=False), job_active_processes=5))
        return st == 'raise' and type(val) is TypeError, describe(st, val)
    case('H11_job_active_processes_must_be_callable', h11)

    # H12: cleanup cannot run twice.
    def h12():
        r = reg(alive=False)
        with PsutilShim(cleanup, r):
            holder = Holder(fake_popen(OWNED, r, running=False), job_active_processes=job(0))
            holder.cleanup(deadline_s=0.5)
            st, val = outcome(lambda: holder.cleanup(deadline_s=0.5))
        return st == 'raise' and type(val) is RuntimeError and 'already performed' in str(val), describe(st, val)
    case('H12_double_cleanup_refused', h12)

    # H13: the clean record satisfies the shared cleanup_verdict contract; a foreign pid does not.
    def h13():
        r = reg(alive=False)
        with PsutilShim(cleanup, r):
            holder = Holder(fake_popen(OWNED, r, running=False), job_active_processes=job(0))
            rec = holder.cleanup(deadline_s=0.5)
        proven = audited.cleanup_verdict(rec, OWNED, (OWNED, CT))
        foreign = audited.cleanup_verdict(rec, FOREIGN, (FOREIGN, CT))
        return proven[0] == 'proven' and foreign[0] == 'failed', f'{proven[0]}/{foreign[0]}'
    case('H13_record_satisfies_cleanup_verdict_only_for_owned', h13)

    # H14: run_owned_qualification refuses to prove cleanup without a holder.
    def h14():
        base = out / 'H14'
        base.mkdir()
        (base / 'startup.log').write_bytes(b'FIXTURE\n')
        result = cleanup.run_owned_qualification(
            report=dict(evidence=str(base), command_phase='adapter-qualification',
                        adapter_profile='adapter-qualification-v1',
                        visual_profile=dict(timer_only_assistance=False)),
            holder=None, executable=Path(sys.executable), debug_port=47001,
            stdout_path=base / 'startup.log', expected_model='FIXTURE')
        c = result.get('cleanup') or {}
        return (result['passed'] is False and c.get('status') == 'failed'
                and 'no OwnedProcessHolder' in c.get('detail', '')), json.dumps(c, default=str)
    case('H14_run_owned_qualification_requires_holder', h14)


if __name__ == '__main__':
    sys.exit(main())
