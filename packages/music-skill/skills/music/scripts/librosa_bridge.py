"""Offline analysis and reference-based selection of original MUSIC audio.
Librosa 0.11.0 (ISC); use actual audio, never modify the score.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile

import librosa
import numpy as np

SR = 22050
HOP = 512
NAMES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

def analyze(path):
    path = Path(path)
    # FFmpeg decodes every game export codec consistently, bounded to six minutes.
    cmd = ['ffmpeg','-nostdin','-v','error','-i',str(path),'-vn','-ac','1','-ar',str(SR),'-t','361','-f','f32le','pipe:1']
    data = subprocess.run(cmd, check=True, capture_output=True, timeout=120).stdout
    y = np.frombuffer(data, dtype='<f4').copy()
    if len(y) < SR or len(y) > SR*360 or not np.isfinite(y).all() or np.max(np.abs(y)) < 1e-5:
        raise ValueError('Expected audible audio of 1–360 seconds')
    # Relative spectral and timing descriptors, invariant to uniform gain.
    y /= np.max(np.abs(y))
    S = np.abs(librosa.stft(y, n_fft=2048, hop_length=HOP))
    rms = librosa.feature.rms(S=S, frame_length=2048)[0]
    active = rms > max(float(rms.max())*.025, 1e-5)
    if not active.any(): raise ValueError('No active audio frames')
    chroma = librosa.feature.chroma_stft(S=S**2, sr=SR, hop_length=HOP, tuning=0)
    hist = np.average(chroma[:,active],axis=1,weights=rms[active]); hist /= max(hist.sum(),1e-12)
    centroid = librosa.feature.spectral_centroid(S=S,sr=SR)[0]
    onset = librosa.onset.onset_strength(y=y,sr=SR,hop_length=HOP)
    tempo, beats = librosa.beat.beat_track(onset_envelope=onset,sr=SR,hop_length=HOP)
    bpm = float(np.asarray(tempo).reshape(-1)[0])
    attacks = librosa.onset.onset_detect(onset_envelope=onset,sr=SR,hop_length=HOP)
    # Eight relative-time segments support coarse structure comparison across renditions.
    segments=[]
    for indexes in np.array_split(np.arange(chroma.shape[1]),8):
        ix=indexes[active[indexes]]
        h=np.average(chroma[:,ix],axis=1,weights=rms[ix]) if len(ix) else np.zeros(12)
        segments.append((h/max(h.sum(),1e-12)).tolist())
    duration=len(y)/SR
    with path.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(schema='music-audio-profile-v1',engine='librosa',version=librosa.__version__,source=str(path),sha256=digest,
                duration=duration,tempoEstimate=bpm if len(beats)>=4 and math.isfinite(bpm) else None,
                beatCount=int(len(beats)),onsetsPerSecond=len(attacks)/duration,
                centroidHz=float(np.average(centroid[active],weights=rms[active])),
                chroma=hist.tolist(),chromaSegments=segments,
                prominentPitchClasses=[NAMES[i] for i in np.argsort(-hist)[:4]])

def distance(a,b):
    # Distances are heuristic, not objective quality ratings or key recognition.
    def cosine(x,y):
        x,y=np.asarray(x),np.asarray(y); d=np.linalg.norm(x)*np.linalg.norm(y)
        return float(np.clip(1-np.dot(x,y)/d,0,1)) if d>1e-12 else (0. if not x.any() and not y.any() else 1.)
    chroma=cosine(a['chroma'],b['chroma'])
    structure=float(np.mean([cosine(x,y) for x,y in zip(a['chromaSegments'],b['chromaSegments'])]))
    def relative(x,y): return min(1.,abs(math.log(max(x,1e-6)/max(y,1e-6))))
    attack=relative(a['onsetsPerSecond'],b['onsetsPerSecond'])
    brightness=relative(a['centroidHz'],b['centroidHz'])
    tempo=None
    if a['tempoEstimate'] and b['tempoEstimate']:
        # Beat trackers can report half/double time; avoid penalizing that ambiguity.
        tempo=min(relative(a['tempoEstimate'],b['tempoEstimate']*k) for k in (.5,1,2))
    terms=[(.45,chroma),(.25,structure),(.15,attack),(.10,brightness)]
    if tempo is not None: terms.append((.05,tempo))
    return dict(distance=sum(w*d for w,d in terms)/sum(w for w,d in terms),chromaDistance=chroma,
                structureDistance=structure,onsetDistance=attack,brightnessDistance=brightness,tempoDistance=tempo,
                durationDelta=abs(a['duration']-b['duration']))

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('profile');q.add_argument('audio',type=Path);q.add_argument('--out',type=Path)
    q=sub.add_parser('rank');q.add_argument('reference',type=Path);q.add_argument('candidates',type=Path,nargs='+');q.add_argument('--out',type=Path)
    q=sub.add_parser('master');q.add_argument('audio',type=Path);q.add_argument('--out',type=Path,required=True);q.add_argument('--target',type=float,default=-18);q.add_argument('--peak',type=float,default=-2)
    a=p.parse_args()
    if a.cmd=='profile': result=analyze(a.audio)
    elif a.cmd=='rank':
        if len(a.candidates)>16: p.error('Maximum 16 candidates')
        ref=analyze(a.reference); ranked=[]
        for candidate in a.candidates:
            prof=analyze(candidate); ranked.append(dict(path=str(candidate),sha256=prof['sha256'],**distance(ref,prof)))
        result=dict(schema='music-audio-ranking-v1',reference=ref,ranked=sorted(ranked,key=lambda v:v['distance']))
    else:
        if a.out.exists(): raise FileExistsError(a.out)
        before=analyze(a.audio); a.out.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=a.out.parent,prefix='.music-master-') as tmp:
            rendered=Path(tmp)/a.out.name
            subprocess.run([sys.executable,str(Path(__file__).with_name('ffmpeg_bridge.py')),str(a.audio),'--out',str(rendered),'--target',str(a.target),'--peak',str(a.peak)],check=True,timeout=240,stdout=sys.stderr)
            after=analyze(rendered); d=distance(before,after)
            # Compare two renditions of the same input, not different compositions.
            if d['durationDelta']>.12 or d['chromaDistance']>.05 or d['structureDistance']>.12:
                raise ValueError(f'Master deviates from source; original retained: {d}')
            # Atomic publish, no overwrite even if another job created the destination.
            import os
            os.link(rendered,a.out)
        after['source']=str(a.out)
        result=dict(schema='music-master-check-v1',source=before,master=after,comparison=d)
    payload=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
    if a.cmd!='master' and a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        with a.out.open('x',encoding='utf-8') as f: f.write(payload+'\n')
    else: print(payload)

if __name__=='__main__': main()
