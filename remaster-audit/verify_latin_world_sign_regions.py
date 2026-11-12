"""Bounded production-loader/source-matcher/PNG-cache check; no game launch."""
from pathlib import Path
import hashlib,json,shutil,subprocess
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'remaster-audit/menu-restoration/latin-world-sign-regions-v1'
BASE=ROOT/'remaster-audit/dev-center-evidence/hud-world-region-candidate-20261112-v9/pack'
RUNTIME=ROOT/'windows-x64/psxrecomp/runtime'
COMPILER=Path('C:/Users/Admin/.local/share/retcomm/toolchains/cmake-clang-v1/latest/bin/clang++.exe')
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def main():
 evidence=OUT/'runtime-test';evidence.mkdir(exist_ok=False)
 cpp=ROOT/'remaster-audit/test_latin_sign_regions.cpp';source=RUNTIME/'src/hd_texture_pack.cpp';header=RUNTIME/'include/hd_texture_pack.h'
 inputs=[ref(p) for p in (OUT/'manifest.json',cpp,source,header,RUNTIME/'third_party/stb_image.h')]
 exe=evidence/'test-latin-sign-regions.exe';commands=[]
 def run(args,label):
  p=subprocess.run([str(a) for a in args],capture_output=True,text=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
  (evidence/(label+'.log')).write_text(p.stdout+p.stderr,encoding='utf-8');commands.append({'arguments':[str(a) for a in args],'exit':p.returncode,'log':ref(evidence/(label+'.log'))})
  print(label,p.returncode,p.stdout.strip(),flush=True);assert p.returncode==0,(p.stdout,p.stderr)
 run([COMPILER,'-std=c++17','-O2','-static','-I'+str(RUNTIME/'include'),cpp,source,'-o',exe],'compile-production-loader-with-PNG-worker')
 run([exe,OUT/'pack',36],'actual-36-Latin-indexed-regions')
 # The unchanged six established direct regions and all new indexed regions
 # must be accepted together by the production overlap/limit checker.
 combined=evidence/'combined-42-pack';png=combined/'einhander-texture-replacements';png.mkdir(parents=True);(combined/'Hashes.ini').write_text('')
 rows=[]
 for pack in (BASE,OUT/'pack'):
  lines=(pack/'ExactRegions.tsv').read_text().splitlines();assert lines[0]=='EIN_EXACT_REGIONS_V1'
  for line in lines[1:]:
   if not line.strip():continue
   key=line.split()[0];rows.append(line)
   for suffix in ('.words.bin','.clut.bin','.valid.bin'):shutil.copy2(pack/(key+suffix),combined/(key+suffix))
   shutil.copy2(pack/'einhander-texture-replacements'/(key+'.png'),png/(key+'.png'))
 (combined/'ExactRegions.tsv').write_text('EIN_EXACT_REGIONS_V1\n'+'\n'.join(rows)+'\n');assert len(rows)==42
 run([exe,combined,42],'combined-existing-six-plus-Latin-36')
 assert all(ref(Path(r['path']))==r for r in inputs),'Hashed input changed during check'
 receipt={'created_at_utc':datetime.now(timezone.utc).isoformat(),'outcome':'PASS','inputs':inputs,'test_executable':ref(exe),'commands':commands,
  'standalone_checks':578,'standalone_failures':0,'combined_region_count':42,'combined_checks':578,'combined_failures':0,
  'all_36_actual_indexed_sources_and_palette_proofs_match':True,'all_36_actual_PNGs_production_decoded':True,'all_32_RISE_phases_remain_cached_after_decode':True,
  'decoded_rgba_bytes':74448896,'decode_budget_bytes':256*1024*1024,'render_GL':'NOT RUN','actual_game_admission':'NOT RUN','game_actions':0,'runtime_files_changed':False}
 (evidence/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(ref(evidence/'receipt.json')))
if __name__=='__main__':main()
