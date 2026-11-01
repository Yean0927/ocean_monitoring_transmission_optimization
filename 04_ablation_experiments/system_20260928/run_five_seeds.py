"""Run, verify, or aggregate the eight ablations across independent seeds."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import statistics
import subprocess
import sys
from audit_results import VARIANTS, audit_seed, read_csv

HERE = Path(__file__).resolve().parent
OCEAN = next(p for p in HERE.parents if (p/'.ocean-root').is_file())
SAVED_RESULTS = HERE.parent/'results/final_five_seeds'


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def aggregate(results, seeds):
    per_seed, summaries, streams = [], {}, {}
    for seed in seeds:
        summary = read_csv(results/f'seed-{seed}/summary.csv')
        summaries[seed] = {r['variant']:r for r in summary}
        streams[seed] = {(r['variant'],r['stream']):r for r in read_csv(results/f'seed-{seed}/by-stream.csv')}
        per_seed.extend(dict(seed=seed, **row) for row in summary)
    write_csv(results/'per-seed-summary.csv', per_seed)
    numeric = [k for k in per_seed[0] if k not in ('seed','variant','stream')]
    overall, stream_table, category_table = [], [], []
    for variant in VARIANTS:
        row = dict(variant=variant, n=len(seeds))
        for key in numeric:
            values = [float(summaries[s][variant][key]) for s in seeds if summaries[s][variant][key] != '']
            row[key+'_mean'] = statistics.mean(values) if values else ''
            row[key+'_sd'] = statistics.stdev(values) if len(values)>1 else 0 if values else ''
        overall.append(row)
        for stream in ('D1','D2','D3','D4','V1','I1'):
            rates = [float(streams[s][variant,stream]['success_delivery_pct']) for s in seeds]
            stream_table.append(dict(variant=variant,stream=stream,n=len(seeds),
                success_delivery_mean_pct=statistics.mean(rates),success_delivery_sd_pct=statistics.stdev(rates)))
        for label, members in [('Text',('D1','D2','D3','D4')),('Video',('V1',)),('Image',('I1',))]:
            rates=[]
            for seed in seeds:
                generated=sum(int(streams[seed][variant,s]['generated_raw_bytes']) for s in members)
                delivered=sum(int(streams[seed][variant,s]['delivered_raw_equivalent_bytes']) for s in members)
                rates.append(100*delivered/generated)
            category_table.append(dict(variant=variant,data_type=label,n_seeds=len(seeds),
                success_delivery_mean_pct=statistics.mean(rates),success_delivery_sd_pct=statistics.stdev(rates),
                seed_rates_pct=';'.join(f'{r:.6f}' for r in rates)))
    write_csv(results/'five-seed-aggregate.csv',overall)
    write_csv(results/'by-stream-five-seed-aggregate.csv',stream_table)
    write_csv(results/'data-type-success-five-seed.csv',category_table)
    table=['# 五种子重复实验汇总','',
        f'种子 {", ".join(map(str,seeds))}；8 组 × {len(seeds)} 个种子。以下为各次按原始字节加权的指标的算术均值 ± 样本标准差。', '',
        '| 组别 | 成功送达率 (%) | 拒收/淘汰率 (%) | 待完成率 (%) | 受限平均送达时间 (s) |',
        '|:--|--:|--:|--:|--:|']
    for row in overall:
        cells=[f'{row[k+"_mean"]:.2f} ± {row[k+"_sd"]:.2f}' for k in
               ('success_delivery_pct','loss_pct','pending_pct','restricted_mean_delivery_time_s')]
        table.append('| '+' | '.join([row['variant']]+cells)+' |')
    table += ['', '前三项相加为 100%（四舍五入可能造成 0.01 个百分点偏差）。loss_pct 对应应用层拒收或缓存淘汰，不是链路物理丢包率。',
              '三类数据送达率见 data-type-success-five-seed.csv；文本先合并 D1–D4 的字节数再除以生成字节数。']
    (results/'five-seed-report.md').write_text('\n'.join(table)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--verify-only',action='store_true',help='Read and audit saved runs without rerunning or replacing their CSV files.')
    mode.add_argument('--aggregate-only',action='store_true',help='Audit and regenerate aggregate CSVs from saved per-seed summaries.')
    parser.add_argument('--results',type=Path,help='Existing result root to verify/aggregate; defaults to the final five-seed archive.')
    parser.add_argument('--output',type=Path,help='New output root when executing simulations.')
    parser.add_argument('--prepared',type=Path,default=HERE/'prepared')
    parser.add_argument('--seeds',type=int,nargs='+',default=[31,32,33,34,35])
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--binary',type=Path)
    parser.add_argument('--quic-lib-dir',type=Path)
    parser.add_argument('--audit-output',type=Path)
    args=parser.parse_args()
    if len(args.seeds)<2 or len(set(args.seeds))!=len(args.seeds):parser.error('Provide at least two distinct seeds.')
    verify=args.verify_only or args.aggregate_only
    results=(args.results or SAVED_RESULTS).resolve() if verify else (args.output or OCEAN/'runs/system_ablation_five_seeds').resolve()
    if not verify:
        if args.results:parser.error('Use --output for new runs, not --results.')
        if results==SAVED_RESULTS.resolve():parser.error('Choose a new output directory for simulations.')
        for seed in args.seeds:
            destination=results/f'seed-{seed}'
            if destination.exists() and any(destination.iterdir()):parser.error(f'Refusing to overwrite existing run: {destination}')
        for seed in args.seeds:
            command=[sys.executable,str(HERE/'run_experiment.py'),'--prepared',str(args.prepared.resolve()),
                     '--output',str(results/f'seed-{seed}'),'--seed',str(seed),'--workers',str(args.workers)]
            if args.binary:command+=['--binary',str(args.binary)]
            if args.quic_lib_dir:command+=['--quic-lib-dir',str(args.quic_lib_dir)]
            subprocess.run(command,check=True)
    audits={}
    for seed in args.seeds:
        audits[str(seed)]=audit_seed(args.prepared,results/f'seed-{seed}')
        print(f'PASS seed={seed}: eight variants, byte accounting, timestamps and protocol decisions',flush=True)
    if not args.verify_only:aggregate(results,args.seeds)
    if args.audit_output:
        args.audit_output.parent.mkdir(parents=True,exist_ok=True)
        args.audit_output.write_text(json.dumps(dict(status='PASS',seeds=args.seeds,runs=len(args.seeds)*8,results=str(results),per_seed=audits),ensure_ascii=False,indent=2)+'\n')
    print(f'Completed {len(args.seeds)*8} run audits; results={results}')


if __name__=='__main__':main()
