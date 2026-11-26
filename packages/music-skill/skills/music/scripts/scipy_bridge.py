"""Offline alignment of complementary stems sharing an explicitly confirmed origin.
SciPy polyphase resampling, optional DC removal, and shared peak headroom.
"""
import argparse, json, math, shutil, tempfile, hashlib
from pathlib import Path
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly


def prepare(inputs, output, *, rate=48000, remove_dc=False, common_origin=False):
    paths=[Path(x).resolve(strict=True) for x in inputs]; out=Path(output).resolve()
    if not common_origin: raise ValueError('Confirm same musical start, clock and intended duration; no automatic alignment')
    if not 1<=len(paths)<=8 or len(set(paths))!=len(paths) or out.exists(): raise ValueError('1–8 distinct inputs and new output directory required')
    if rate not in (32000,44100,48000): raise ValueError('Unsupported output rate')
    infos=[sf.info(p) for p in paths]; ch=infos[0].channels
    if ch not in (1,2) or any(i.channels!=ch or i.format not in ('WAV','WAVEX','FLAC','AIFF') or i.samplerate not in (32000,44100,48000,88200,96000) or not 0<i.frames<=180*i.samplerate for i in infos): raise ValueError('Lossless mono/stereo sources of <=180 seconds with identical channel layout required')
    duration=infos[0].frames/infos[0].samplerate; frames=round(duration*rate)
    for i in infos:
        if abs(i.frames/i.samplerate-duration)>1/i.samplerate+1/rate: raise ValueError('Different source durations; align explicitly before resampling')
    if frames<1: raise ValueError('Empty output')
    out.parent.mkdir(parents=True,exist_ok=True); tmp=Path(tempfile.mkdtemp(prefix='.music-resample-',dir=out.parent)); records=[]; bound=0.
    try:
        for j,(p,i) in enumerate(zip(paths,infos)):
            x,sr=sf.read(p,dtype='float64',always_2d=True)
            if sr!=i.samplerate or x.shape!=(i.frames,ch) or not np.isfinite(x).all(): raise ValueError('Invalid samples')
            dc=x.mean(axis=0)
            if remove_dc: x-=dc
            g=math.gcd(sr,rate); y=resample_poly(x,rate//g,sr//g,axis=0,window=('kaiser',8.6),padtype='constant') if sr!=rate else x
            correction=frames-len(y)
            if abs(correction)>3: raise ValueError('Unexpected duration discrepancy')
            if correction>0: y=np.pad(y,((0,correction),(0,0)))
            else: y=y[:frames]
            if not np.isfinite(y).all(): raise ValueError('Nonfinite resampler output')
            peak=float(np.max(np.abs(y))); bound+=peak
            filename=f'stem-{j+1:02d}.wav'; sf.write(tmp/filename,y,rate,subtype='FLOAT')
            records.append({'file':filename,'source':p.name,'sourceRate':sr,'sourceFrames':i.frames,'lengthCorrectionFrames':correction,'sourceDC':dc.tolist(),'samplePeakBeforeGain':peak})
            del x,y
        if bound<=1e-10: raise ValueError('Silent stem set')
        gain=min(1.,10**(-2/20)/bound)
        for r in records:
            p=tmp/r['file']; y,_=sf.read(p,dtype='float64',always_2d=True); sf.write(p,y*gain,rate,subtype='FLOAT'); info=sf.info(p)
            if (info.frames,info.samplerate,info.channels)!=(frames,rate,ch): raise RuntimeError('Output alignment mismatch')
            with p.open('rb') as f:r['sha256']=hashlib.file_digest(f,'sha256').hexdigest()
        manifest={'schema':'music-aligned-stems-v1','engine':'SciPy resample_poly','sampleRate':rate,'channels':ch,'frames':frames,'durationSeconds':frames/rate,'commonGain':gain,'dcRemoved':remove_dc,'stems':records}
        (tmp/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
        if out.exists(): raise FileExistsError(out)
        tmp.rename(out); return manifest
    finally:
        if tmp.exists(): shutil.rmtree(tmp)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('inputs',nargs='+');p.add_argument('--out',required=True);p.add_argument('--rate',type=int,default=48000);p.add_argument('--remove-dc',action='store_true');p.add_argument('--common-origin',action='store_true',required=True);a=p.parse_args();print(json.dumps(prepare(a.inputs,a.out,rate=a.rate,remove_dc=a.remove_dc,common_origin=a.common_origin),ensure_ascii=False))
if __name__=='__main__':main()
