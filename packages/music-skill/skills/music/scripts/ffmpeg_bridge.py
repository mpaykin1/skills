"""Master rendered original music with system FFmpeg, without altering scores.
Inputs are alternative masters OR explicitly complementary, zero-aligned stems.
"""
import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import sys

FORMATS={'.wav':['-c:a','pcm_s16le'],'.ogg':['-c:a','libopus','-b:a','96k','-vbr','on'],'.mp3':['-c:a','libmp3lame','-b:a','128k'],'.m4a':['-c:a','aac','-b:a','128k','-movflags','+faststart']}

def run(exe,args):
    r=subprocess.run([exe,*args],capture_output=True,text=True,timeout=180,check=False)
    if r.returncode: raise RuntimeError(r.stderr[-3000:])
    return r

def probe(path,ffprobe):
    r=run(ffprobe,['-v','error','-show_streams','-show_format','-of','json',str(path)])
    d=json.loads(r.stdout); streams=[s for s in d['streams'] if s['codec_type']=='audio']
    if len(streams)!=1: raise ValueError('Expected one audio stream')
    s=streams[0]; duration=float(s.get('duration',d['format'].get('duration',0)))
    if not math.isfinite(duration) or not .5<=duration<=370: raise ValueError('Audio duration must be 0.5–370 seconds')
    return duration

def measure(ffmpeg,src,base):
    r=run(ffmpeg,['-hide_banner','-nostdin','-i',str(src),'-vn','-af',base+':print_format=json','-f','null','-'])
    matches=re.findall(r'\{[^{}]*"input_i"[^{}]*\}',r.stderr,re.S)
    if not matches: raise RuntimeError('Missing loudnorm measurements')
    d=json.loads(matches[-1]); fields=['input_i','input_tp','input_lra','input_thresh','target_offset']
    vals={k:float(d[k]) for k in fields}
    if not all(math.isfinite(v) for v in vals.values()): raise ValueError('Silent or invalid music; no mastering performed')
    return vals

def master(inputs,output,*,weights=None,target=-18,peak=-2,rate=48000,ffmpeg='ffmpeg',ffprobe='ffprobe'):
    inputs=[Path(p).resolve(strict=True) for p in inputs]; output=Path(output).resolve()
    if not 1<=len(inputs)<=8 or len(set(inputs))!=len(inputs): raise ValueError('1–8 distinct inputs required')
    if output.exists() or output.suffix.lower() not in FORMATS: raise ValueError('Choose new WAV, OGG, MP3 or M4A output')
    if not -24<=target<=-14 or not -4<=peak<=-1 or rate not in (32000,44100,48000): raise ValueError('Invalid mastering parameters')
    if output.suffix.lower()=='.ogg' and rate not in (48000,): raise ValueError('Use 48000 Hz for Opus')
    if not shutil.which(ffmpeg) or not shutil.which(ffprobe): raise RuntimeError('Install system FFmpeg and ffprobe')
    if any(p.suffix.lower() not in ('.wav','.flac','.aiff','.aif','.ogg','.mp3','.m4a') or not p.is_file() for p in inputs): raise ValueError('Local audio files only')
    durations=[probe(p,ffprobe) for p in inputs]
    if len(inputs)>1 and (weights is None or max(durations)-min(durations)>.1): raise ValueError('Stems need explicit gains and matching duration (100 ms tolerance); align them first')
    weights=weights or [1.]
    if len(weights)!=len(inputs) or any(not math.isfinite(w) or not 0<w<=1 for w in weights): raise ValueError('One gain in (0,1] per stem')
    output.parent.mkdir(parents=True,exist_ok=True)
    base=f'loudnorm=I={target}:TP={peak}:LRA=20'
    with tempfile.TemporaryDirectory(prefix='music-master-',dir=output.parent) as d:
        mix=Path(d)/'mix.wav'; rendered=Path(d)/('master'+output.suffix.lower())
        args=['-hide_banner','-nostdin','-v','error']
        for p in inputs: args+=['-i',str(p)]
        # Normalize sample format before mix; avoid independent loudness changes on stems.
        graph=';'.join(f'[{i}:a:0]aresample={rate},aformat=sample_fmts=fltp:channel_layouts=stereo,volume={w}[s{i}]' for i,w in enumerate(weights))
        graph+=';'+''.join(f'[s{i}]' for i in range(len(inputs)))+f'amix=inputs={len(inputs)}:duration=longest:normalize=0[m]'
        run(ffmpeg,[*args,'-filter_complex',graph,'-map','[m]','-c:a','pcm_f32le',str(mix)])
        m=measure(ffmpeg,mix,base)
        params=':'.join(f'{dest}={m[src]}' for src,dest in [('input_i','measured_I'),('input_tp','measured_TP'),('input_lra','measured_LRA'),('input_thresh','measured_thresh'),('target_offset','offset')])
        run(ffmpeg,['-hide_banner','-nostdin','-v','error','-i',str(mix),'-af',f'{base}:{params}:linear=true','-ar',str(rate),'-ac','2',*FORMATS[output.suffix.lower()],str(rendered)])
        # Re-measure actual encoded file; lossy encoders can overshoot true peak.
        actual=measure(ffmpeg,rendered,base); duration=probe(rendered,ffprobe)
        if abs(duration-max(durations))>.12: raise RuntimeError('Unexpected output duration')
        if actual['input_tp']>peak+.35: raise RuntimeError('Encoded true peak above tolerance; use lower --peak')
        if abs(actual['input_i']-target)>2: raise RuntimeError('Loudness target not reached; inspect input dynamics')
        if output.exists(): raise FileExistsError(output)
        rendered.rename(output)
    return {'file':str(output),'duration':duration,'bytes':output.stat().st_size,'lufs':actual['input_i'],'true_peak_dbtp':actual['input_tp']}

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('input',nargs='+'); p.add_argument('--out',required=True); p.add_argument('--weights',nargs='+',type=float); p.add_argument('--target',type=float,default=-18); p.add_argument('--peak',type=float,default=-2); p.add_argument('--rate',type=int,default=48000)
    p.add_argument('--soundfont',type=Path,help='Licensed SF2/SF3 for a MIDI or MUSIC JSON input')
    a=p.parse_args()
    opts=dict(weights=a.weights,target=a.target,peak=a.peak,rate=a.rate)
    if len(a.input)==1 and Path(a.input[0]).suffix.lower() in ('.json','.mid','.midi'):
        # Use the existing native renderer; never render the same arrangement twice.
        with tempfile.TemporaryDirectory(prefix='music-fluid-') as d:
            wav=Path(d)/'render.wav'
            cmd=[sys.executable,str(Path(__file__).with_name('fluidsynth_bridge.py')),str(Path(a.input[0]).resolve()),str(wav),'--rate',str(a.rate)]
            if a.soundfont: cmd+=['--soundfont',str(a.soundfont.resolve())]
            run(cmd[0],cmd[1:]); result=master([wav],a.out,**opts)
    else:
        if a.soundfont: p.error('--soundfont only applies to MIDI or MUSIC JSON')
        result=master(a.input,a.out,**opts)
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
