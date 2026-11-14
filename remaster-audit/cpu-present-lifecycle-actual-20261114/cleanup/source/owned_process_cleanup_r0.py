"""Exact owned-process cleanup for audited adapter qualification (claude-einhander-support,
EIN-SUPPORT-LIVE-CLEANUP-R0-20261114). PRIVATE, NOT canonical. AUTHORED, NOT EXECUTED.

This closes the item root left open in msg_5d746412: run_audited_qualification (collector r1 9f455093) keeps its
`process` parameter, and dropping the observation alone does not prove that the Windows PID is gone. Collector r1
and its 41 pure controls are UNCHANGED. For live use, run_owned_qualification() below supersedes r1's
run_audited_qualification(), which must not be used for a live qualification.

OwnedProcessHolder(popen, job_active_processes=None) is the SOLE owner of the caller's Popen. Create it as
    holder = OwnedProcessHolder(subprocess.Popen(...), job_active_processes=<qualified outer Job readback>)
and keep no other reference to the Popen. holder.cleanup() returns exactly the cleanup_verdict() contract
    {owned_pid, owned_identity, identity_absent, tree_absent, method}
and keeps the evidence in holder.facts. It proceeds as follows:
  1. Record the owned identity's descendants (pid, create_time), if they can be enumerated.
  2. Kill the owned process if it is still running, and kill each recorded descendant whose pid AND create_time still
     match. Nothing else is ever stopped.
  3. Wait, bounded by ONE shared deadline, and record the retained-handle exit facts.
  4. Drop this holder's Popen and run gc. A weakref then shows whether ANY alias still retains it. A retained alias
     means identity_absent is False, because Windows can keep an exited identity visible while a handle is open.
  5. Run a bounded absence poll for the owned identity and every recorded descendant. ONLY NoSuchProcess, PID absence
     or a different creation time proves absence. AccessDenied or any other psutil error does not.
  6. tree_absent also requires the caller's qualified outer Job to report exactly 0 active processes. Without that
     readback tree_absent is False (fail closed): descendants created after the snapshot, or re-parented ones, cannot
     otherwise be ruled out.
"""
from __future__ import annotations

import gc
import subprocess
import time
import weakref

import psutil

import owned_gl_adapter_observation_audited_r1 as audited

METHOD = ('OwnedProcessHolder r0: kill owned process and recorded owned descendants; release every Popen alias '
          '(weakref) and gc; bounded pid+create_time absence; qualified Job active_processes == 0')


def _absent_once(pid, create_time):
    try:
        if not psutil.pid_exists(pid):
            return True
        return psutil.Process(pid).create_time() != create_time
    except psutil.NoSuchProcess:
        return True
    except psutil.Error:
        return False                                  # AccessDenied etc. is NOT proof of absence


def _wait_absent(pid, create_time, deadline):
    verdict = _absent_once(pid, create_time)
    while not verdict and time.monotonic() < deadline:
        time.sleep(min(0.025, max(0.0, deadline - time.monotonic())))
        verdict = _absent_once(pid, create_time)
    return verdict


def _descendants(pid, create_time, facts):
    try:
        root = psutil.Process(pid)
        if root.create_time() != create_time:
            facts['descendant_note'] = 'owned identity already gone or reused before enumeration'
            return []
        children = root.children(recursive=True)
    except psutil.NoSuchProcess:
        facts['descendant_note'] = 'owned process exited before enumeration; the Job readback is the tree proof'
        return []
    except psutil.Error as error:
        facts['descendant_error'] = type(error).__name__ + ': ' + str(error)
        return []
    found = []
    for child in children:
        try:
            found.append((child.pid, child.create_time()))
        except psutil.NoSuchProcess:
            pass                                      # already gone; nothing to stop or poll
        except psutil.Error as error:
            facts.setdefault('descendant_errors', []).append(type(error).__name__ + ': ' + str(error))
    facts['descendants_enumerated'] = True
    return found


def _kill_if_same(pid, create_time, facts):
    try:
        process = psutil.Process(pid)
        if process.create_time() == create_time:     # never stop a reused PID
            process.kill()
            facts.setdefault('descendants_signaled', []).append(pid)
    except psutil.NoSuchProcess:
        pass
    except psutil.Error as error:
        facts.setdefault('descendant_kill_errors', []).append(f'{pid}: {type(error).__name__}: {error}')


class OwnedProcessHolder:
    def __init__(self, popen, *, job_active_processes=None):
        if not isinstance(popen, subprocess.Popen):
            raise TypeError('OwnedProcessHolder requires the retained subprocess.Popen')
        if job_active_processes is not None and not callable(job_active_processes):
            raise TypeError('job_active_processes must be a callable returning the qualified Job active count')
        self._proc = popen
        self._ref = weakref.ref(popen)
        self.pid = popen.pid
        self.create_time = psutil.Process(self.pid).create_time()   # errors propagate; the caller's Job still owns it
        self._job_active_processes = job_active_processes
        self.facts = {}
        self.cleaned = False

    @property
    def identity(self):
        return (self.pid, self.create_time)

    @property
    def process(self):
        if self._proc is None:
            raise RuntimeError('owned process already released by cleanup')
        return self._proc

    def cleanup(self, deadline_s=3.0):
        if self.cleaned:
            raise RuntimeError('owned cleanup already performed')
        self.cleaned = True
        deadline = time.monotonic() + deadline_s          # ONE shared deadline for every wait below
        facts = self.facts
        facts['descendants_enumerated'] = False
        descendants = _descendants(self.pid, self.create_time, facts)
        facts['descendants_recorded'] = [list(d) for d in descendants]
        proc = self._proc
        facts['exited_before_cleanup'] = proc.poll() is not None
        if not facts['exited_before_cleanup']:
            proc.kill()
            facts['signaled'] = True
        for pid, create_time in descendants:
            _kill_if_same(pid, create_time, facts)
        left = deadline - time.monotonic()
        if left > 0 and proc.poll() is None:
            try:
                proc.wait(timeout=left)
            except subprocess.TimeoutExpired:
                pass
        facts['retained_handle_exited'] = proc.poll() is not None
        facts['returncode'] = proc.returncode
        proc = None
        self._proc = None                                 # drop this holder's alias, then prove nobody else holds one
        gc.collect()
        facts['popen_aliases_released'] = self._ref() is None
        owned_absent = (facts['popen_aliases_released'] and facts['retained_handle_exited']
                        and _wait_absent(self.pid, self.create_time, deadline))
        facts['descendants_absent'] = {f'{p}:{c}': _wait_absent(p, c, deadline) for p, c in descendants}
        job = None
        if self._job_active_processes is not None:
            try:
                job = self._job_active_processes()
            except Exception as error:  # noqa: BLE001 - recorded; tree absence then stays unproven
                facts['job_readback_error'] = type(error).__name__ + ': ' + str(error)
        facts['job_active_processes'] = job
        tree_absent = (owned_absent and all(facts['descendants_absent'].values())
                       and type(job) is int and job == 0)
        return dict(owned_pid=self.pid, owned_identity=[self.pid, self.create_time],
                    identity_absent=bool(owned_absent), tree_absent=bool(tree_absent), method=METHOD)


def run_owned_qualification(*, report, holder, executable, debug_port, stdout_path, expected_model):
    """Live-use replacement for r1 run_audited_qualification. The observation gets the Popen only through the holder,
    and is dropped before cleanup. Cleanup is the holder's own exact cleanup, ALWAYS run, and judged by r1's
    cleanup_verdict. passed requires a passed receipt AND a 'proven' cleanup."""
    result = dict(passed=False, cleanup=None)
    observation = None
    try:
        if not isinstance(holder, OwnedProcessHolder):
            raise audited.AdapterEvidenceError('OwnedProcessHolder required for live qualification')
        observation = audited.AuditedOwnedGlAdapterObservation(
            report=report, process=holder.process, executable=executable, debug_port=debug_port,
            stdout_path=stdout_path, expected_model=expected_model)
        if tuple(observation.identity) != tuple(holder.identity):
            raise audited.AdapterEvidenceError('observation identity differs from the owned holder identity')
        observation.sample()
        observation.sample()
        result['receipt'] = observation.finish()
    except Exception as caught:  # noqa: BLE001 - every failure is a recorded FAIL; cleanup below still runs
        result['error'] = type(caught).__name__ + ': ' + str(caught)
        partial = getattr(caught, 'receipt', None)
        if partial is not None:
            result['partial_receipt'] = partial
    finally:
        expected_identity = getattr(observation, 'identity', None)
        observation = None                                # the observation retains .process: drop it first
        if isinstance(holder, OwnedProcessHolder):
            try:
                record = holder.cleanup()
            except Exception as caught:  # noqa: BLE001 - recorded; never hides the qualification outcome
                result['cleanup'] = dict(status='failed', detail='owned cleanup raised ' + type(caught).__name__
                                         + ': ' + str(caught), facts=audited._json_safe(holder.facts))
            else:
                status, detail = audited.cleanup_verdict(record, holder.pid,
                                                         expected_identity if expected_identity is not None
                                                         else holder.identity)
                result['cleanup'] = dict(status=status, detail=detail, record=audited._json_safe(record),
                                         facts=audited._json_safe(holder.facts))
        else:
            result['cleanup'] = dict(status='failed', detail='no OwnedProcessHolder: owned cleanup cannot be proven')
    result['passed'] = ('error' not in result and (result.get('cleanup') or {}).get('status') == 'proven'
                        and (result.get('receipt') or {}).get('passed') is True)
    return result
