from pathlib import Path
import datetime,hashlib,json,shutil
out=Path('C:/github/Einhander/remaster-audit/dev-center-evidence/stage1-completion-20261112/sampling-build-v67-decode-identity-r2')
assert not (out/'build.json').exists()
archive=out/'before-growth-fix';archive.mkdir(exist_ok=False)
for name in ['src/debug_server.c','counter-handler.inc','counter-handler-test.c','prepared.json']:
    dst=archive/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(out/name,dst)
h=out/'counter-handler.inc';s=h.read_text(encoding='utf-8')
assert s.count('uint64_t v[TOTAL]')==1 and s.count('gl_renderer_class_mips_counters(v,TOTAL)')==1
s=s.replace('uint64_t v[TOTAL]','uint64_t v[TOTAL+1]').replace('gl_renderer_class_mips_counters(v,TOTAL)','gl_renderer_class_mips_counters(v,TOTAL+1)')
h.write_text(s,encoding='utf-8',newline='\n')
debug=out/'src/debug_server.c';old=(archive/'counter-handler.inc').read_text(encoding='utf-8');text=debug.read_text(encoding='utf-8');assert text.count(old)==1;debug.write_text(text.replace(old,s),encoding='utf-8',newline='\n')
t=out/'counter-handler-test.c';text=t.read_text(encoding='utf-8')
text=text.replace('static int forced_count=-999;','static int forced_count=-999, grown_contract=0;')
text=text.replace('    int n=actual_class_mips_counters(out,cap);','    if(grown_contract){int n=cap<99?cap:99;for(int i=0;i<n;i++)out[i]=(uint64_t)i;return n;}\n    int n=actual_class_mips_counters(out,cap);')
text=text.replace('    for(int i=0;i<4;i++){','    grown_contract=1;handle_hd_class_mips(13,"{}");grown_contract=0;\n    for(int i=0;i<4;i++){')
t.write_text(text,encoding='utf-8',newline='\n')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
prep=json.loads((out/'prepared.json').read_text(encoding='utf-8'));prep['sources']['src/debug_server.c']=sha(debug);prep['counter_handler_sha256']=sha(h);prep['counter_test_sha256']=sha(t)
prep['growth_fix']=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_review_sha256='8f3b988380889834e1c9d9b351ba72524ff77e845a8ceeef7e2af48035c5984b',request_capacity=99,required_count=98,real_cap_honouring_growth_control=True,prior_unbuilt_source_preserved='before-growth-fix')
(out/'prepared.json').write_text(json.dumps(prep,indent=2)+'\n',encoding='utf-8');print(json.dumps(prep['growth_fix']))
