"""Measure real compression/decompression inside a controlled process group."""
import argparse
import gzip
import hashlib
import io
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stream', required=True)
    p.add_argument('--stage', required=True)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--result', type=Path, required=True)
    p.add_argument('--threads', type=int, default=1)
    p.add_argument('--ffmpeg', default='')
    a = p.parse_args()
    raw = a.input.read_bytes() if a.stream != 'calibration' else b''
    # Initialization is outside the measured interval and quota accounting.
    if a.stream == 'D2':
        gzip.decompress(gzip.compress(raw, compresslevel=6, mtime=0)) if a.stage == 'compress' else gzip.decompress(raw)
    elif a.stream == 'I1':
        with Image.open(io.BytesIO(raw)) as im:
            im.load()
            dims = im.size
    print('READY', flush=True)
    if sys.stdin.readline().strip() != 'GO':
        raise RuntimeError('Missing start signal')
    ru0 = resource.getrusage(resource.RUSAGE_SELF)
    ch0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    start = time.perf_counter()
    if a.stream == 'calibration':
        cmd = [sys.executable, '-c', 'import time\nt=time.process_time()\nwhile time.process_time()-t<0.3: pass']
        children = [subprocess.Popen(cmd) for _ in range(4)]
        for child in children:
            assert child.wait() == 0
        iterations = 1
        payload = b''
    elif a.stream == 'D2':
        iterations = 10000 if a.stage == 'compress' else 40000
        for _ in range(iterations):
            payload = gzip.compress(raw, compresslevel=6, mtime=0) if a.stage == 'compress' else gzip.decompress(raw)
    elif a.stream == 'I1':
        iterations = 50 if a.stage == 'compress' else 500
        for _ in range(iterations):
            with Image.open(io.BytesIO(raw)) as im:
                im.load()
                if a.stage == 'compress':
                    rgb = im.convert('RGB')
                    buffer = io.BytesIO()
                    rgb.save(buffer, format='JPEG', quality=75, optimize=True)
                    rgb.close()
                    payload = buffer.getvalue()
                else:
                    assert im.size == dims
                    payload = b''
    elif a.stream == 'V1':
        iterations = 1
        cmd = [a.ffmpeg, '-y', '-hide_banner', '-nostdin', '-v', 'error']
        if a.stage == 'compress':
            cmd += ['-threads:v', str(a.threads), '-i', str(a.input), '-map', '0:v:0', '-map', '0:a?',
                    '-c:v', 'libx265', '-preset', 'fast', '-crf', '30', '-pix_fmt', 'yuv420p',
                    '-x265-params', f'pools={a.threads}:frame-threads=1:lookahead-threads=1:log-level=error',
                    '-threads:v', str(a.threads), '-tag:v', 'hvc1', '-c:a', 'copy',
                    '-movflags', '+faststart', str(a.output)]
        else:
            cmd += ['-threads:v', str(a.threads), '-i', str(a.input), '-map', '0:v:0',
                    '-an', '-progress', str(a.output)+'.progress', '-f', 'null', '/dev/null']
        with a.result.with_suffix('.ffmpeg.log').open('w') as log:
            completed = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
        if completed.returncode:
            raise RuntimeError(f'FFmpeg returned {completed.returncode}')
        payload = b''
    else:
        raise ValueError(a.stream)
    wall = time.perf_counter()-start
    ru1 = resource.getrusage(resource.RUSAGE_SELF)
    ch1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (ru1.ru_utime+ru1.ru_stime-ru0.ru_utime-ru0.ru_stime +
           ch1.ru_utime+ch1.ru_stime-ch0.ru_utime-ch0.ru_stime)
    result = dict(stream=a.stream, stage=a.stage, batch_wall_s=wall,
                  batch_cpu_s=cpu, iterations=iterations, per_object_s=wall/iterations,
                  thread_limit=a.threads)
    if a.stream in ('D2', 'I1') and a.stage == 'compress':
        a.output.write_bytes(payload)
        result.update(raw_bytes=len(raw), compressed_bytes=len(payload),
                      raw_sha256=sha(raw), compressed_sha256=sha(payload))
    elif a.stream == 'D2':
        result.update(restored_sha256=sha(payload), restored_bytes=len(payload))
    elif a.stream == 'I1':
        result.update(width=dims[0], height=dims[1], integrity='decode_and_dimensions')
    elif a.stream == 'V1' and a.stage == 'compress':
        data = a.output.read_bytes()
        result.update(raw_bytes=len(raw), compressed_bytes=len(data),
                      raw_sha256=sha(raw), compressed_sha256=sha(data))
    elif a.stream == 'V1':
        progress = dict(line.split('=', 1) for line in Path(str(a.output)+'.progress').read_text().splitlines() if '=' in line)
        assert progress['progress'] == 'end'
        result.update(decoded_frames=int(progress['frame']), integrity='full_video_decode')
    a.result.write_text(json.dumps(result, indent=2))
    print('DONE', flush=True)

if __name__ == '__main__':
    main()
