"""Validate per-file accounting, event order and exact-state model decisions."""
import csv, json
from collections import Counter
from pathlib import Path
P=Path(__file__).resolve().parent
files=json.loads((P/'prepared/files.json').read_text())
config=json.loads((P/'prepared/run-config.json').read_text())
report={}
common=None
for variant in config['variants']:
    rows=list(csv.DictReader((P/'results'/f'{variant}.csv').open()))
    assert len(rows)==len(files)
    generated=[int(r['generated_raw_bytes']) for r in rows]
    if common is None:common=generated
    assert common==generated
    delivered=[r for r in rows if r['status']=='delivered']
    dropped=[r for r in rows if r['status'] in ('source_dropped','cache_evicted')]
    transport_stalls=[]
    for r in rows:
        if r['status'] in ('in_service','in_transport') and float(r['tx_start_s'])>=0:
            age=config['duration_s']+config['drain_s']-float(r['tx_start_s'])
            if age>=600:
                transport_stalls.append({'id':r['id'],'stream':r['stream'],'protocol':r['protocol'],'age_s':round(age,3)})
    for r in delivered:
        assert int(r['raw_file_bytes'])==int(r['generated_raw_bytes'])==int(r['arrived_raw_bytes'])
        times=[float(r[k]) for k in ['first_s','assembled_s','ready_s','tx_start_s','received_s','decoded_s']]
        assert all(a<=b+1e-8 for a,b in zip(times,times[1:])),r
    for r in csv.DictReader((P/'results'/f'{variant}.csv.decisions.csv').open()):
        item=files[int(r['id'])]
        forced_static=variant in ('WO_PROTOCOL','BASELINE','ADD_COMPRESSION','ADD_CACHE')
        raw_features=variant in ('WO_COMPRESSION','ADD_PROTOCOL','ADD_CACHE')
        expected=2 if forced_static else int(item['raw_choices' if raw_features else 'comp_choices'][int(r['state_index'])])
        assert int(r['protocol'])==expected
    g=sum(generated);d=sum(int(r['raw_file_bytes']) for r in delivered);loss=sum(int(r['generated_raw_bytes']) for r in dropped)
    assert g-d-loss>=0
    metrics=json.loads((P/'results'/f'{variant}.csv.metrics.json').read_text())
    assert metrics['peak_queue_bytes']<=config['cache_bytes']
    if variant in ('WO_CACHE','BASELINE','ADD_PROTOCOL','ADD_COMPRESSION'):assert metrics['peak_queue_bytes']==0
    report[variant]={'file_rows':len(rows),'status_counts':dict(Counter(r['status'] for r in rows)),
       'generated_bytes':g,'delivered_bytes':d,'dropped_bytes':loss,'pending_bytes':g-d-loss,
       'last_delivery_s':max((float(r['decoded_s']) for r in delivered),default=None),
       'transport_stalls_over_600s':transport_stalls,
       'accounting_and_event_order':'PASS','protocol_predictions':'PASS',
       'transport_stall_audit':'FLAG' if transport_stalls else 'PASS'}
(P/'results/audit.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
stalled=[name for name,item in report.items() if item['transport_stall_audit']=='FLAG']
assert not stalled, f'Long transport stalls in: {", ".join(stalled)}'
