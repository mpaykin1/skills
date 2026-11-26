"""Canonical MUSIC performance JSON -> General MIDI (Mido 1.3.3).
Use a source MIDI conductor to retain rubato, or a constant tempo grid.
No resynthesis, no changes to the input score, no network.
"""
from __future__ import annotations
import argparse
from bisect import bisect_right
from collections import defaultdict
import json
import math
from pathlib import Path
import tempfile
import mido
from fluidsynth_bridge import json_events


def conductor(source, reference=None):
    """Return PPQN, tempo segments and conductor events in absolute ticks."""
    if reference is not None:
        if reference.type not in (0, 1) or not 0 < reference.ticks_per_beat <= 32767:
            raise ValueError('Reference must be synchronous PPQN MIDI')
        ppqn = reference.ticks_per_beat
        tick = 0
        meta = {}
        for msg in mido.merge_tracks(reference.tracks):
            tick += msg.time
            if msg.type in ('set_tempo', 'time_signature', 'key_signature'):
                # Upstream may set tempo twice at tick 0. Last event wins.
                meta[(tick, msg.type)] = msg.copy(time=0)
        meta.setdefault((0, 'set_tempo'), mido.MetaMessage('set_tempo', tempo=500000))
    else:
        ppqn = 960
        piece = source.get('piece', {})
        bpm = piece.get('tempo', 120) * piece.get('beatUnit', 1)
        if not math.isfinite(bpm) or not 20 <= bpm <= 350:
            raise ValueError('Invalid quarter-note tempo')
        meta = {(0, 'set_tempo'): mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm))}
        beats, unit = piece.get('beats', 4), piece.get('beatUnit', 1)
        if (beats, unit) == (2, 1.5): meter = (6, 8)
        elif type(beats) is int and 1 <= beats <= 12 and unit == 1: meter = (beats, 4)
        else: raise ValueError('Supply a reference MIDI for this meter')
        meta[(0, 'time_signature')] = mido.MetaMessage('time_signature', numerator=meter[0], denominator=meter[1])
    changes = sorted((t, m.tempo) for (t,k),m in meta.items() if k == 'set_tempo')
    elapsed = 0.; segments = []
    previous_tick = 0; previous_tempo = 500000
    for tick, tempo in changes:
        if tempo <= 0: raise ValueError('Invalid conductor tempo')
        elapsed += mido.tick2second(tick-previous_tick, ppqn, previous_tempo)
        segments.append((elapsed, tick, tempo))
        previous_tick, previous_tempo = tick, tempo
    starts = [s[0] for s in segments]
    def to_tick(seconds):
        origin, tick, tempo = segments[max(0, bisect_right(starts, seconds)-1)]
        return tick + round(mido.second2tick(seconds-origin, ppqn, tempo))
    return ppqn, to_tick, sorted((t,k,m) for (t,k),m in meta.items())


def build(source, reference=None):
    events, duration = json_events(source)  # identical validation and GM role map as native renderer
    ppqn, to_tick, meta = conductor(source, reference)
    end_tick = to_tick(duration)
    out = mido.MidiFile(type=1, ticks_per_beat=ppqn)
    def track(name, items):
        tr = mido.MidiTrack(); tr.append(mido.MetaMessage('track_name', name=name)); prev=0
        for tick, msg in items:
            tr.append(msg.copy(time=tick-prev)); prev=tick
        tr.append(mido.MetaMessage('end_of_track',time=max(0,end_tick-prev)))
        out.tracks.append(tr)
    by = defaultdict(list); active={}
    for sec, fn, args in events:
        ch = args[0]; t = to_tick(sec); key = args[:2]
        if fn == 'program_change':
            by[ch].append((t,mido.Message('program_change',channel=ch,program=args[1])))
        elif fn == 'noteon':
            # Standard MIDI cannot independently release overlapping identical pitches
            # on the same channel. Retrigger with an explicit off; preserve union end.
            if key in active:
                t=max(t,active[key]+1)
                by[ch].append((t,mido.Message('note_off',channel=ch,note=args[1],velocity=0)))
            active[key]=t
            by[ch].append((t,mido.Message('note_on',channel=ch,note=args[1],velocity=args[2])))
        elif fn == 'noteoff':
            if key not in active: raise ValueError('Unexpected note-off')
            t=max(t,active.pop(key)+1)
            by[ch].append((t,mido.Message('note_off',channel=ch,note=args[1],velocity=0)))
        else: raise ValueError('Unexpected performance event')
        end_tick=max(end_tick,t)
    if active: raise ValueError('Unterminated notes')
    if not any(m.type=='note_on' for items in by.values() for _,m in items): raise ValueError('No audible notes')
    # All tracks end at the same tick (including conductor after rounding).
    track('MUSIC conductor',[(t,m) for t,_,m in meta if t <= end_tick])
    for ch, items in sorted(by.items()):
        track(f'MUSIC channel {ch+1}', sorted(items,key=lambda x:x[0]))
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('input',type=Path); p.add_argument('output',type=Path)
    p.add_argument('--conductor',type=Path,help='Source MIDI tempo/meter/key map only; no source notes copied')
    a=p.parse_args()
    if a.input.stat().st_size>50_000_000 or (a.conductor and a.conductor.stat().st_size>50_000_000): raise ValueError('Input too large')
    if a.output.suffix.lower() not in ('.mid','.midi') or a.output.exists(): raise ValueError('Choose a new MIDI path')
    mf=build(json.loads(a.input.read_text()), mido.MidiFile(a.conductor) if a.conductor else None)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=a.output.parent,suffix='.mid',delete=False) as f: tmp=Path(f.name)
    try:
        mf.save(tmp)
        # Exclusive publication avoids replacing any existing file.
        with a.output.open('xb') as dest: dest.write(tmp.read_bytes())
    finally: tmp.unlink(missing_ok=True)

if __name__=='__main__': main()
