"""Reclassify the completed 3900 s traces at a 3600 s observation cutoff.

The source generated data only before 3600 s. No files became ready after
3600 s in the source traces. Since Ready() is the only place where the
application drops or evicts files, their final drop labels already apply at
the cutoff. Network packet counters cannot be reconstructed from final file
records and are deliberately left unavailable.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
VARIANTS = [
    'FULL', 'WO_PROTOCOL', 'WO_COMPRESSION', 'WO_CACHE', 'BASELINE',
    'ADD_PROTOCOL', 'ADD_COMPRESSION', 'ADD_CACHE',
]
DROP_STATUSES = {'source_dropped', 'cache_evicted'}
TIMES = ('assembled_s', 'ready_s', 'tx_start_s', 'received_s', 'decoded_s')


def rows(path: Path):
    with path.open(newline='') as f:
        return list(csv.DictReader(f))


def write_rows(path: Path, data):
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def at_cutoff(row, horizon):
    out = row.copy()
    status = row['status']
    ready = float(row['ready_s'])
    if ready > horizon:
        raise ValueError(f"File {row['id']} became ready after cutoff; drop time cannot be inferred")
    if status in DROP_STATUSES:
        if ready < 0:
            raise ValueError(f"Dropped file {row['id']} lacks a ready timestamp")
    elif 0 <= float(row['decoded_s']) <= horizon:
        status = 'delivered'
    elif 0 <= float(row['received_s']) <= horizon:
        status = 'decoding'
    elif 0 <= float(row['tx_start_s']) <= horizon:
        status = 'in_transport'
    elif 0 <= ready <= horizon:
        status = 'queued'
    elif 0 <= float(row['assembled_s']) <= horizon:
        status = 'encoding'
    else:
        status = 'assembling'
    out['status'] = status
    for field in TIMES:
        if float(out[field]) > horizon:
            out[field] = '-1'
    if float(out['tx_start_s']) < 0:
        out['protocol'] = '-1'
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, default=HERE / 'validation/prior-3900s-eight-groups')
    p.add_argument('--output', type=Path, default=HERE / 'results')
    p.add_argument('--cutoff', type=float, default=3600.0)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    audit = {'method': 'postprocess existing 3900 s per-file traces; no simulation run',
             'observation_cutoff_s': args.cutoff, 'source': str(args.source.resolve()),
             'variants': {}}
    for variant in VARIANTS:
        source_rows = rows(args.source / f'{variant}.csv')
        if not source_rows:
            raise ValueError(f'{variant}: source trace is empty')
        ids = [int(r['id']) for r in source_rows]
        if ids != list(range(len(ids))):
            raise ValueError(f'{variant}: file IDs are incomplete or unordered')
        reclassified = [at_cutoff(r, args.cutoff) for r in source_rows]
        for source, current in zip(source_rows, reclassified):
            if source['status'] in DROP_STATUSES and current['status'] != source['status']:
                raise AssertionError('Permanent drop label changed')
            if current['status'] == 'delivered' and float(current['decoded_s']) > args.cutoff:
                raise AssertionError('Post-cutoff delivery counted as success')
        write_rows(args.output / f'{variant}.csv', reclassified)
        source_decisions = rows(args.source / f'{variant}.csv.decisions.csv')
        decisions = [r for r in source_decisions if float(r['time_s']) <= args.cutoff]
        write_rows(args.output / f'{variant}.csv.decisions.csv', decisions)
        raw_metrics = json.loads((args.source / f'{variant}.csv.metrics.json').read_text())
        remaining_queue = sum(int(r['wire_file_bytes']) for r in reclassified if r['status'] == 'queued')
        metrics = {
            'peak_queue_bytes': raw_metrics['peak_queue_bytes'],
            'peak_assembly_bytes': None,
            'link_dropped_packets': None,
            'wire_packets_both_directions': None,
            'remaining_queue_bytes': remaining_queue,
        }
        (args.output / f'{variant}.csv.metrics.json').write_text(json.dumps(metrics, indent=2) + '\n')
        transitioned = [r for r in source_rows if r['status'] == 'delivered' and float(r['decoded_s']) > args.cutoff]
        audit['variants'][variant] = {
            'file_rows': len(source_rows),
            'ready_after_cutoff': sum(float(r['ready_s']) > args.cutoff for r in source_rows),
            'drops_reclassified': sum(r['status'] in DROP_STATUSES for r in source_rows),
            'deliveries_after_cutoff_reclassified_pending': len(transitioned),
            'raw_bytes_reclassified_pending': sum(int(r['generated_raw_bytes']) for r in transitioned),
            'decisions_after_cutoff_removed': len(source_decisions) - len(decisions),
            'file_metrics_reconstructible': True,
            'packet_counters_at_cutoff_reconstructible': False,
        }
    (args.output / 'cutoff-reclassification.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps(audit, indent=2))


if __name__ == '__main__':
    main()
