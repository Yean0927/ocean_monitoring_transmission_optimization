from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess,time,json,os
h=Path(__file__).resolve().parent
prepared=Path('/Users/yean/program/海洋监测/system-ablation-20260928-table-rates/prepared')
def run(seed):
 d=h/f'diagnostic-seed-{seed}';d.mkdir(exist_ok=True)
 args=[str(h/'system-ablation-diag'),f'--input={prepared}',f'--output={d}/FULL.csv','--variant=FULL','--duration=3600','--drain=0','--cacheBytes=50000000',f'--seed={seed}','--stopAt=1000']
 env=os.environ.copy();env['DYLD_LIBRARY_PATH']=str(h/'lib')
 print('START',seed,flush=True);start=time.perf_counter()
 with (d/'diagnostic.log').open('w') as f: subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,env=env,check=True)
 print('DONE',seed,round(time.perf_counter()-start,1),flush=True)
with ThreadPoolExecutor(max_workers=2) as ex:list(ex.map(run,[32,34]))
