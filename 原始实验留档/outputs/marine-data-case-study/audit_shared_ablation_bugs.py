"""Read saved case-study evidence and replay isolated transport checks.

Writes only to audit-20261016; preserves formal data, codecs and figures.
Run with Python 3; no third-party dependencies required.
"""
import collections
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXP = HERE / 'resource-experiment'
OUT = HERE / 'audit-20261016'
FIXED = ROOT / 'system-ablation-20260928-table-rates/validation/repeated-five-seeds-rto-fixed-20261015'
OUT.mkdir(exist_ok=True)


def read_json(path):
    return json.loads(path.read_text())


def rows(path, delimiter=','):
    with path.open(newline='') as f:
        return list(csv.DictReader(f, delimiter=delimiter))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(a, b, tol=1e-8):
    assert math.isclose(float(a), float(b), rel_tol=0, abs_tol=tol), (a, b)


config = read_json(EXP / 'run-config.json')
build = read_json(EXP / 'simulator-build.json')
codecs = read_json(EXP / 'codec-measurements.json')
trials = read_json(EXP / 'trials.json')
summary = read_json(EXP / 'summary.json')
binary = EXP / 'resource-simulator'
assert len(codecs) == 45 and len(trials) == 135 and len(summary) == 27
assert sha(binary) == config['ns3_binary_sha256']
assert sha(EXP / 'resource-simulator.cc') == config['simulator_source_sha256'] == build['source_sha256']
assert 'TimeValue(Seconds(l.rtt/2000.0))' in (EXP / 'resource-simulator.cc').read_text()

for c in codecs:
    raw, enc = Path(c['raw_path']), Path(c['compressed_path'])
    assert sha(raw) == c['raw_sha256'] and sha(enc) == c['compressed_sha256']
    assert raw.stat().st_size == c['raw_bytes'] and enc.stat().st_size == c['compressed_bytes']
    compression = read_json(enc.with_name('compression.json'))
    decompression = read_json(enc.with_name('decompression.json'))
    close(compression['per_object_s'], c['compression_s'])
    close(decompression['per_object_s'], c['decompression_s'])
    if c['stream'] == 'D2':
        assert gzip.decompress(enc.read_bytes()) == raw.read_bytes()
    if c['stream'] == 'V1':
        assert decompression['decoded_frames'] == 505

protocols = collections.Counter()
max_queue, max_drops, max_waiting = 0, 0, 0
for t in trials:
    p = Path(t['trace'])
    assert p.is_relative_to(EXP / 'network')
    trace = rows(p)
    inputs = rows(p.with_name('files.tsv'), '\t')
    decisions = rows(Path(str(p) + '.decisions.csv'))
    link = rows(p.with_name('link.csv'))
    assert len(trace) == len(inputs) == len(decisions) == len(link) == 1
    r, inp, decision, link = trace[0], inputs[0], decisions[0], link[0]
    protocols[r['protocol']] += 1
    assert r['protocol'] == decision['protocol'] == '2'
    assert inp['raw_choices'] == inp['comp_choices'] == '2'
    assert t['protocol'] == 'TCP_CUBIC' and r['status'] == t['status'] == 'delivered'
    assert int(r['generated_raw_bytes']) == int(r['arrived_raw_bytes']) == t['raw_bytes']
    assert int(inp['raw_bytes']) == t['raw_bytes'] and int(inp['encoded_bytes']) == t['compressed_bytes']
    assert int(r['wire_file_bytes']) == t['compressed_bytes']
    assert sha(Path(inp['raw_path'])) == t['raw_sha256']
    assert sha(Path(inp['encoded_path'])) == t['compressed_sha256']
    assert float(link['packet_loss_rate']) == 0
    close(link['capacity_mbps'], t['bandwidth_mbps'])
    close(link['rtt_ms'], t['rtt_ms'])
    close(inp['encode_s'], t['compression_s'])
    close(inp['decode_s'], t['decompression_s'])
    close(float(r['tx_start_s']) - float(r['assembled_s']), t['compression_s'])
    close(float(r['received_s']) - float(r['tx_start_s']), t['transport_s'])
    close(float(r['decoded_s']) - float(r['received_s']), t['decompression_s'])
    close(float(r['decoded_s']) - float(r['assembled_s']), t['jct_s'])
    close(t['jct_s'], t['compression_s'] + t['transport_s'] + t['decompression_s'])
    assert float(r['decoded_s']) < 3600 and abs(t['queue_s']) < 1e-8
    log = p.with_name('ns3.log').read_text()
    assert 'Completed WO_PROTOCOL files=1' in log
    assert not any(x in log for x in ['PAYLOAD_MISMATCH', 'QUIC_ABORT', 'NS_FATAL'])
    metrics = read_json(Path(str(p) + '.metrics.json'))
    max_queue = max(max_queue, metrics['peak_queue_bytes'])
    max_drops = max(max_drops, metrics['link_dropped_packets'])
    max_waiting = max(max_waiting, metrics['remaining_queue_bytes'])

for s in summary:
    group = [t for t in trials if all(t[k] == s[k] for k in ['stream', 'resource', 'quality'])]
    assert len(group) == s['n'] == 5
    close(s['mean_jct_s'], statistics.mean(t['jct_s'] for t in group), 1e-12)
    close(s['sd_jct_s'], statistics.stdev(t['jct_s'] for t in group), 1e-12)
    for k in ['compression_s', 'decompression_s', 'transport_s', 'compressed_bytes']:
        close(s['mean_' + k], statistics.mean(t[k] for t in group), 1e-12)

source_files = [HERE / 'figures/resource_source_data.json', HERE / 'figures/版式图/resource_source_data.json']
for source in source_files:
    plotted = read_json(source)['records']
    key = lambda r: (r['stream'], r['resource'], r['quality'])
    assert sorted(plotted, key=key) == sorted(summary, key=key)

# A paired check across object types, high RTT, high bandwidth and shared CPU.
# Reuse recorded inputs and codec timings, changing only the loaded QUIC library.
selected = [t for t in trials if t['replicate'] == 0 and
            (t['resource'], t['quality']) in [('Delay', 'Poor'), ('BW', 'Good'), ('CPU', 'Poor')]]
fixed_library = FIXED / 'lib/libns3.42-quic-optimized.dylib'
assert sha(fixed_library) == read_json(FIXED / 'provenance.json')['library_sha256']
smoke = []
for t in selected:
    original = Path(t['trace'])
    old = rows(original)[0]
    for mode in ['public', 'quic_fixed']:
        target = OUT / mode / t['resource'] / t['quality'] / t['stream']
        target.mkdir(parents=True, exist_ok=True)
        result = target / 'trace.csv'
        command = [str(binary), '--input=' + str(original.parent), '--output=' + str(result),
                   '--variant=WO_PROTOCOL', '--duration=3600', '--drain=0', '--seed=31', '--cacheBytes=50000000']
        env = dict(os.environ)
        env.pop('DYLD_LIBRARY_PATH', None)
        env.pop('DYLD_INSERT_LIBRARIES', None)
        env['DYLD_PRINT_LIBRARIES'] = '1'
        if mode == 'quic_fixed':
            env['DYLD_LIBRARY_PATH'] = str(fixed_library.parent)
        with (target / 'ns3.log').open('w') as log:
            subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
        new = rows(result)[0]
        assert new == old, (mode, t['stream'], t['resource'], new, old)
        assert rows(Path(str(result) + '.decisions.csv')) == rows(Path(str(original) + '.decisions.csv'))
        assert read_json(Path(str(result) + '.metrics.json')) == read_json(Path(str(original) + '.metrics.json'))
        if mode == 'quic_fixed':
            assert str(fixed_library) in (target / 'ns3.log').read_text()
        (target / 'command.json').write_text(json.dumps(dict(command=command, library_mode=mode), indent=2))
        smoke.append(dict(stream=t['stream'], resource=t['resource'], quality=t['quality'],
                          library_mode=mode, all_trace_fields_identical=True,
                          decisions_identical=True, link_metrics_identical=True, trace=str(result)))
        print('PASS replay', mode, t['resource'], t['quality'], t['stream'], flush=True)

with (ROOT / 'system-ablation-20260928-table-rates/results/FULL.csv').open() as f:
    historical = {r['id']: r for r in csv.DictReader(f)}
legacy = [dict(stream=e['stream'], file_id=e['file_id'],
               protocol_id=int(historical[str(e['file_id'])]['protocol']))
          for e in read_json(HERE / 'case_measurements.json')['actual_full_events']]
report = dict(verdict='PASS_CURRENT_RESOURCE_CASE_STUDY_NO_RERUN_REQUIRED',
              audited_date='2026-10-16', codec_pairs=45, formal_network_trials=135, plot_points=27,
              actual_protocol_ids=dict(protocols), max_queue_bytes=max_queue,
              max_remaining_queue_bytes=max_waiting, max_link_drops=max_drops,
              source_sha256=sha(EXP / 'resource-simulator.cc'), binary_sha256=sha(binary),
              fixed_quic_library_sha256=sha(fixed_library),
              summary_and_both_figure_sources_match=True, isolated_replays=smoke,
              legacy_full_events=legacy,
              limitations=['Formal run config does not pin dynamic library hashes.',
                           'Runner reuses existing trace/codec caches without full input and version validation.',
                           'CPU repetition is technical repetition of one representative object per data type.'],
              production_results_modified=False)
(OUT / 'audit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print('PASS: 135 formal traces; 45 codec pairs; 27 points; 18 identical isolated replays.')
