from pathlib import Path
import csv,json,statistics,re,difflib,argparse
parser=argparse.ArgumentParser();parser.add_argument("--stage",default="recovery-full");args=parser.parse_args()
h=Path(__file__).resolve().parent
old=h.parent/'repeated-five-seeds-20261015'
variants=[]
for seed in (32,34):
 def read(p):
  with p.open(newline='') as f:return list(csv.DictReader(f))
 baseline=read(old/f'seed-{seed}/FULL.csv')
 diag=read(h/f'diagnostic-seed-{seed}/FULL.csv')
 old_delivered={r['id']:float(r['decoded_s']) for r in baseline if r['status']=='delivered' and float(r['decoded_s'])<1000}
 diag_delivered={r['id']:float(r['decoded_s']) for r in diag if r['status']=='delivered'}
 assert old_delivered.keys()==diag_delivered.keys(),(seed,'diagnostic changed completion set')
 max_diff=max(abs(t-diag_delivered[k]) for k,t in old_delivered.items())
 assert max_diff<1e-7,(seed,max_diff)
 print('BASELINE_REPRODUCED',seed,len(diag_delivered),'maximum time difference',max_diff)
 p=h/f'{args.stage}-seed-{seed}/FULL.csv'
 if not p.exists():continue
 fixed=read(p)
 assert [r['id'] for r in baseline]==[r['id'] for r in fixed]
 assert all(a['generated_raw_bytes']==b['generated_raw_bytes'] and a['wire_file_bytes']==b['wire_file_bytes'] for a,b in zip(baseline,fixed))
 for label,rows in [('before',baseline),('after',fixed)]:
  G=sum(int(r['generated_raw_bytes']) for r in rows)
  D=sum(int(r['generated_raw_bytes']) for r in rows if r['status']=='delivered' and float(r['decoded_s'])<=3600)
  L=sum(int(r['generated_raw_bytes']) for r in rows if r['status'] in ('source_dropped','cache_evicted'))
  ds=sorted(float(r['decoded_s']) for r in rows if r['status']=='delivered')
  gaps=[(b-a,a,b) for a,b in zip([0]+ds,ds+[3600])]
  gap,start,end=max(gaps)
  out={'seed':seed,'stage':label,'generated_raw_bytes':G,'delivered_raw_bytes':D,'confirmed_lost_raw_bytes':L,'pending_raw_bytes':G-D-L,'success_pct':100*D/G,'loss_pct':100*L/G,'pending_pct':100*(G-D-L)/G,'delivered_files':len(ds),'last_delivered_s':max(ds),'longest_interval_without_file_completion_s':gap,'interval_start_s':start,'interval_end_s':end}
  variants.append(out);print(json.dumps(out))
if len(variants)==4:
 with (h/f'comparison-{args.stage}.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(variants[0]));w.writeheader();w.writerows(variants)
 (h/f'comparison-{args.stage}.json').write_text(json.dumps(variants,indent=2))
