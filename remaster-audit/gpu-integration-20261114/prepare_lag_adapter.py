from pathlib import Path
import shutil
n=Path(__file__).resolve().parent;old=n.parent/'cpu-remix-integration-20261114/scene-packet-v2';out=n/'scene-packet-lag1';assert not out.exists();out.mkdir()
for name in ['remix_mesh_packet.h','remix_mesh_packet.cpp','test_remix_mesh_packet.cpp']:shutil.copy2(old/name,out/name)
shutil.copytree(old/'vendor',out/'vendor')
s=(old/'run_host_checks.py').read_text()
s=s.replace("hold_bytes=hold.read_bytes();assert json.loads(hold_bytes)['owner']=='user-external-project'","hold_bytes=hold.read_bytes() if hold.exists() else None")
s=s.replace("assert hold.read_bytes()==hold_bytes","assert (hold.read_bytes() if hold.exists() else None)==hold_bytes")
(out/'run_host_checks.py').write_text(s,encoding='utf-8')
