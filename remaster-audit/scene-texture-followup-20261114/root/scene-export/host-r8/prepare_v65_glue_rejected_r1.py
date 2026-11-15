from pathlib import Path
n=Path(__file__).resolve().parent
s=(n/'run_runtime_glue.py').read_text()
s=s.replace('sampling-build-v64-scene-capture-r2','sampling-build-v65-word-sources-r1')
s=s.replace('runtime-glue-r1','runtime-glue-r2')
s=s.replace('2bfb715fca71fff81f70d2e4d1acd61f1e83ddd1f803663467a528b5800972c5','765a6a21ce614597c38bdd0c6b1c29ec0135cef15202d2610c53f6a835eb571f')
s=s.replace('seed(0x24,100);scene_runtime_tick(101);scene_runtime_command(101,words,count,0x1000,&state);scene_runtime_tick(102);',
'''seed(0x24,100);uint32_t sources[12];for(int j=0;j<12;++j)sources[j]=0x4000-uint32_t(j)*4;
    for(int j=0;j<3;++j)addresses[j]=sources[1+j*2];
    scene_runtime_tick(101);scene_runtime_command(101,words,count,sources,&state);scene_runtime_tick(102);''')
a='request("{\\\\\\"index\\\\\\":1024}");request("{\\\\\\"cancel\\\\\\":1}");'
# Use a clear raw-string anchor matching the generator text exactly.
a=r'request("{\\\"index\\\":1024}");request("{\\\"cancel\\\":1}");'
assert s.count(a)==1
s=s.replace(a,a+'\n    scene_runtime_invalidate();request("{}");',1)
s=s.replace('len(lines)==6','len(lines)==7')
s=s.replace("assert not lines[4]['ok'] and lines[5]['mode']==1 and lines[5]['count']==0", "assert not lines[4]['ok'] and lines[5]['mode']==1 and lines[5]['count']==0\nassert lines[6]['mode']==1 and lines[6]['count']==0\nassert lines[3]['record']['word_sources']==[0x4000-j*4 for j in range(7)]")
s=s.replace('rpc_cases=8','rpc_cases=9')
compile(s,'run_runtime_glue_v65.py','exec')
(n/'run_runtime_glue_v65.py').write_text(s)
print('Prepared v65 exact handler/Windows adapter replay')
