"""BS.1770 scene loudness matching with one gain per aligned stem group.
Uses installed pyloudnorm, SoundFile and SciPy. Offline, not a limiter.
"""
import argparse, json, math, re, tempfile, shutil
from pathlib import Path
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
from scipy.signal import resample_poly


def measure(x, rate):
    if not np.isfinite(x).all() or len(x) < rate*.4:
        raise ValueError('Need >=400 ms finite audio')
    value=float(pyln.Meter(rate).integrated_loudness(x))
    if not math.isfinite(value): raise ValueError('Silent or below loudness gate')
    return value


def peak(x):
    # Conservative estimate including intersample overshoot; not certified true peak.
    return max(float(np.max(np.abs(x))),float(np.max(np.abs(resample_poly(x,4,1,axis=0)))))


def match(config, out, base=Path('.'), target=-18., ceiling=-2.):
    out=Path(out).resolve(); base=Path(base).resolve()
    if out.exists() or not -30<=target<=-12 or not -6<=ceiling<=-1:
        raise ValueError('Use new output directory; target -30..-12 LUFS, ceiling -6..-1 dB')
    scenes=config.get('scenes'); ids=set()
    if not isinstance(scenes,list) or not 1<=len(scenes)<=24: raise ValueError('1..24 scenes required')
    out.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.loudness-',dir=out.parent)); result=[]
    try:
        for scene in scenes:
            name=scene['id']; stems=scene['stems']; offset=float(scene.get('offsetLU',0))
            if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',name) or name in ids or not -12<=offset<=6 or not 1<=len(stems)<=8: raise ValueError('Invalid scene')
            ids.add(name); paths=[(base/s['file']).resolve(strict=True) for s in stems]
            if len(set(paths))!=len(paths): raise ValueError('Duplicate stem')
            infos=[sf.info(p) for p in paths]; first=infos[0]; rate=first.samplerate; frames=first.frames; channels=first.channels
            if rate not in (32000,44100,48000) or channels not in (1,2) or not rate*.4<=frames<=rate*180: raise ValueError('Invalid scene format or duration')
            if any((i.frames,i.samplerate,i.channels)!=(frames,rate,channels) or i.format not in ('WAV','WAVEX','FLAC','AIFF') for i in infos): raise ValueError('Lossless, exactly aligned stems required')
            weights=[float(s.get('weight',1)) for s in stems]
            if any(not 0<w<=1 for w in weights): raise ValueError('Stem weights must be 0 < w <= 1')
            mix=np.zeros((frames,channels),dtype=np.float64); bound=0.
            def read(i):
                x,sr=sf.read(paths[i],dtype='float64',always_2d=True)
                if sr!=rate or x.shape!=mix.shape or not np.isfinite(x).all(): raise ValueError('Invalid source audio')
                return x*weights[i]
            for i in range(len(paths)):
                x=read(i); mix+=x; bound+=peak(x)
            before=measure(mix,rate); desired=target+offset
            # One scalar for every layer. Peak sum bounds arbitrary independent 0..1 layer gains.
            gain=min(10**((desired-before)/20),10**(ceiling/20)/bound,10**(18/20))
            achieved=measure(mix*gain,rate); folder=temp/name; folder.mkdir()
            outputs=[]
            for i,p in enumerate(paths):
                x=read(i)*gain; file=f'stem-{i+1:02d}.wav'; sf.write(folder/file,x,rate,subtype='FLOAT')
                info=sf.info(folder/file)
                if (info.frames,info.samplerate,info.channels)!=(frames,rate,channels): raise RuntimeError('Output timing mismatch')
                outputs.append({'file':f'{name}/{file}','source':p.name,'weight':weights[i],'bakedGain':weights[i]*gain})
            result.append({'id':name,'beforeLUFS':before,'targetLUFS':desired,'achievedLUFS':achieved,'commonGain':gain,'peakBoundDB':20*math.log10(bound*gain),'targetReached':abs(achieved-desired)<=.2,'sampleRate':rate,'frames':frames,'channels':channels,'stems':outputs})
        manifest={'schema':'music-loudness-scenes-v1','engine':'pyloudnorm','targetLUFS':target,'estimatedPeakCeilingDB':ceiling,'scenes':result}
        (temp/'manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False),encoding='utf-8')
        if out.exists(): raise FileExistsError(out)
        temp.rename(out); return manifest
    finally:
        if temp.exists(): shutil.rmtree(temp)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('config',type=Path);p.add_argument('output',type=Path);p.add_argument('--target',type=float,default=-18);p.add_argument('--ceiling',type=float,default=-2)
    a=p.parse_args();print(json.dumps(match(json.loads(a.config.read_text()),a.output,a.config.parent,a.target,a.ceiling),allow_nan=False))
if __name__=='__main__':main()
