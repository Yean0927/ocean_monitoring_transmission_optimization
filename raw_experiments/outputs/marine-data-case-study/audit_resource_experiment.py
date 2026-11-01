"""Audit the saved real payloads and final network traces before publication."""
import csv
import gzip
import hashlib
import json
import statistics
import subprocess
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
EXP = HERE/'resource-experiment'
config = json.loads((EXP/'run-config.json').read_text())
codecs = json.loads((EXP/'codec-measurements.json').read_text())
trials = json.loads((EXP/'trials.json').read_text())
summary = json.loads((EXP/'summary.json').read_text())
assert len(codecs)==45 and len(trials)==135 and len(summary)==27
assert 'Seconds(l.rtt/2000.0)' in (EXP/'resource-simulator.cc').read_text()
assert hashlib.sha256((EXP/'resource-simulator').read_bytes()).hexdigest()==config['ns3_binary_sha256']
video = next(c for c in codecs if c['stream']=='V1')
progress = EXP/'source-video-decompression.progress'
with (EXP/'source-video-decompression.log').open('w') as log:
    subprocess.run([config['ffmpeg'],'-y','-nostdin','-v','error','-i',video['raw_path'],
                    '-map','0:v:0','-an','-progress',str(progress),'-f','null','/dev/null'],
                   stdout=log,stderr=subprocess.STDOUT,check=True)
raw_progress = dict(line.split('=',1) for line in progress.read_text().splitlines() if '=' in line)
assert raw_progress['progress']=='end'
frames = int(raw_progress['frame'])
rates = {}
for c in codecs:
    raw = Path(c['raw_path']).read_bytes()
    encoded = Path(c['compressed_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==c['raw_sha256']
    assert hashlib.sha256(encoded).hexdigest()==c['compressed_sha256']
    assert len(encoded)==c['compressed_bytes'] and len(raw)==c['raw_bytes']
    if c['stream']=='D2':
        assert gzip.decompress(encoded)==raw
    elif c['stream']=='I1':
        with Image.open(c['raw_path']) as original, Image.open(c['compressed_path']) as restored:
            restored.load()
            assert restored.size==original.size
    else:
        d=json.loads(Path(c['compressed_path']).with_name('decompression.json').read_text())
        assert d['decoded_frames']==frames
    for stage in ['compression','decompression']:
        r=json.loads(Path(c['compressed_path']).with_name(stage+'.json').read_text())
        rates.setdefault((c['profile'],c['stream']),[]).append(r['batch_cpu_s']/r['batch_wall_s'])
for r in trials:
    assert r['status']=='delivered' and r['protocol']=='TCP_CUBIC'
    assert abs(r['jct_s']-r['compression_s']-r['transport_s']-r['decompression_s'])<1e-8
    assert abs(r['queue_s'])<1e-8
    assert r['trace'].startswith(str(EXP/'network/'))
    with Path(r['trace']).open() as f:
        trace=next(csv.DictReader(f))
    assert int(trace['wire_file_bytes'])==r['compressed_bytes']
    assert int(trace['generated_raw_bytes'])==r['raw_bytes']
    assert float(trace['decoded_s'])<3600 and trace['status']=='delivered'
    with Path(r['trace']).with_name('link.csv').open() as f:
        link=next(csv.DictReader(f))
    assert float(link['rtt_ms'])==r['rtt_ms'] and float(link['capacity_mbps'])==r['bandwidth_mbps']
for row in summary:
    a=[t['jct_s'] for t in trials if all(t[k]==row[k] for k in ['stream','resource','quality'])]
    assert len(a)==5
    assert abs(statistics.mean(a)-row['mean_jct_s'])<1e-12
    assert abs(statistics.stdev(a)-row['sd_jct_s'])<1e-12
report=dict(verdict='PASS',codec_pairs=45,network_trials=135,plot_points=27,
            delivered_before_horizon=135,source_and_all_compressed_video_frames=frames,
            fractional_rtt_source_verified=True,byte_checks='all saved payloads verified; all network traces delivered',
            jct_sum_verified=True,summary_means_and_sample_sd_verified=True,
            measured_cpu_per_wall={f'{profile}/{stream}':dict(min=min(a),mean=statistics.mean(a),max=max(a))
                                   for (profile,stream),a in rates.items()})
(EXP/'audit.json').write_text(json.dumps(report,indent=2))
print('PASS: 45 codec pairs; 135 delivered trials; 27 means and SDs; source and all compressed videos',frames,'frames')
