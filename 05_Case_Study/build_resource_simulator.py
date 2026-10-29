"""Compile an isolated copy of the existing simulator with fractional RTT support."""

# Paths for the consolidated ocean package.
import os
from pathlib import Path
OCEAN_ROOT = next(p for p in Path(__file__).resolve().parents if (p / '.ocean-root').is_file())
OCEAN_DATA = Path(os.environ.get('OCEAN_DATA_DIR', str(OCEAN_ROOT / 'data'))).expanduser().resolve()
OCEAN_IMAGE_DIR = Path(os.environ.get('OCEAN_IMAGE_DIR', str(OCEAN_ROOT / 'data/图片文件'))).expanduser().resolve()
OCEAN_NS3 = Path(os.environ.get('OCEAN_NS3_ROOT', str(OCEAN_ROOT / '原始实验留档/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42'))).expanduser().resolve()

import hashlib
import json
import shlex
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = OCEAN_ROOT
NS = OCEAN_NS3
OUT = HERE/'resource-experiment'
OUT.mkdir(exist_ok=True)
original = ROOT/'04_消融实验/system_20260928/system-ablation.cc'
source = OUT/'resource-simulator.cc'
old = 'TimeValue(MilliSeconds(l.rtt/2))'
new = 'TimeValue(Seconds(l.rtt/2000.0))'
code = original.read_text()
assert code.count(old) == 1
source.write_text(code.replace(old,new))
commands = json.loads((NS/'cmake-cache/compile_commands.json').read_text())
entry = next(c for c in commands if Path(c['file']).name == 'system-ablation.cc')
compile_cmd = shlex.split(entry['command'])
obj = OUT/'resource-simulator.o'
compile_cmd[compile_cmd.index('-o')+1] = str(obj)
compile_cmd[-1] = str(source)
link = shlex.split((NS/'cmake-cache/scratch/CMakeFiles/scratch_system-ablation.dir/link.txt').read_text())
link[link.index('CMakeFiles/scratch_system-ablation.dir/system-ablation.cc.o')] = str(obj)
link[link.index('-o')+1] = str(OUT/'resource-simulator')
subprocess.run(compile_cmd, cwd=entry['directory'], check=True)
subprocess.run(link, cwd=entry['directory'], check=True)
(OUT/'simulator-build.json').write_text(json.dumps(dict(
    source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    original=str(original), original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),
    change=f'{old} -> {new}', compile_command=compile_cmd, link_command=link),indent=2))
print('Built isolated resource-simulator with fractional RTT support')
