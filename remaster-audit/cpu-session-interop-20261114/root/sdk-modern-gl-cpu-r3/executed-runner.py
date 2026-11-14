"""Fresh CPU-only qualification of the nonce-bound private GL probe."""
from pathlib import Path

p = Path(__file__).resolve().parent
source = (p / 'build_modern_gl_cpu_r2.py').read_text()
source = source.replace("out=n/'sdk-modern-gl-cpu-r2'", "out=n/'sdk-modern-gl-cpu-r3'")
start = source.index("r1=n/'sdk-modern-gl-cpu-r1'")
end = source.index('shutil.copy2(__file__', start)
source = source[:start] + source[end:]
source = source.replace("a['cpu_contract_checks']==10", "a['cpu_contract_checks']==14")
source = source.replace("assert a['reservation_exists'] and not a['gpu_started']", "assert a['reservation_exists'] and not a['owned_execution_lease'] and not a['gpu_started']")
exec(compile(source, str(__file__), 'exec'))
