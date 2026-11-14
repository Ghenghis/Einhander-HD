from pathlib import Path
import shutil
n=Path(__file__).resolve().parent;out=n/'scene-packet-lag1-r1-rejected';assert not out.exists();shutil.copytree(n/'scene-packet-lag1',out)
