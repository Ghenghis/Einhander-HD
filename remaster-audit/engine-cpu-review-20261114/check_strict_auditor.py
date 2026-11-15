from pathlib import Path
import hashlib,importlib.util,json,tempfile,zlib,psutil
r=Path('C:/github/Einhander');n=Path(__file__).resolve().parent
src=r/'remaster-audit/claude-backlog/class-audit/audit_native_classes_v2.py'
pin=hashlib.sha256(src.read_bytes()).hexdigest()
psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
spec=importlib.util.spec_from_file_location('strict_class_auditor',src);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
words=bytes.fromhex('1032');clut=b''.join(q.to_bytes(2,'little') for q in [0,1,0x8000,0x7fff]+[1]*12)
key=f'{zlib.crc32(words):08X}-{zlib.crc32(clut):08X}'
checks=[]
with tempfile.TemporaryDirectory(prefix='native-audit-control-',dir=n) as tmp:
 d=Path(tmp)
 def setup(meta=None,valid=None,wb=words,cb=clut):
  for f in d.iterdir():f.unlink()
  (d/(key+'.words.bin')).write_bytes(wb);(d/(key+'.clut.bin')).write_bytes(cb)
  if meta is not None:(d/(key+'.source.json')).write_text(json.dumps(meta))
  if valid is not None:(d/(key+'.valid.bin')).write_bytes(valid)
 def check(label,passed):checks.append({'check':label,'passed':bool(passed)});assert passed,label
 full={'width_words':1,'height':1,'depth':0,'known_words':1,'total_words':1}
 setup(full);a,b=mod.try_dump(d,key,{});check('explicit complete metadata accepted',a is not None);check('4bpp class decode',b.tolist()==[[0,127,255,127]])
 setup({'width_words':1,'height':1,'depth':0});check('missing validity rejected',mod.try_dump(d,key,{})[0] is None)
 setup(full,b'\1');check('valid byte accepted',mod.try_dump(d,key,{})[0] is not None)
 setup(full,b'\1\1');check('wrong-sized validity rejects despite complete metadata',mod.try_dump(d,key,{})[0] is None)
 setup(full,b'\0');check('unknown validity rejects despite complete metadata',mod.try_dump(d,key,{})[0] is None)
 setup(dict(full,depth=3));check('invalid depth rejects',mod.try_dump(d,key,{})[0] is None)
 setup(dict(full,width_words=True));check('boolean shape rejects',mod.try_dump(d,key,{})[0] is None)
 setup(dict(full,known_words=0));check('incomplete metadata rejects',mod.try_dump(d,key,{})[0] is None)
 setup(full,wb=b'\1\0');check('wrong words CRC rejects',mod.try_dump(d,key,{})[0] is None)
 setup(full,cb=clut+b'\0\0');check('oversized palette rejects',mod.try_dump(d,key,{})[0] is None)
 setup(None,b'\1');a,b=mod.try_dump(d,key,{key:(320,0,1,1,0,0,0)});check('exact region validity accepted without metadata',a is not None)
 setup(None,b'\1\1');check('exact region malformed validity rejects',mod.try_dump(d,key,{key:(320,0,1,1,0,0,0)})[0] is None)
assert hashlib.sha256(src.read_bytes()).hexdigest()==pin
result={'checker_sha256':pin,'cpu_only':True,'checks':checks,'passed':all(x['passed'] for x in checks),'scope':'Independent bounded fixture checks of strict native-source validation and 4bpp class decoding only. Not an independent full-pack replay or visual acceptance.'}
(n/'strict-auditor-controls.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'checks':len(checks),'passed':result['passed']}))
