#!/usr/bin/env python3
"""Create four ORIGINAL synthetic sound assets. No external recordings or samples.

Deterministic, CPU-only. The files are part of the authored MGF demo, never
replace user music or copy third-party audio. ffmpeg is needed only to regenerate.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess
import tempfile
import wave
import numpy as np

RATE = 22050


def _normalize(x, peak=.72):
    return (np.asarray(x, dtype=np.float64) * (peak / max(1e-5,np.max(np.abs(x))))).astype(np.float32)


def _periodic(duration, seed, low, high, exponent=1.1, harmonics=130):
    n=round(duration*RATE)
    t=np.arange(n,dtype=np.float64)/n
    rng=np.random.default_rng(seed)
    values=np.zeros(n,dtype=np.float64)
    for _ in range(harmonics):
        k=int(rng.integers(low,high))
        a=rng.uniform(.4,1.0)/(k**exponent)
        values+=a*np.sin(2*np.pi*k*t+rng.uniform(0,2*np.pi))
    return values


def _wind():
    n=RATE*9;t=np.arange(n)/RATE
    left=_periodic(9,743,1,280,.65,220)
    right=_periodic(9,1993,1,270,.64,220)
    swell=.69+.2*np.sin(2*np.pi*t/9)+.11*np.cos(2*np.pi*3*t/9)
    return _normalize(np.stack([left*swell,right*swell],axis=1),.34)


def _drone():
    n=RATE*8;t=np.arange(n)/RATE
    a=.4*np.sin(2*np.pi*55*t)+.23*np.sin(2*np.pi*82.5*t)+.09*np.sin(2*np.pi*110*t)
    b=.35*np.sin(2*np.pi*55*t+.2)+.19*np.sin(2*np.pi*82.5*t-.35)
    noise=_periodic(8,3901,16,220,.9,75)
    pulse=.61+.24*np.sin(2*np.pi*2*t/8)+.15*np.cos(2*np.pi*t/8)
    return _normalize(np.stack([(a+.15*noise)*pulse,(b+.13*noise)*pulse],axis=1),.27)


def _footstep():
    n=round(RATE*.36);t=np.arange(n)/RATE
    rng=np.random.default_rng(433)
    raw=rng.normal(size=n)
    smoothed=np.convolve(raw,np.ones(15)/15,mode='same')
    thump=np.sin(2*np.pi*(76*t-130*t*t)) * np.exp(-t*28)
    crack=smoothed*np.exp(-t*18)
    envelope=np.minimum(1,t*200)*np.exp(-t*13)
    mix=.6*thump+.35*crack*envelope
    return _normalize(np.stack([mix,mix*.96],axis=1),.54)


def _rune():
    n=round(RATE*1.6);t=np.arange(n)/RATE
    bell=sum(a*np.sin(2*np.pi*f*t) for a,f in [(1,523.25),(.38,784.9),(.13,1046.5),(.07,1568)])
    shimmer=.15*np.sin(2*np.pi*(1277*t+190*t*t))
    fade=(1-np.exp(-t*60))*np.exp(-t*2.8)
    sound=(bell+shimmer)*fade
    return _normalize(np.stack([sound,.90*sound],axis=1),.53)


def save_track(out:Path,name:str,audio:np.ndarray):
    with tempfile.TemporaryDirectory() as td:
        wav=Path(td)/f'{name}.wav'
        with wave.open(str(wav),'wb') as w:
            w.setnchannels(2);w.setsampwidth(2);w.setframerate(RATE)
            w.writeframes((np.clip(audio,-1,1)*32767).astype('<i2').tobytes())
        for ext,opts in [('ogg',['-c:a','libvorbis','-q:a','1']),('mp3',['-c:a','libmp3lame','-b:a','48k'])]:
            dest=out/f'{name}.{ext}'
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-i',str(wav),'-map_metadata','-1',*opts,str(dest)],check=True,timeout=30)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True)
    a=p.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    for name,fn in [('wind',_wind),('drone',_drone),('step',_footstep),('rune',_rune)]:
        save_track(out,name,fn())
    (out/'SOURCE.txt').write_text('Original deterministic synthesized MGF demo audio; created with scripts/audio_synthesis.py. No third-party recordings.\n',encoding='utf8')
    print('Original sound pack:',out)

if __name__=='__main__':main()
