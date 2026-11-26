"""Render MUSIC JSON or Standard MIDI with the real native FluidSynth 2.x library.
Offline stereo WAV, no API, no external player, no bundled SoundFont.
"""
from __future__ import annotations
import argparse
import ctypes as C
import ctypes.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import wave

MAX_SECONDS = 360
# General MIDI program numbers (zero-based); only one owner per role.
ROLES = {'piano': (0, 0), 'pad': (1, 89), 'bass': (2, 33), 'melody': (3, 46), 'alt': (4, 73)}
DEFAULT_FONTS = ('/usr/share/sounds/sf2/default-GM.sf2', '/usr/share/sounds/sf3/default-GM.sf3', '/usr/share/sounds/sf2/TimGM6mb.sf2')


def valid_time(t):
    return type(t) in (int, float) and math.isfinite(t) and 0 <= t <= MAX_SECONDS + 2


def json_events(source):
    p = source.get('performance', source)
    notes = p['notes']; duration = p['totalSeconds']; backing = source.get('backing', {}).get('notes', [])
    if not valid_time(duration) or not 0 < duration <= MAX_SECONDS or not isinstance(notes, list) or not isinstance(backing, list) or not 0 < len(notes) + len(backing) <= 60000:
        raise ValueError('Invalid performance size or duration')
    if any(n.get('part') == 'bass' for n in notes) and any(n.get('kind') == 'bass' for n in backing):
        raise ValueError('MMA and Modular Riffs cannot both own the bass')
    events = [(0., 0, 'program_change', (ch, prog)) for ch, prog in ROLES.values()]
    # Lower backing velocity to preserve the lead; no rewriting pitches or times.
    def add(n, ch, gain=1.):
        pitch, a, b, v = n['pitch'], n['start'], n['end'], n['velocity']
        if type(pitch) is not int or not 0 <= pitch <= 127 or not valid_time(a) or not valid_time(b) or not a < b <= duration + 2 or type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1:
            raise ValueError('Invalid note event')
        if v == 0: return
        events.extend([(a, 2, 'noteon', (ch, pitch, max(1, round(v * gain * 127)))), (b, 1, 'noteoff', (ch, pitch))])
    for n in notes:
        role = n.get('part', 'piano')
        if role not in ROLES: raise ValueError('Unknown musical part')
        add(n, ROLES[role][0])
    for n in backing:
        kind = n.get('kind')
        if kind not in ('bass','drum'): raise ValueError('Unknown backing part')
        add(n, 2 if kind == 'bass' else 9, .65)
    # Preserve overlapping repeats: retrigger each onset but release only after
    # the last overlapping instance ends (MIDI cannot address duplicate voices).
    active = {}; result = []
    for t, priority, fn, args in sorted(events, key=lambda e: (e[0],e[1])):
        key = args[:2]
        if fn == 'noteon': active[key] = active.get(key, 0) + 1
        if fn == 'noteoff':
            active[key] -= 1
            if active[key]: continue
        result.append((t, fn, args))
    return result, max(duration, max((e[0] for e in result), default=0))


def midi_events(path):
    import mido
    mf = mido.MidiFile(path)
    if mf.type not in (0, 1) or mf.ticks_per_beat <= 0: raise ValueError('Only synchronous PPQN MIDI supported')
    tempo, t, events = 500000, 0., []
    for msg in mido.merge_tracks(mf.tracks):
        t += mido.tick2second(msg.time, mf.ticks_per_beat, tempo)
        if not valid_time(t) or t > MAX_SECONDS: raise ValueError('MIDI exceeds duration limit')
        if msg.type == 'set_tempo': tempo = msg.tempo
        elif msg.type == 'note_on' and msg.velocity: events.append((t,'noteon',(msg.channel,msg.note,msg.velocity)))
        elif msg.type in ('note_off','note_on'): events.append((t,'noteoff',(msg.channel,msg.note)))
        elif msg.type == 'control_change': events.append((t,'cc',(msg.channel,msg.control,msg.value)))
        elif msg.type == 'program_change': events.append((t,'program_change',(msg.channel,msg.program)))
        elif msg.type == 'pitchwheel': events.append((t,'pitch_bend',(msg.channel,msg.pitch+8192)))
        elif msg.type == 'aftertouch': events.append((t,'channel_pressure',(msg.channel,msg.value)))
        elif msg.type == 'polytouch': events.append((t,'key_pressure',(msg.channel,msg.note,msg.value)))
        elif msg.type == 'sysex': raise ValueError('SysEx is not supported by this GM renderer; export ordinary GM MIDI')
        if len(events)>200000: raise ValueError('Too many MIDI events')
    if not any(e[1]=='noteon' for e in events): raise ValueError('No notes in MIDI')
    return events,t


class Fluid:
    def __init__(self,font,rate,library=None):
        name = library or ctypes.util.find_library('fluidsynth')
        if not name: raise RuntimeError('Install native FluidSynth 2.x (libfluidsynth), then retry')
        self.lib=C.CDLL(name); self.settings=None; self.synth=None
        ptr=C.c_void_p; integer=C.c_int; string=C.c_char_p; double=C.c_double
        def bind(n, ret, *args):
            f=getattr(self.lib,n); f.restype=ret; f.argtypes=list(args); return f
        self.newsettings=bind('new_fluid_settings',ptr)
        self.delsettings=bind('delete_fluid_settings',None,ptr)
        self.newsynth=bind('new_fluid_synth',ptr,ptr)
        self.delsynth=bind('delete_fluid_synth',None,ptr)
        self.setnum=bind('fluid_settings_setnum',integer,ptr,string,double)
        self.setint=bind('fluid_settings_setint',integer,ptr,string,integer)
        self.load=bind('fluid_synth_sfload',integer,ptr,string,integer)
        self.write=bind('fluid_synth_write_s16',integer,ptr,integer,ptr,integer,integer,ptr,integer,integer)
        self.calls={n:bind('fluid_synth_'+n,integer,ptr,*([integer]*count)) for n,count in [('noteon',3),('noteoff',2),('cc',3),('program_change',2),('pitch_bend',2),('channel_pressure',2),('key_pressure',3)]}
        try:
            self.settings=self.newsettings()
            if not self.settings: raise RuntimeError('Cannot create FluidSynth settings')
            self.setnum(self.settings,b'synth.sample-rate',rate)
            self.setnum(self.settings,b'synth.gain',.25)
            self.setint(self.settings,b'synth.polyphony',128)
            self.synth=self.newsynth(self.settings)
            if not self.synth: raise RuntimeError('Cannot create FluidSynth')
            if self.load(self.synth,os.fsencode(font),1)<0: raise RuntimeError('Cannot load SoundFont')
        except BaseException:
            self.close(); raise
    def event(self,fn,args):
        rc=self.calls[fn](self.synth,*args)
        # Note-off for an already stolen/ended voice is harmless; other errors fail.
        if rc<0 and fn!='noteoff': raise RuntimeError(f'FluidSynth rejected {fn}: {args}')
    def audio(self,n):
        buf=(C.c_int16*(2*n))()
        if self.write(self.synth,n,buf,0,2,buf,1,2)!=0: raise RuntimeError('FluidSynth rendering failed')
        if sys.byteorder=='big':
            import array
            a=array.array('h',buf); a.byteswap(); return a.tobytes()
        return bytes(buf)
    def close(self):
        if self.synth: self.delsynth(self.synth); self.synth=None
        if self.settings: self.delsettings(self.settings); self.settings=None


def render(events,duration,output,font,rate=44100,tail=1.5,library=None):
    if rate not in (22050,32000,44100,48000) or not 0<=tail<=5: raise ValueError('Invalid sample rate or tail')
    output=Path(output); font=Path(font)
    if output.suffix.lower()!='.wav' or output.exists(): raise ValueError('Choose a new WAV output')
    if not font.is_file() or font.suffix.lower() not in ('.sf2','.sf3'): raise ValueError('Provide a licensed SF2/SF3 SoundFont')
    output.parent.mkdir(parents=True,exist_ok=True)
    s=Fluid(font,rate,library); tmp=None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent,suffix='.wav',delete=False) as f: tmp=Path(f.name)
        with wave.open(str(tmp),'wb') as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate); frame=0
            def advance(t):
                nonlocal frame
                target=round(t*rate)
                while frame<target:
                    n=min(4096,target-frame); w.writeframesraw(s.audio(n)); frame+=n
            for t,fn,args in events:
                advance(t); s.event(fn,args)
            advance(duration)
            for ch in range(16):
                s.event('cc',(ch,64,0)); s.event('cc',(ch,123,0))
            advance(duration+tail)
        if output.exists(): raise FileExistsError(output)
        tmp.rename(output); tmp=None
    finally:
        s.close()
        if tmp: tmp.unlink(missing_ok=True)
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('input',type=Path); p.add_argument('output',type=Path)
    p.add_argument('--soundfont',type=Path); p.add_argument('--rate',type=int,default=44100); p.add_argument('--tail',type=float,default=1.5); p.add_argument('--library')
    a=p.parse_args(); font=a.soundfont or next((Path(f) for f in DEFAULT_FONTS if Path(f).is_file()),None)
    if font is None: raise RuntimeError('No installed SoundFont; use --soundfont with a licensed GM bank')
    if a.input.stat().st_size>50_000_000: raise ValueError('Input too large')
    suffix=a.input.suffix.lower()
    if suffix=='.json': events,duration=json_events(json.loads(a.input.read_text()))
    elif suffix in ('.mid','.midi'): events,duration=midi_events(a.input)
    else: raise ValueError('Expected MUSIC JSON or MIDI')
    render(events,duration,a.output,font,a.rate,a.tail,a.library)
    print(f'{a.output} | SoundFont: {font}')

if __name__=='__main__': main()
