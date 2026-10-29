"""Prepare real encoded payloads and exact-state XGBoost decisions for ns-3.

Encoded artifacts are measured once per distinct input and replayed with their
own measured processing delay. No report compression ratios or mean link states
are used. The ns-3 receiver verifies the transmitted payload bytes.
"""
from __future__ import annotations

# Paths for the consolidated ocean package.
import os
from pathlib import Path
OCEAN_ROOT = next(p for p in Path(__file__).resolve().parents if (p / '.ocean-root').is_file())
OCEAN_DATA = Path(os.environ.get('OCEAN_DATA_DIR', str(OCEAN_ROOT / 'data'))).expanduser().resolve()
OCEAN_IMAGE_DIR = Path(os.environ.get('OCEAN_IMAGE_DIR', str(OCEAN_ROOT.parent / '实验数据/图片文件'))).expanduser().resolve()
OCEAN_NS3 = Path(os.environ.get('OCEAN_NS3_ROOT', str(OCEAN_ROOT.parent / 'cache_exam/ns3-simulation-main/.tooling/ns-allinone-3.42/ns-3.42'))).expanduser().resolve()

import argparse, csv, gzip, hashlib, importlib.util, io, json, math, struct, sys, time
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from PIL import Image
from xgboost import XGBClassifier

HERE = Path(__file__).resolve().parent
ROOT = OCEAN_ROOT
CODECS = ROOT/'02_文件压缩/compression_scripts'
sys.path.insert(0, str(CODECS))
import run_edge_compression_experiment as edge
import run_parquet_optimization_experiment as columnar
import run_timeseries_optimization_experiment as ts
import run_video_compression_experiment as video
sys.path.insert(0, str(ROOT/'02_文件压缩/image_codecs'))
from actual_image_codec import encode_image

STREAMS = ['D1','D2','D3','D4','V1','I1']
PERIODS = [12.,12.,.02,120.]
WAITS = [120.,300.,1.,1800.]
VIDEO_SCHEMES = {'2019-05-30_18.50.28.mkv':'S1','4412e5bfafeaa07161d2082422e349e1.mp4':'S1'}

def digest(b): return hashlib.sha256(b).hexdigest()
def write_json(p, data): p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def load_module(name,p):
    spec=importlib.util.spec_from_file_location(name,p)
    obj=importlib.util.module_from_spec(spec); spec.loader.exec_module(obj); return obj

class Preparation:
    def __init__(self, args):
        self.args=args; self.out=args.output.resolve(); self.out.mkdir(parents=True,exist_ok=True)
        self.assets=self.out/'assets'; self.assets.mkdir(exist_ok=True)
        self.items=[]; self.events=[]; self.measurements={}; self.generated=np.zeros(6)

    def text_encode(self, ds, raw):
        start=time.perf_counter(); sid=ds.dataset_id[:2]
        if sid in ('D1','D3'):
            table=columnar.build_columnar_table(ds)
            buf=io.BytesIO()
            pq.write_table(table,buf,compression='zstd',compression_level=6,
                           use_dictionary=True,row_group_size=65536 if sid=='D3' else None)
            payload=buf.getvalue(); mid=time.perf_counter()
            restored=pq.read_table(io.BytesIO(payload)); end=time.perf_counter()
            if not columnar.tables_equal(table,restored): raise RuntimeError('Parquet roundtrip failed')
            alg='parquet_zstd6'; scope='typed_columns'; logical=len(table)
        elif sid=='D4':
            packets=ts.numeric_packets_for_candidate(ds,'d4_semantic_adcp',1024)
            packets=[p for p in packets if p.timestamps]
            if packets:
                encoded=[edge.encode_numeric_packet(p,'chimp') for p in packets]
                payload=b'OCCH1'+b''.join(struct.pack('>I',len(b))+b for b in encoded)
                mid=time.perf_counter()
                restored=[edge.decode_numeric_packet(b) for b in encoded]; end=time.perf_counter()
                if not all(edge.values_equal(a,b) for a,b in zip(packets,restored)): raise RuntimeError('Chimp roundtrip failed')
                alg='chimp_python_d4_semantic_1024'; scope='ADCP_numeric_observations'; logical=sum(len(p.timestamps) for p in packets)
            else:
                payload=gzip.compress(raw,compresslevel=6,mtime=0); mid=time.perf_counter()
                restored=gzip.decompress(payload); end=time.perf_counter()
                if restored!=raw: raise RuntimeError('Gzip roundtrip failed')
                alg='gzip6_no_ADCP_fields'; scope='byte_exact'; logical=len(ds.records)
        else:
            payload=gzip.compress(raw,compresslevel=6,mtime=0); mid=time.perf_counter()
            restored=gzip.decompress(payload); end=time.perf_counter()
            if restored!=raw: raise RuntimeError('Gzip roundtrip failed')
            alg='gzip6'; scope='byte_exact'; logical=len(ds.records)
        return payload,dict(algorithm=alg,encode_seconds=mid-start,decode_seconds=end-mid,
                            integrity_scope=scope,logical_rows=logical,raw_decode_seconds=0.)

    def artifact(self, stream, raw, ds=None, source=None):
        key=digest(raw); prefix=stream if stream!='I1' or self.args.image_quality==75 else f'I1-q{self.args.image_quality}'
        base=self.assets/(prefix+'-'+key)
        meta=base.with_suffix('.json'); rp=base.with_suffix('.raw'); cp=base.with_suffix('.encoded')
        if meta.exists() and rp.exists() and cp.exists():
            measure=json.loads(meta.read_text())
            if digest(cp.read_bytes())!=measure['encoded_sha256']: raise RuntimeError('Artifact digest mismatch')
        else:
            rp.write_bytes(raw)
            if ds is not None: payload,measure=self.text_encode(ds,raw)
            elif stream=='I1':
                payload,measure=encode_image(raw,self.args.image_quality)
                t=time.perf_counter()
                with Image.open(io.BytesIO(raw)) as im: im.load()
                measure['raw_decode_seconds']=time.perf_counter()-t
            else:
                scheme=next(s for s in video.SCHEMES if s.code==VIDEO_SCHEMES.get(source.name,'S2'))
                target=base.with_suffix('.mp4')
                rc,encode_ms,log=video.transcode(self.args.ffmpeg,source,target,scheme)
                if rc: raise RuntimeError(log[-4000:])
                rc,decode_ms,log=video.decode_to_null(self.args.ffmpeg,target)
                if rc: raise RuntimeError(log[-4000:])
                rc,raw_ms,log=video.decode_to_null(self.args.ffmpeg,source)
                if rc: raise RuntimeError(log[-4000:])
                payload=target.read_bytes()
                measure=dict(algorithm=scheme.code,encode_seconds=encode_ms/1000,
                    decode_seconds=decode_ms/1000,raw_decode_seconds=raw_ms/1000,
                    integrity_scope='lossy_video_full_decode')
            cp.write_bytes(payload)
            measure.update(stream=stream,raw_bytes=len(raw),encoded_bytes=len(payload),
                source_sha256=key,encoded_sha256=digest(payload),
                source=str(source) if source else 'assembled local records')
            write_json(meta,measure)
        self.measurements[str(base)]=measure
        return rp,cp,measure

    def item(self, sid, raw, arrivals, deadline, ds=None, source=None):
        rp,cp,m=self.artifact(STREAMS[sid],raw,ds,source)
        ident=len(self.items)
        item=dict(id=ident,stream=sid,raw_path=str(rp),encoded_path=str(cp),
            raw_bytes=len(raw),encoded_bytes=m['encoded_bytes'],first_s=arrivals[0][0],
            deadline_s=deadline,encode_s=m['encode_seconds'],decode_s=m['decode_seconds'],
            raw_decode_s=m['raw_decode_seconds'],algorithm=m['algorithm'],
            integrity_scope=m['integrity_scope'],record_count=len(arrivals))
        self.items.append(item)
        for t,offset,length in arrivals:
            if t<self.args.duration:
                self.events.append((t,ident,offset,length)); self.generated[sid]+=length

    def text(self):
        for ds in edge.discover_datasets(OCEAN_DATA):
            sid=int(ds.dataset_id[1])-1
            records=ds.records; prefix=[]
            if sid==0: prefix=records[:1]; records=records[1:]
            elif sid==1: prefix=records[:1]; records=records[1:]
            elif sid==2:
                while records and (records[0].text.startswith('StartTime') or records[0].text.startswith('address')):
                    prefix.append(records[0]); records=records[1:]
            n=math.ceil(self.args.duration/PERIODS[sid]); batch=[]; times=[]; batch_start=0.
            def flush(deadline):
                if not batch:return
                all_records=prefix+batch
                raw=b''.join(r.raw for r in all_records)
                arrivals=[]; offset=0
                for i,(r,t) in enumerate(zip(batch,times)):
                    length=len(r.raw)+(sum(len(p.raw) for p in prefix) if i==0 else 0)
                    arrivals.append((t,offset,length)); offset+=length
                newds=edge.Dataset(ds.dataset_id,ds.kind,all_records,ds.source_files,len(raw),ds.encoding)
                self.item(sid,raw,arrivals,deadline,ds=newds)
            size=0
            for i in range(n):
                t=i*PERIODS[sid]
                if batch and (t>=batch_start+WAITS[sid]-1e-8 or size>=ds.raw_size_bytes):
                    flush(min(batch_start+WAITS[sid],t)); batch=[];times=[];size=0
                if not batch: batch_start=t
                row=records[i%len(records)];batch.append(row);times.append(t);size+=len(row.raw)
            # Preserve the real timeout even if it exceeds the generation horizon.
            flush(batch_start+WAITS[sid])
            print('prepared',STREAMS[sid],len(self.items),'files',flush=True)

    def media(self):
        images=sorted((OCEAN_IMAGE_DIR).glob('*.png'),key=lambda p:(p.stat().st_size,p.name))
        image=images[len(images)//2]; raw=image.read_bytes()
        for step in range(math.ceil(self.args.duration/self.args.image_period)):
            t=step*self.args.image_period
            self.item(5,raw,[(t,0,len(raw))],t,source=image)
        paths=sorted(p for p in (OCEAN_DATA/'视频样本').iterdir() if p.suffix in ('.mp4','.mkv'))
        t=0.;index=0;rate=self.args.video_bytes_per_second
        while t<self.args.duration:
            p=paths[index%len(paths)]; raw=p.read_bytes();arrivals=[]
            for offset in range(0,len(raw),rate):
                length=min(rate,len(raw)-offset)
                arrivals.append((t+(offset+length)/rate,offset,length))
            self.item(4,raw,arrivals,t+len(raw)/rate,source=p)
            t+=len(raw)/rate;index+=1
            print('prepared video',index,p.name,flush=True)

    def decisions(self, links):
        modeldir=ROOT/'04_消融实验/xgboost_features/model'
        metadata=json.loads((modeldir/'metadata.json').read_text())
        pre=joblib.load(modeldir/'preprocessor.joblib'); model=XGBClassifier();model.load_model(modeldir/'xgboost.json')
        cols=metadata['numeric_features']+metadata['categorical_features']
        raw_rates=self.generated*8/self.args.duration/1e6
        cache={}; feature_records=[]
        for i,item in enumerate(self.items):
            for compressed in (False,True):
                size=item['encoded_bytes'] if compressed else item['raw_bytes']
                key=(item['stream'],item['raw_bytes'],size)
                if key not in cache:
                    count=math.ceil(size/1448);tail=size-(count-1)*1448;mean=size/count
                    rate=raw_rates[item['stream']]*size/item['raw_bytes']
                    interval=mean*8/max(rate,1e-12)/1000
                    features=[]
                    for j,link in enumerate(links):
                        prev=links[max(0,j-1)];loss=float(link['packet_loss_rate']);rtt=float(link['rtt_ms']);cap=float(link['capacity_mbps'])
                        row=dict(rtt_ms=rtt,capacity_mbps=cap,packet_loss_rate=loss,
                            phase_progress=j/max(1,len(links)-1),loss_trend=loss-float(prev['packet_loss_rate']),
                            capacity_trend=cap-float(prev['capacity_mbps']),rtt_trend=rtt-float(prev['rtt_ms']),
                            packet_size_min=min(1448,tail),packet_size_max=min(size,1448),packet_size_mean=mean,
                            packet_size_std=math.sqrt(((count-1)*(1448-mean)**2+(tail-mean)**2)/count),
                            interval_min_ms=interval,interval_max_ms=interval,interval_mean_ms=interval,interval_std_ms=0.,
                            offered_load_mbps=rate,file_size_mb=item['raw_bytes']/1e6,effective_file_size_mb=size/1e6,
                            compression_ratio=size/item['raw_bytes'],prev_rtt_ms=float(prev['rtt_ms']),
                            prev_capacity_mbps=float(prev['capacity_mbps']),prev_packet_loss_rate=float(prev['packet_loss_rate']),
                            source_scenario='rtt-80' if rtt<115 else 'rtt-150',
                            state_name='normal' if loss<.02 else 'degrading' if loss<.08 else 'bad-variable' if loss<.16 else 'severe',
                            interval_mode='fixed',traffic_mode='assembled-file',data_type='text' if item['stream']<4 else 'video' if item['stream']==4 else 'image',
                            prev_best_protocol='unknown')
                        features.append(row)
                    predictions=model.predict(pre.transform(pd.DataFrame(features)[cols])).astype(int)
                    cache[key]=''.join(str(p) for p in predictions)
                    feature_records.append(dict(stream=key[0],raw_bytes=key[1],sent_bytes=key[2],protocols=cache[key],
                        first_state_features=features[0]))
                item['comp_choices' if compressed else 'raw_choices']=cache[key]
            if i%1000==0:print('inference',i,'/',len(self.items),flush=True)
        write_json(self.out/'model-inputs.json',feature_records)
        return raw_rates.tolist()

    def run(self):
        self.text();self.media()
        profile=load_module('stage1_profile',ROOT/'shared/link_profile.py')
        links=profile.build_series(31,.5);profile.write_csv(links,self.out/'link.csv')
        rates=self.decisions(links)
        fields=['id','stream','raw_path','encoded_path','raw_bytes','encoded_bytes','first_s','deadline_s','encode_s','decode_s','raw_decode_s','raw_choices','comp_choices']
        with (self.out/'files.tsv').open('w') as f:
            w=csv.writer(f,delimiter='\t');w.writerow(fields)
            for item in self.items:w.writerow([item[k] for k in fields])
        with (self.out/'events.tsv').open('w') as f:
            w=csv.writer(f,delimiter='\t');w.writerow(['time','id','offset','length']);w.writerows(sorted(self.events))
        write_json(self.out/'files.json',self.items)
        write_json(self.out/'codec-measurements.json',list(self.measurements.values()))
        write_json(self.out/'run-config.json',dict(duration_s=self.args.duration,drain_s=self.args.drain,cache_bytes=self.args.cache_bytes,
            model=str(modeldir) if (modeldir:=ROOT/'04_消融实验/xgboost_features/model') else '',
            model_sha256=digest((modeldir/'xgboost.json').read_bytes()),
            text_max_wait_s=WAITS,record_period_s=PERIODS,raw_rates_mbps=rates,
            generated_raw_bytes=self.generated.tolist(),image_representative_bytes=258715,
            image_period_s=self.args.image_period,image_quality=self.args.image_quality,video_bytes_per_second=self.args.video_bytes_per_second,
            codec_timing='per-distinct-content measured encode and decode, deterministic replay',
            feature_pacing='per-file nominal fragment interval from actual generated stream byte rate',
            text_integrity='D1/D3 typed columns; D2 byte exact; D4 ADCP numeric fields (stage-two scope)',
            variants=['FULL','WO_PROTOCOL','WO_COMPRESSION','WO_CACHE','BASELINE']))
        print('READY',self.out,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--duration',type=float,default=3600)
    p.add_argument('--drain',type=float,default=300);p.add_argument('--cache-bytes',type=int,default=50000000)
    p.add_argument('--text-waits',default='120,300,1,1800');p.add_argument('--text-periods',default='12,12,0.02,120')
    p.add_argument('--image-period',type=float,default=1);p.add_argument('--image-quality',type=int,default=75)
    p.add_argument('--video-bytes-per-second',type=int,default=195875)
    p.add_argument('--output',type=Path,default=HERE/'prepared')
    p.add_argument('--ffmpeg',default=os.environ.get('FFMPEG', __import__('imageio_ffmpeg').get_ffmpeg_exe()))
    args=p.parse_args();WAITS[:]=[float(x) for x in args.text_waits.split(',')];PERIODS[:]=[float(x) for x in args.text_periods.split(',')]
    if len(WAITS)!=4 or len(PERIODS)!=4 or any(x<=0 for x in WAITS+PERIODS+[args.duration,args.image_period,args.video_bytes_per_second]):
        p.error('Exactly four positive waits/periods and positive production parameters are required')
    Preparation(args).run()
