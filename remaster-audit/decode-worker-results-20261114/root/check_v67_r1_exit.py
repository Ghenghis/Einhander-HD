from pathlib import Path
import datetime,json,psutil
n=Path(__file__).resolve().parent;rows=[]
for pid,created in [(1120,1794669889.724),(31968,1794669891.0584211)]:
    row=dict(pid=pid,recorded_creation_unix=created)
    try:
        p=psutil.Process(pid);actual=p.create_time()
        row.update(current_creation_unix=actual,same_identity=abs(actual-created)<.01,original_absent=abs(actual-created)>=.01,current_name=p.name())
    except psutil.NoSuchProcess:row.update(original_absent=True,current_pid_present=False)
    rows.append(row)
receipt=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),observations=rows,processes_terminated=False,prior_outer_exit=1)
(n/'v67-r1-exit-followup.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))
