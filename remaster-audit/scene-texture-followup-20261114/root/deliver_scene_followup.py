"""Publish only reviewed owned paths and verify actual remote/committed bytes."""
from pathlib import Path
import datetime,hashlib,io,json,os,psutil,shutil,subprocess
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent;w=Path('C:/github/Einhander-wt/display-history-opt-in');p=w/'remaster-audit/scene-texture-followup-20261114'
me=psutil.Process();me.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);me.cpu_affinity(me.cpu_affinity()[-1:])
report='docs/media/gallery/scene-followup-documentation-verification-results.json'
assert json.loads((w/report).read_text())['passed']
assert subprocess.check_output(['git','remote','get-url','origin'],cwd=w,text=True).strip()=='https://github.com/Ghenghis/Einhander-HD.git'
assert subprocess.check_output(['git','branch','--show-current'],cwd=w,text=True).strip()=='codex/display-history-opt-in'
subprocess.run(['git','add','-f','--',report],cwd=w,check=True)
allowed=['.gitattributes','AGENTS.md','coordination/Codex-HANDOFF.md','coordination/Codex-WORK-QUEUE.md',report,'remaster-audit/stage1-completion-20261112/execution-state.json',*['docs/'+x for x in ['4K-REMIX-IMPLEMENTATION-PLAN.md','RTX-REMIX-SETUP-20261114.md','RUNTIME-CONTINUATION-20261113.md','STAGE1-COMPLETION-STATUS.md','STAGE1-SIGN-QUALITY-20261114.md']]]
changed=subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=w).decode().strip('\0').split('\0')
assert changed and all(f in allowed or f.startswith('remaster-audit/scene-texture-followup-20261114/') for f in changed)
subprocess.run(['git','diff','--cached','--check'],cwd=w,check=True)
# Flush our delivered files, then re-read. This is durability effort, not a guarantee against hardware failure.
for rel in changed:
    with (w/rel).open('rb+') as f:os.fsync(f.fileno())
expected={}
for name in ['gpu-integration-20261114','gpu-shader-followup-20261114']:
    d=json.loads((w/'remaster-audit'/name/'SHA256.json').read_text());expected.update({f'remaster-audit/{name}/{f}':h for f,h in d['files'].items()})
for name in ['cpu-hour-integration-20261114','scene-texture-followup-20261114']:
    for line in (w/'remaster-audit'/name/'SHA256SUMS.txt').read_text().splitlines():
        h,f=line.split('  ',1);expected[f'remaster-audit/{name}/'+f]=h
def verify(ref):
    raw=subprocess.check_output(['git','cat-file','--batch'],cwd=w,input=''.join(ref+f+'\n' for f in expected).encode());stream=io.BytesIO(raw)
    for f,h in expected.items():
        hdr=stream.readline().decode().split();assert len(hdr)==3 and hdr[1]=='blob',(f,hdr)
        assert hashlib.sha256(stream.read(int(hdr[2]))).hexdigest()==h,f;assert stream.read(1)==b'\n'
        assert hashlib.sha256((w/f).read_bytes()).hexdigest()==h,f
        assert hashlib.sha256((r/f).read_bytes()).hexdigest()==h,f
    assert stream.read()==b''
verify(':')
msg=n/'scene-followup-commit.txt';msg.write_text('Qualify reviewed scene capture and record SDK/restart results\n\nInclude generation-bound v66 source and actual CPU checks, failed or aborted legacy SDK controls, matching modern runtime table initialization, scoped crash integrity evidence and current Codex continuation/acceptance state. No live scene, ray tracing, DLSS or full remaster acceptance claimed.\n')
subprocess.run(['git','commit','--quiet','-F',str(msg)],cwd=w,check=True,timeout=30)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=w,text=True).strip()
subprocess.run(['git','push','origin','HEAD:refs/heads/codex/display-history-opt-in'],cwd=w,check=True,timeout=30)
remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/codex/display-history-opt-in'],cwd=w,text=True,timeout=30).split()[0]
assert remote==head
assert not subprocess.check_output(['git','status','--porcelain'],cwd=w).strip()
verify('HEAD:')
shutil.copy2(w/report,r/report)
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),head=head,remote_head=remote,delivery_worktree_clean=True,committed_historical_and_new_pins_verified=len(expected),new_packet_pins=len((p/'SHA256SUMS.txt').read_text().splitlines()),root_evidence_copy_matches=True,docs=json.loads((w/report).read_text()),new_gpu_executed=False,new_game_executed=False,scope='Commit/push and hash verification; published packet retains earlier failed GPU controls. Overall project remains incomplete.')
(n/'scene-delivery-verification.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='docs'}))
