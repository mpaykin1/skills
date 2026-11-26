"""Prepare sample-aligned lossless loop packs from complementary rendered stems.
Uses real SoundFile/libsndfile. Explicit beat-aligned pre-roll is required.
"""
import argparse, hashlib, json, math, shutil, tempfile
from pathlib import Path
import numpy as np
import soundfile as sf


def pack(inputs, output, *, bpm, bars, beats=4, start_frame, fade_ms=30, weights=None):
    paths=[Path(p).resolve(strict=True) for p in inputs]; out=Path(output).resolve()
    if not 1<=len(paths)<=8 or len(set(paths))!=len(paths) or out.exists():
        raise ValueError('1–8 distinct complementary stems and a new output directory required')
    if not math.isfinite(bpm) or not 30<=bpm<=220 or type(bars)!=int or not 1<=bars<=64 or beats not in (2,3,4,6):
        raise ValueError('Invalid quarter-note tempo or meter (beats = quarter notes per bar)')
    if type(start_frame)!=int or start_frame<0 or not 5<=fade_ms<=100: raise ValueError('Invalid start or fade')
    if len(paths)>1 and weights is None: raise ValueError('Explicit gains required for complementary stems')
    weights=[1.] if weights is None else list(weights)
    if len(weights)!=len(paths) or any(not math.isfinite(g) or not 0<g<=1 for g in weights): raise ValueError('Invalid gains')
    infos=[sf.info(p) for p in paths]; rate=infos[0].samplerate; channels=infos[0].channels
    if rate not in (32000,44100,48000) or channels not in (1,2) or any(i.samplerate!=rate or i.channels!=channels or i.format not in ('WAV','FLAC','AIFF','WAVEX') for i in infos):
        raise ValueError('Lossless input with identical sample rate/channel count required; align before export')
    frames=round(rate*60/bpm*bars*beats); fade=round(rate*fade_ms/1000)
    if frames>rate*180 or frames<fade*4 or start_frame<fade or any(i.frames<start_frame+frames for i in infos):
        raise ValueError('Need exact loop length, <=180 seconds, and genuine audio pre-roll')
    # Crossfade final samples into the audio immediately preceding the loop start.
    # Preserves the exact bar length; no inserted/removed samples inside the cycle.
    a=np.linspace(0.,1.,fade,dtype=np.float32)[:,None]; a=a*a*(3-2*a)
    out.parent.mkdir(parents=True,exist_ok=True)
    # Two passes avoid holding all stems in RAM. Bound the sum of absolute peaks
    # per channel so all independent 0..1 runtime gains remain below headroom.
    peak_bound=0.; data=[]
    def read_loop(path):
        x,sr=sf.read(path,start=start_frame-fade,frames=frames+fade,dtype='float32',always_2d=True)
        if sr!=rate or len(x)!=frames+fade or not np.isfinite(x).all(): raise ValueError('Invalid decoded audio')
        loop=x[fade:].copy(); loop[-fade:]=loop[-fade:]*(1-a)+x[:fade]*a
        return loop
    for p,w in zip(paths,weights):
        x=read_loop(p); peak=float(np.max(np.abs(x))); peak_bound+=peak*w
        # The seam jump now follows the original adjacent pre-roll sample pair.
        seam=float(np.max(np.abs(x[0]-x[-1]))); data.append((peak,seam)); del x
    if peak_bound<=1e-8: raise ValueError('Silent loop pack')
    gain=min(1.,10**(-2/20)/peak_bound)
    tmp=Path(tempfile.mkdtemp(prefix='.music-loop-',dir=out.parent))
    try:
        stems=[]
        for idx,(p,w,(_,seam)) in enumerate(zip(paths,weights,data)):
            x=read_loop(p)*np.float32(w*gain); filename=f'stem-{idx+1:02d}.wav'; dest=tmp/filename
            sf.write(dest,x,rate,subtype='PCM_24'); info=sf.info(dest)
            if (info.frames,info.samplerate,info.channels)!=(frames,rate,channels): raise RuntimeError('Loop export mismatch')
            with dest.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
            stems.append({'file':filename,'source':p.name,'bakedGain':w*gain,'seamJump':seam*w*gain,'sha256':digest}); del x
        manifest={'schema':'music-loop-pack-v1','engine':'SoundFile/libsndfile','sampleRate':rate,'channels':channels,'frames':frames,'durationSeconds':frames/rate,'bpm':bpm,'bars':bars,'beatsPerBar':beats,'startFrame':start_frame,'fadeFrames':fade,'commonGain':gain,'stems':stems,'license':'See source asset licenses; generated pack does not change them'}
        (tmp/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False,allow_nan=False))
        if out.exists(): raise FileExistsError(out)
        tmp.rename(out)
    finally:
        if tmp.exists(): shutil.rmtree(tmp)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('inputs',nargs='+'); p.add_argument('--out',required=True);p.add_argument('--bpm',type=float,required=True);p.add_argument('--bars',type=int,required=True);p.add_argument('--beats',type=int,default=4);p.add_argument('--start-frame',type=int,required=True);p.add_argument('--fade-ms',type=float,default=30);p.add_argument('--weights',nargs='+',type=float);p.add_argument('--compatible-boundaries',action='store_true',required=True,help='Confirm all stems have identical clock/phase and loop end is musically compatible with pre-roll')
    a=p.parse_args(); print(json.dumps(pack(a.inputs,a.out,bpm=a.bpm,bars=a.bars,beats=a.beats,start_frame=a.start_frame,fade_ms=a.fade_ms,weights=a.weights),ensure_ascii=False))
if __name__=='__main__':main()
