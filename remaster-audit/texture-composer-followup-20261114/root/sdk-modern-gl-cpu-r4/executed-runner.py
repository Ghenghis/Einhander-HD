"""Fresh CPU-only build after the independent lifetime/Present/freshness review."""
from pathlib import Path
p=Path(__file__).resolve().parent
source=(p/'build_modern_gl_cpu_r2.py').read_text()
source=source.replace("out=n/'sdk-modern-gl-cpu-r2'", "out=n/'sdk-modern-gl-cpu-r4'")
start=source.index("r1=n/'sdk-modern-gl-cpu-r1'");end=source.index('shutil.copy2(__file__',start);source=source[:start]+source[end:]
source=source.replace("hold=marker.read_bytes();assert json.loads(hold)['owner']=='user-external-project' and json.loads(hold)['expires_utc'] is None", "hold=marker.read_bytes() if marker.exists() else None;assert hold is None, 'Do not build a GPU candidate while another reservation exists'")
source=source.replace("a['cpu_contract_checks']==10", "a['cpu_contract_checks']==14")
source=source.replace("assert a['reservation_exists'] and not a['gpu_started'] and not a['dll_loaded']", "assert not a['reservation_exists'] and not a['owned_execution_lease'] and not a['gpu_started'] and not a['dll_loaded']")
source=source.replace('assert marker.read_bytes()==hold', 'assert not marker.exists()')
source=source.replace('hashlib.sha256(hold).hexdigest()', 'None')
source=source.replace('user_hold_unchanged=True', 'other_reservation_unchanged=True, user_hold_released=True')
exec(compile(source,str(__file__),'exec'))
