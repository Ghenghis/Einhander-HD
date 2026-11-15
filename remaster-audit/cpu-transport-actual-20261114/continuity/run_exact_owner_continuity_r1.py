"""One granted CPU-only regression run; copied scripts, no active Claude session hooks invoked."""
from pathlib import Path
import argparse, datetime as dt, hashlib, json, os, psutil, subprocess, time

R = Path('C:/github/Einhander')
HERE = Path(__file__).resolve().parent
NODE = Path('C:/Program Files/nodejs/node.exe')
PINS = {
    'claude-continuity-hook.mjs': '7ee73f38ee77cf7179e5b9111a5ad79af12a604de4e0dc93cabcaa03bd566ca4',
    'test-claude-continuity.mjs': '8a30a019b6cec425c47d2ab472b5dfff9f7ec70c25ffc37e6f099473dad7b367',
}

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cpu', type=int, required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--grant-id', required=True)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    if not out.is_relative_to(HERE) or out == HERE:
        raise ValueError('receipt must be a new child directory of this review namespace')
    out.mkdir(exist_ok=False)
    me = psutil.Process()
    me.cpu_affinity([a.cpu]); me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    rec = dict(at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), grant_id=a.grant_id,
               driver_sha256=sha(Path(__file__)), cpu=a.cpu, passed=False,
               gpu_used=False, game_launched=False, native_sessions_invoked=False,
               inherited_job_required=True, job_verified_by_this_driver=False)
    child = None
    try:
        copies = {}
        for name, want in PINS.items():
            src = R/'tools/coordination'/name
            raw = src.read_bytes()
            if hashlib.sha256(raw).hexdigest() != want:
                raise ValueError('source changed: '+name)
            dst = out/name
            with dst.open('xb') as f:
                f.write(raw)
            if sha(dst) != want:
                raise ValueError('copied source changed: '+name)
            copies[name] = dict(original=str(src), copied=str(dst), sha256=want)
        rec['copies'] = copies
        rec['node'] = dict(path=str(NODE), sha256=sha(NODE),
                           pin_recorded_at_execution=True, independently_preapproved_pin=False)
        env = dict(os.environ)
        for k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
            env[k] = '1'
        argv = [str(NODE), '--test', '--test-concurrency=1', '--test-reporter=tap',
                str(out/'test-claude-continuity.mjs')]
        rec.update(argv=argv, cwd=str(out), started_utc=dt.datetime.now(dt.timezone.utc).isoformat())
        started = time.monotonic()
        with (out/'test.tap').open('xb') as log:
            child = subprocess.Popen(argv, cwd=out, env=env, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=subprocess.STDOUT, creationflags=0x08004000)
            rec['pid'] = child.pid
            try:
                rec['creation_unix'] = psutil.Process(child.pid).create_time()
            except psutil.Error:
                rec['creation_unix'] = None
            try:
                rec['exit'] = child.wait(timeout=20)
                rec['timed_out'] = False
            except subprocess.TimeoutExpired:
                rec['timed_out'] = True
                child.kill()
                rec['exit'] = child.wait(timeout=3)
        rec['elapsed_s'] = time.monotonic()-started
        tap = (out/'test.tap').read_text(encoding='utf-8')
        summary = [line for line in tap.splitlines() if line.startswith(('# tests ', '# pass ', '# fail ', '# skipped ', '# cancelled '))]
        rec.update(summary=summary, tap_sha256=sha(out/'test.tap'),
                   passed=rec['exit'] == 0 and not rec['timed_out'] and '# fail 0' in summary
                   and '# cancelled 0' in summary)
    except BaseException as e:
        rec['error'] = type(e).__name__+': '+str(e)
    finally:
        with (out/'result.json').open('x', encoding='utf-8') as f:
            json.dump(rec, f, indent=2); f.write('\n'); f.flush(); os.fsync(f.fileno())
    print(json.dumps(dict(passed=rec['passed'], out=str(out), summary=rec.get('summary'), error=rec.get('error'))))
    return 0 if rec['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
