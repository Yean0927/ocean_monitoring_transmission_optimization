from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess,time,json,os,argparse
h=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--label');p.add_argument('--seeds',nargs='+',type=int,default=[32,34]);p.add_argument('--stop',type=float,default=1000);args=p.parse_args()
prepared=Path('/Users/yean/program/海洋监测/system-ablation-20260928-table-rates/prepared')
def run(seed):
 d=h/f'{args.label or args.tag}-seed-{seed}';d.mkdir(exist_ok=True)
 cmd=[str(h/'system-ablation-diag'),f'--input={prepared}',f'--output={d}/FULL.csv','--variant=FULL','--duration=3600','--drain=0','--cacheBytes=50000000',f'--seed={seed}',f'--stopAt={args.stop}']
 env=os.environ.copy();env['DYLD_LIBRARY_PATH']=str(h/f'lib-{args.tag}')
 print('START',args.tag,seed,flush=True);start=time.perf_counter()
 with (d/'diagnostic.log').open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,env=env)
 (d/'run.json').write_text(json.dumps({'command':cmd,'library':env['DYLD_LIBRARY_PATH'],'returncode':r.returncode,'wall_seconds':time.perf_counter()-start},indent=2))
 print('DONE',args.tag,seed,'exit',r.returncode,round(time.perf_counter()-start,1),flush=True)
 if r.returncode:raise RuntimeError('Trial failed')
with ThreadPoolExecutor(max_workers=min(2,len(args.seeds))) as ex:list(ex.map(run,args.seeds))
