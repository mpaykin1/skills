# SPDX-License-Identifier: GPL-3.0-only
"""Offline scene acoustics for original MUSIC renders, using Spotify Pedalboard.
Never run inside a browser or ship the Python DSP engine with a game.
"""
import argparse
import json
import math
import os
from pathlib import Path
import tempfile
import numpy as np
import soundfile as sf
import pedalboard as pb

# high-pass, low shelf gain, high shelf gain, compression threshold, ratio,
# room size, damping, wet fraction. One board processes the full stereo mix.
PRESETS = {
    'intimate': (30, -0.5, -1, -20, 1.4, .25, .65, .10),
    'white-hall': (35, -1.5, -1.5, -18, 1.5, .78, .55, .20),
    'nocturne': (30, -.5, -3, -22, 1.5, .48, .7, .15),
    'combat': (45, -2, 1.0, -18, 2.4, .28, .65, .08),
    'cathedral': (40, -2, -2, -20, 1.6, .9, .6, .26),
}

def make_board(preset):
    hp, low, high, th, ratio, room, damping, wet = PRESETS[preset]
    return pb.Pedalboard([
        pb.HighpassFilter(cutoff_frequency_hz=hp),
        pb.LowShelfFilter(cutoff_frequency_hz=160, gain_db=low),
        pb.HighShelfFilter(cutoff_frequency_hz=5500, gain_db=high),
        pb.Compressor(threshold_db=th, ratio=ratio, attack_ms=20, release_ms=160),
        pb.Reverb(room_size=room, damping=damping, wet_level=wet, dry_level=1-wet, width=1),
    ])

def process(source, output, preset='white-hall', tail=0., peak_db=-3.):
    source, output = Path(source), Path(output)
    if source.resolve()==output.resolve() or output.exists(): raise FileExistsError(output)
    if source.suffix.lower() not in ('.wav','.flac','.aif','.aiff') or output.suffix.lower()!='.wav':
        raise ValueError('Use local lossless input and new WAV output')
    if preset not in PRESETS or not math.isfinite(tail) or not 0<=tail<=5 or not math.isfinite(peak_db) or not -12<=peak_db<=-1:
        raise ValueError('Invalid preset, tail (0–5 s) or peak (-12 to -1 dBFS)')
    info=sf.info(source)
    if info.samplerate not in (22050,32000,44100,48000) or info.channels not in (1,2) or not 1<=info.duration<=360 or info.duration+tail>360:
        raise ValueError('Expected 1–360 s mono/stereo PCM at supported sample rate')
    x,sr=sf.read(source,dtype='float32',always_2d=True)
    if not np.isfinite(x).all() or np.max(np.abs(x))<1e-6: raise ValueError('Invalid or silent input')
    x=np.repeat(x,2,axis=1) if x.shape[1]==1 else x
    n=len(x); extra=round(tail*sr)
    audio=np.ascontiguousarray(np.pad(x,((0,extra),(0,0))).T)
    y=make_board(preset)(audio,sr,reset=True)
    if y.shape!=audio.shape or not np.isfinite(y).all(): raise RuntimeError('Invalid DSP output')
    # A common attenuation only; no independent stem normalization. FFmpeg handles LUFS/true peak later.
    peak=float(np.max(np.abs(y))); gain=min(1.,10**(peak_db/20)/max(peak,1e-12))
    y*=gain
    if extra:
        fade=min(extra,round(.06*sr)); y[:,-fade:]*=np.linspace(1,0,fade,dtype=np.float32)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='.music-fx-') as d:
        tmp=Path(d)/'fx.wav';sf.write(tmp,y.T,sr,subtype='FLOAT')
        os.link(tmp,output)  # atomic no-overwrite publish
    return dict(engine='Pedalboard',preset=preset,rate=sr,sourceFrames=n,outputFrames=y.shape[1],tailFrames=extra,peakDbfs=20*math.log10(max(float(np.max(np.abs(y))),1e-12)),gain=gain)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--preset',choices=PRESETS,default='white-hall');p.add_argument('--tail',type=float,default=0);p.add_argument('--peak',type=float,default=-3)
    a=p.parse_args();print(json.dumps(process(a.input,a.output,a.preset,a.tail,a.peak)))

if __name__=='__main__':main()
