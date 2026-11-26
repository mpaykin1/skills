"""Offline tempo matching of original MUSIC renders via FFmpeg/librubberband.
Keep score and input immutable. Export a new stereo WAV; no runtime GPL code.
"""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

from ffmpeg_bridge import probe


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=180)


def bpm(value):
    value = float(value)
    if not math.isfinite(value) or not 30 <= value <= 220:
        raise ValueError('BPM must be 30–220; use authoritative score BPM, not guessed tempo')
    return value


def stretch(source, target, source_bpm, target_bpm):
    source = Path(source).resolve(strict=True)
    if not source.is_file() or source.suffix.lower() not in ('.wav', '.flac', '.aiff', '.aif'):
        raise ValueError('Use original lossless audio')
    ratio = bpm(target_bpm) / bpm(source_bpm)
    if not .75 <= ratio <= 1.33:
        raise ValueError('Regenerate from score for larger tempo differences')
    duration = probe(source, 'ffprobe')
    if duration / ratio > 360 or duration < 1:
        raise ValueError('Expected 1–360 seconds after stretching')
    run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(source),'-vn',
         '-af',f'rubberband=tempo={ratio:.12f}:pitch=1:transients=mixed:channels=together:pitchq=quality',
         '-ar','48000','-ac','2','-c:a','pcm_f32le','-n',str(target)])
    actual = probe(target, 'ffprobe')
    if abs(actual-duration/ratio) > .12:
        raise ValueError(f'Stretched duration mismatch: {actual:.3f} vs {duration/ratio:.3f}')
    return actual


def check_harmony(original, stretched):
    from librosa_bridge import analyze, distance
    a,b = analyze(original), analyze(stretched)
    d=distance(a,b)
    if d['chromaDistance'] > .08 or d['structureDistance'] > .18:
        raise ValueError(f'Chroma/structure changed beyond tolerance: {d}')
    return {k:d[k] for k in ('chromaDistance','structureDistance')}


def prepare(source, output, source_bpm, target_bpm, *, verify=True):
    output=Path(output).resolve()
    if output.exists() or output.suffix.lower()!='.wav':
        raise ValueError('Use a new WAV output path')
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='.rubberband-') as tmp:
        staged=Path(tmp)/'matched.wav'
        duration=stretch(source,staged,source_bpm,target_bpm)
        comparison=check_harmony(source,staged) if verify else None
        os.link(staged,output)
    return {'engine':'Rubber Band via FFmpeg','sourceBpm':source_bpm,'targetBpm':target_bpm,
            'duration':duration,'pitchRatio':1,'verification':comparison,'output':str(output)}


def transition(left,right,output,left_bpm,right_bpm,target_bpm,beats):
    # Explicit caller-confirmed compatible boundaries: no automatic reharmonization.
    output=Path(output).resolve()
    if output.exists() or output.suffix.lower()!='.wav': raise ValueError('Use a new WAV output path')
    if type(beats) is not int or not 1<=beats<=8: raise ValueError('Overlap 1–8 beats')
    overlap=beats*60/bpm(target_bpm)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='.rubberband-') as tmp:
        a,b,mix=[Path(tmp)/n for n in ('a.wav','b.wav','mix.wav')]
        da=stretch(left,a,left_bpm,target_bpm); db=stretch(right,b,right_bpm,target_bpm)
        if min(da,db)<overlap+.5 or da+db-overlap>360: raise ValueError('Overlap or total duration out of bounds')
        ca=check_harmony(left,a); cb=check_harmony(right,b)
        run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(a),'-i',str(b),'-filter_complex',
             f'[0:a][1:a]acrossfade=d={overlap:.9f}:c1=qsin:c2=qsin[out]', '-map','[out]',
             '-c:a','pcm_f32le','-n',str(mix)])
        actual=probe(mix,'ffprobe')
        if abs(actual-(da+db-overlap))>.03: raise ValueError('Crossfade duration mismatch')
        # Real shared mastering and peak check, not per-stem normalization.
        from ffmpeg_bridge import master
        staged=Path(tmp)/'master.wav'
        master([mix],staged)
        os.link(staged,output)
    return {'engine':'Rubber Band + FFmpeg + Librosa','targetBpm':target_bpm,'crossfadeSeconds':overlap,
            'leftComparison':ca,'rightComparison':cb,'output':str(output)}


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('stretch'); q.add_argument('source',type=Path);q.add_argument('--out',type=Path,required=True)
    q.add_argument('--source-bpm',type=float,required=True);q.add_argument('--target-bpm',type=float,required=True)
    q=sub.add_parser('transition');q.add_argument('left',type=Path);q.add_argument('right',type=Path);q.add_argument('--out',type=Path,required=True)
    q.add_argument('--left-bpm',type=float,required=True);q.add_argument('--right-bpm',type=float,required=True);q.add_argument('--target-bpm',type=float,required=True)
    q.add_argument('--beats',type=int,default=2);q.add_argument('--compatible-boundaries',action='store_true',required=True,
      help='Confirm compatible harmonies and precisely cut beat-aligned boundaries; no reverb tail before overlap')
    a=p.parse_args()
    result=prepare(a.source,a.out,a.source_bpm,a.target_bpm) if a.cmd=='stretch' else transition(a.left,a.right,a.out,a.left_bpm,a.right_bpm,a.target_bpm,a.beats)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))

if __name__=='__main__': main()
