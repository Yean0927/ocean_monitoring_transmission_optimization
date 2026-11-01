"""Measure resource-constrained codecs and replay actual payloads over ns-3 TCP."""

# Paths for the consolidated ocean package.
import os
from pathlib import Path
OCEAN_ROOT = next(p for p in Path(__file__).resolve().parents if (p / '.ocean-root').is_file())
OCEAN_DATA = Path(os.environ.get('OCEAN_DATA_DIR', str(OCEAN_ROOT / 'data'))).expanduser().resolve()
OCEAN_IMAGE_DIR = Path(os.environ.get('OCEAN_IMAGE_DIR', str(OCEAN_ROOT / 'data/images'))).expanduser().resolve()
OCEAN_NS3 = Path(os.environ.get('OCEAN_NS3_ROOT', str(OCEAN_ROOT / 'raw_experiments/cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42'))).expanduser().resolve()

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path

import imageio_ffmpeg
import psutil

HERE = Path(__file__).resolve().parent
ROOT = OCEAN_ROOT
OUT = HERE / 'resource-experiment'
BIN = OUT / 'resource-simulator'
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
PROFILES = {'cpu1': (1.0, 1), 'cpu4': (4.0, 4), 'shared1': (0.5, 1)}
STREAM_IDS = {'D2': 1, 'V1': 4, 'I1': 5}

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temp.replace(path)

def controlled_worker(stream, stage, raw, target, result, profile):
    if result.exists():
        cached = json.loads(result.read_text())
        if 'quota_cpu_seconds_per_second' in cached:
            return cached
    quota, threads = PROFILES[profile]
    result.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, str(HERE/'codec_worker.py'), '--stream', stream, '--stage', stage,
           '--input', str(raw), '--output', str(target), '--result', str(result),
           '--threads', str(threads), '--ffmpeg', FFMPEG]
    env = dict(os.environ, OMP_NUM_THREADS=str(threads), OPENBLAS_NUM_THREADS=str(threads))
    with result.with_suffix('.stderr.log').open('w') as log:
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=log, text=True, start_new_session=True, env=env)
        if process.stdout.readline().strip() != 'READY':
            process.wait()
            raise RuntimeError(f'Worker initialization failed: {result}')
        parent = psutil.Process(process.pid)
        t0 = parent.cpu_times()
        baseline = t0.user+t0.system
        ledger = {process.pid: baseline}
        started = time.perf_counter()
        process.stdin.write('GO\n')
        process.stdin.flush()
        stopped = False
        stops = 0
        paused = 0.0
        max_cpu_error = 0.0
        try:
            while process.poll() is None:
                try:
                    family = [parent]+parent.children(recursive=True)
                    for member in family:
                        try:
                            ct = member.cpu_times()
                            ledger[member.pid] = ct.user+ct.system
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                except psutil.NoSuchProcess:
                    break
                cpu = max(0.0, sum(ledger.values())-baseline)
                elapsed = time.perf_counter()-started
                max_cpu_error = max(max_cpu_error, cpu-quota*elapsed)
                debt = cpu/quota-elapsed
                if debt > 0.003:
                    try:
                        os.killpg(process.pid, signal.SIGSTOP)
                    except (ProcessLookupError, PermissionError):
                        if process.poll() is not None:
                            break
                        raise
                    stopped = True
                    stops += 1
                    pause_start = time.perf_counter()
                    time.sleep(min(debt, 0.04))
                    paused += time.perf_counter()-pause_start
                    try:
                        os.killpg(process.pid, signal.SIGCONT)
                    except (ProcessLookupError, PermissionError):
                        if process.poll() is None:
                            raise
                    stopped = False
                else:
                    time.sleep(0.003)
                if time.perf_counter()-started > 300:
                    raise TimeoutError(str(result))
            remaining = process.stdout.read()
            rc = process.wait()
            if rc or not result.exists():
                raise RuntimeError(f'Worker failed rc={rc}: {result}; {remaining}')
        finally:
            if stopped:
                os.killpg(process.pid, signal.SIGCONT)
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait()
    measured = json.loads(result.read_text())
    measured.update(cpu_profile=profile, quota_cpu_seconds_per_second=quota,
                    limiter_stops=stops, limiter_paused_s=paused,
                    limiter_max_observed_budget_error_cpu_s=max_cpu_error,
                    controller_poll_s=0.003, controller_burst_tolerance_s=0.003)
    write_json(result, measured)
    return measured

def codec_measure(stream, raw, profile, replicate):
    path = OUT/'codec'/profile/stream/f'rep-{replicate}'
    path.mkdir(parents=True, exist_ok=True)
    encoded = path/('payload.mp4' if stream == 'V1' else 'payload.encoded')
    c = controlled_worker(stream, 'compress', raw, encoded, path/'compression.json', profile)
    d = controlled_worker(stream, 'decompress', encoded, path/'decompressed', path/'decompression.json', profile)
    if stream == 'D2':
        assert c['raw_sha256'] == d['restored_sha256']
        assert c['raw_bytes'] == d['restored_bytes']
    elif stream == 'I1':
        assert (d['width'], d['height']) == (1280, 720)
    else:
        assert d['decoded_frames'] > 0
    assert hashlib.sha256(encoded.read_bytes()).hexdigest() == c['compressed_sha256']
    return dict(stream=stream, profile=profile, replicate=replicate, raw_path=str(raw),
                compressed_path=str(encoded), raw_bytes=c['raw_bytes'],
                compressed_bytes=c['compressed_bytes'], compression_s=c['per_object_s'],
                decompression_s=d['per_object_s'], raw_sha256=c['raw_sha256'],
                compressed_sha256=c['compressed_sha256'])

def network_trial(codec, cfg):
    path = OUT/'network'/cfg['resource']/cfg['quality']/codec['stream']/f"rep-{codec['replicate']}"
    path.mkdir(parents=True, exist_ok=True)
    result = path/'trace.csv'
    if not result.exists():
        with (path/'files.tsv').open('w', newline='') as f:
            w = csv.writer(f, delimiter='\t')
            w.writerow(['id','stream','raw_path','encoded_path','raw_bytes','encoded_bytes','first_s',
                        'deadline_s','encode_s','decode_s','raw_decode_s','raw_choices','comp_choices'])
            w.writerow([0, STREAM_IDS[codec['stream']], codec['raw_path'], codec['compressed_path'],
                        codec['raw_bytes'], codec['compressed_bytes'], 1., 1.,
                        codec['compression_s'], codec['decompression_s'], 0., '2', '2'])
        with (path/'events.tsv').open('w', newline='') as f:
            w = csv.writer(f, delimiter='\t')
            w.writerow(['time','id','offset','length'])
            for offset in range(0, codec['raw_bytes'], 1472):
                w.writerow([1., 0, offset, min(1472, codec['raw_bytes']-offset)])
        with (path/'link.csv').open('w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['time_min','phase','capacity_mbps','rtt_ms','packet_loss_rate','severity'])
            w.writerow([0, 'controlled', cfg['bandwidth_mbps'], cfg['rtt_ms'], 0., 0.])
        command = [str(BIN), '--input='+str(path), '--output='+str(result), '--variant=WO_PROTOCOL',
                   '--duration=3600', '--drain=0', '--seed='+str(31+codec['replicate']), '--cacheBytes=50000000']
        with (path/'ns3.log').open('w') as log:
            subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    with result.open() as f:
        row = next(csv.DictReader(f))
    assert row['status'] == 'delivered'
    assert int(row['protocol']) == 2
    assert int(row['wire_file_bytes']) == codec['compressed_bytes']
    assembled, start, received, done = [float(row[k]) for k in ['assembled_s','tx_start_s','received_s','decoded_s']]
    assert abs(start-assembled-codec['compression_s']) < 1e-8
    assert abs(done-received-codec['decompression_s']) < 1e-8
    return dict(**codec, **cfg, jct_s=done-assembled, transport_s=received-start,
                first_byte_e2e_s=done-float(row['first_s']), assembly_s=assembled-float(row['first_s']),
                queue_s=start-assembled-codec['compression_s'], status=row['status'], protocol='TCP_CUBIC',
                trace=str(result))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--calibration-only', action='store_true')
    parser.add_argument('--codec-only', action='store_true')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    calibration = {}
    for profile in PROFILES:
        m = controlled_worker('calibration','burn', HERE/'case_measurements.json', OUT/'unused',
                              OUT/'calibration'/f'{profile}.json', profile)
        rate = m['batch_cpu_s']/m['batch_wall_s']
        calibration[profile] = dict(cpu_per_wall=rate, quota=PROFILES[profile][0],
                                    batch_cpu_s=m['batch_cpu_s'], batch_wall_s=m['batch_wall_s'])
        if rate > PROFILES[profile][0]*1.15+0.03:
            raise RuntimeError(f'CPU quota calibration failed: {profile} {rate}')
        print(f'CALIBRATION {profile}: {rate:.3f} CPU-s/s', flush=True)
    write_json(OUT/'cpu-calibration.json', calibration)
    if args.calibration_only:
        return
    case = json.loads((HERE/'case_measurements.json').read_text())
    assets = {}
    definitions = json.loads((ROOT/'04_ablation_experiments/system_20260928/prepared/files.json').read_text())
    for m in case['samples']:
        f = next(f for f in definitions if m['source_sha256'] in f['raw_path'])
        assets[m['stream']] = Path(f['raw_path'])
        assert hashlib.sha256(assets[m['stream']].read_bytes()).hexdigest() == m['source_sha256']
    cfgs = []
    for quality, rtt in [('Poor',194.38),('Medium',153.61),('Good',85.04)]:
        cfgs.append(dict(resource='Delay',quality=quality,rtt_ms=rtt,bandwidth_mbps=2,cpu_profile='cpu1'))
    for quality, bw in [('Poor',2),('Medium',4),('Good',10)]:
        cfgs.append(dict(resource='BW',quality=quality,rtt_ms=153.61,bandwidth_mbps=bw,cpu_profile='cpu1'))
    for quality, profile in [('Poor','shared1'),('Medium','cpu1'),('Good','cpu4')]:
        cfgs.append(dict(resource='CPU',quality=quality,rtt_ms=153.61,bandwidth_mbps=2,cpu_profile=profile))
    write_json(OUT/'run-config.json', dict(
        repeats=args.repeats, configs=cfgs, protocol='TCP_CUBIC', topology='N0-N1-N2-N3',
        codec_measurement='real constrained compression and decompression; per-recorded-replicate replay in ns-3',
        shared_cpu_implementation='software CPU-time quota 0.5, representing fixed 50% availability of one shared vCPU; not a physical pinned-core contention experiment',
        dedicated_cpu_implementation='aggregate process-group CPU-time quotas 1.0/4.0; FFmpeg worker pools 1/4',
        profiles=PROFILES, horizon_s=3600, loss_rate=0.,
        start_definition='complete raw file assembled and byte-verified at N1',
        completion_definition='N3 verifies actual compressed payload and finishes measured decompression',
        tiny_codec_iterations={'D2': {'compress':10000,'decompress':40000}, 'I1': {'compress':50,'decompress':500}, 'V1': {'compress':1,'decompress':1}},
        paired_design='same measured codec replicate reused across the Delay/BW and CPU-Medium conditions; network configs isolated per file',
        ns3_binary_sha256=hashlib.sha256(BIN.read_bytes()).hexdigest(),
        ffmpeg=FFMPEG, ffmpeg_sha256=hashlib.sha256(Path(FFMPEG).read_bytes()).hexdigest(),
        dependency_versions={p:importlib.metadata.version(p) for p in ['pillow','psutil','imageio-ffmpeg']},
        simulator_source=str(OUT/'resource-simulator.cc'),
        simulator_source_sha256=hashlib.sha256((OUT/'resource-simulator.cc').read_bytes()).hexdigest(),
        simulator_rtt_implementation='Seconds(rtt_ms/2000.0), preserving fractional milliseconds',
        host=platform.platform(), cpu_count=os.cpu_count(), python=sys.version))
    measured = {}
    jobs = [(profile, stream, rep) for profile in PROFILES for stream in assets for rep in range(args.repeats)]
    random.Random(31).shuffle(jobs)
    for index, (profile, stream, rep) in enumerate(jobs, 1):
        c = codec_measure(stream, assets[stream], profile, rep)
        measured[(profile, stream, rep)] = c
        print(f'CODEC {index}/{len(jobs)} {profile}/{stream}/{rep}: '
              f"{c['compressed_bytes']} B; compression {c['compression_s']:.6f}s, decompression {c['decompression_s']:.6f}s", flush=True)
    write_json(OUT/'codec-measurements.json', list(measured.values()))
    if args.codec_only:
        return
    trials = []
    for cfg in cfgs:
        for stream in assets:
            for rep in range(args.repeats):
                r = network_trial(measured[(cfg['cpu_profile'],stream,rep)],cfg)
                trials.append(r)
        print(f"NETWORK {cfg['resource']}/{cfg['quality']}: complete {len(trials)} trials", flush=True)
    write_json(OUT/'trials.json', trials)
    summary = []
    for cfg in cfgs:
        for stream in assets:
            group = [r for r in trials if r['resource']==cfg['resource'] and r['quality']==cfg['quality'] and r['stream']==stream]
            summary.append(dict(stream=stream, **cfg, n=len(group),
                mean_jct_s=statistics.mean(r['jct_s'] for r in group),
                sd_jct_s=statistics.stdev(r['jct_s'] for r in group),
                mean_compression_s=statistics.mean(r['compression_s'] for r in group),
                mean_decompression_s=statistics.mean(r['decompression_s'] for r in group),
                mean_transport_s=statistics.mean(r['transport_s'] for r in group),
                mean_compressed_bytes=statistics.mean(r['compressed_bytes'] for r in group)))
    assert len(summary)==27 and len(trials)==27*args.repeats
    write_json(OUT/'summary.json', summary)
    with (OUT/'summary.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    print(f'COMPLETE: {len(trials)} trials, {len(summary)} plotted points', flush=True)

if __name__ == '__main__':
    main()
