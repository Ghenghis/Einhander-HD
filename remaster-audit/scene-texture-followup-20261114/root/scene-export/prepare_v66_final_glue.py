from pathlib import Path
n=Path(__file__).resolve().parent
s=(n/'run_runtime_glue_v66.py').read_text()
s=s.replace('sampling-build-v66-reviewed-scene-r2','sampling-build-v66-reviewed-scene-r3')
s=s.replace('runtime-glue-v66-r1','runtime-glue-v66-r2')
s=s.replace('6193f454c0d8b37552a6c6930b9921a24715c98d46d25ac05a944c5f0af8b7e6','51ec32e3fdf4fc7567e807bce7106576a51e0c39ae73e65cb0599c33bd6a5a98')
compile(s,'run_runtime_glue_v66_final.py','exec');(n/'run_runtime_glue_v66_final.py').write_text(s)
print('Prepared final v66 exact runtime replay')
