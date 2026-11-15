"""Compose the separately verified exact-native-alpha option, preserving failed precheck."""
from pathlib import Path
p=Path(__file__).resolve().parent
source=(p/'compose_rise_f32.py').read_text()
source=source.replace("source=r/'remaster-audit/claude-backlog/class-mip/rise-native-vector/expand33/20261114T135902Z'", "source=n/'rise-native-alpha-r1'")
source=source.replace('d4379b41b64bbeff1e38fb965a93a5880f677e3779b716859f60ba8fce1326ec','4b4c7397afd66b757bfe0d1d1fdf6b7c2942ac31bac5cad12f37bca4340fc0ab')
source=source.replace("data['summary']['reference_palette_identical_to_approved_v5']", "data['summary']['all_alpha_exact_native']")
source=source.replace("integration_variant='native-faithful-rise-f32-1024x512'", "integration_variant='rise-f32-exact-native-alpha-1024x512'")
source=source.replace("n/'rise-f32-plan.json'", "n/'rise-native-alpha-plan.json'")
source=source.replace("n/'rise-f32-composition-result.json'", "n/'rise-native-alpha-composition-result.json'")
source=source.replace("n/('rise-f32-'+label+'.log')", "n/('rise-native-alpha-'+label+'.log')")
exec(compile(source,str(__file__),'exec'))
