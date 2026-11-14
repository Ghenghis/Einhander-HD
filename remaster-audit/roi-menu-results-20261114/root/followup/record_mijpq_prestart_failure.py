from pathlib import Path
import datetime,hashlib,json,psutil
n=Path(__file__).resolve().parent;r=Path('C:/github/Einhander')
actual=r/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/tools/run_rc2.py'
saved=n/'region-o-roi-composition-r1/run_rc2.py';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(saved)=='cd3988af06cd348cdef0c9a14e6a87a180b5aea09bb6207eeeb9d3d80a4ea9dd'
out=n/'mijpq-roi-composition-r1';assert not (out/'rc.json').exists()
assert not (r/'remaster-audit/dev-center-evidence/stage1-completion-20261112/world-integrated-mijpq-roi-r1').exists()
result=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),outer_exit=1,failed_assertion='Shared worktree guard hash no longer matches reviewed cd3988af',actual_guard_sha256=sha(actual),preserved_reviewed_guard_sha256=sha(saved),failure_before_popen=True,composition_child_started=False,output_candidate_exists=False,gpu_run=False,grant_returned=True,requires_fresh_grant=True)
(out/'prestart-failure.json').write_text(json.dumps(result,indent=2)+'\n');(out/'attempted-runner.py').write_bytes((n/'run_mijpq_roi_composition.py').read_bytes())
s=(n/'run_mijpq_roi_composition.py').read_text();s=s.replace("out=n/'mijpq-roi-composition-r1'","out=n/'mijpq-roi-composition-r2'")
s=s.replace("guard=r/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/tools/run_rc2.py'", "guard=n/'region-o-roi-composition-r1/run_rc2.py'")
(n/'run_mijpq_roi_composition_r2.py').write_text(s,encoding='utf-8',newline='\n')
s=(n/'run_mijpq_native_admission.py').read_text();s=s.replace("guard=r/'.claude/worktrees/einhander-stages-6-7-0849db/remaster-audit/claude-einhander-primary/tools/run_rc2.py'", "guard=n/'region-o-roi-composition-r1/run_rc2.py'")
(n/'run_mijpq_native_admission_r2.py').write_text(s,encoding='utf-8',newline='\n')
print(json.dumps(result))
