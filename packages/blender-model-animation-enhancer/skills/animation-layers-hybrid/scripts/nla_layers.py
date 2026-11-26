"""Blender 4.5 LTS, offline, explicit authored action layers; never changes source file."""
import math, re

TRANSFORM = re.compile(r'^pose\.bones\["([^"\\]+)"\]\.(location|rotation_quaternion|rotation_euler|rotation_axis_angle|scale)$')

def action_slot(action, name):
    slots = [s for s in action.slots if s.identifier == name]
    if len(slots) != 1: raise ValueError(f'{action.name}: explicit action slot required')
    return slots[0]

def channel_paths(action, slot):
    paths = set()
    for layer in action.layers:
        for strip in layer.strips:
            if strip.type != 'KEYFRAME': raise ValueError('unsupported action strip')
            bag = strip.channelbag(slot)
            if bag:
                paths.update(f.data_path for f in bag.fcurves)
    if not paths: raise ValueError(f'{action.name}: no authored channels for slot')
    return paths

def compose(rig, spec):
    import bpy
    ad = rig.animation_data
    if not ad or any(not t.mute for t in ad.nla_tracks): raise ValueError('existing active NLA must be isolated')
    if ad.use_tweak_mode: raise ValueError('exit NLA tweak mode')
    start,end = spec['start'],spec['end']
    if type(start) is not int or type(end) is not int or not 1 <= end-start <= 600: raise ValueError('invalid frame range')
    tracks=[]; old_action=ad.action; old_slot=ad.action_slot if old_action else None; old_use=ad.use_nla
    try:
        ad.action=None; ad.use_nla=True
        layers=[{'action':spec['action'],'slot':spec['slot'],'role':'base','blend':'REPLACE','weight':1.0}]+spec.get('layers',[])
        if len(layers)>8: raise ValueError('too many layers')
        used=set(); names=set()
        for i,layer in enumerate(layers):
            role=layer['role']; weight=float(layer['weight']); blend=layer['blend']
            if role in names or not math.isfinite(weight) or not 0<weight<=1 or blend not in ('REPLACE','COMBINE'): raise ValueError('invalid layer')
            names.add(role)
            if i and role not in ('pelvis','upper_body','weapon','secondary','foot_correction'): raise ValueError('unknown correction role')
            act=bpy.data.actions[layer['action']]; slot=action_slot(act,layer['slot']); paths=channel_paths(act,slot)
            if not act.frame_range[0]<=start<end<=act.frame_range[1]: raise ValueError(f'{role}: action does not cover clip')
            if i:
                mask=set(layer['bones']); protected=set(spec.get('protected_bones',[]));
                if not mask or not mask<=set(rig.pose.bones.keys()): raise ValueError('invalid bone mask')
                if mask&used: raise ValueError('overlapping correction layers')
                if role not in ('pelvis','foot_correction') and mask&protected: raise ValueError('protected lower-body control')
                for path in paths:
                    m=TRANSFORM.fullmatch(path)
                    if not m or m.group(1) not in mask: raise ValueError(f'out-of-mask channel: {path}')
                if blend=='COMBINE' and layer.get('authored_delta') is not True: raise ValueError('COMBINE requires authored delta action')
                used.update(mask)
            track=ad.nla_tracks.new(prev=tracks[-1]) if tracks else ad.nla_tracks.new();tracks.append(track);track.name=f'META_LAYER_{i}_{role}'
            strip=track.strips.new(role,start,act);strip.action_slot=slot
            strip.action_frame_start=start;strip.action_frame_end=end;strip.frame_start=start;strip.frame_end=end
            strip.blend_type=blend;strip.extrapolation='NOTHING';strip.use_auto_blend=False;strip.blend_in=0;strip.blend_out=0
            strip.use_animated_influence=False;strip.influence=weight
        def cleanup():
            for t in reversed(tracks):ad.nla_tracks.remove(t)
            ad.use_nla=old_use;ad.action=old_action
            if old_action and old_slot:ad.action_slot=old_slot
        return cleanup
    except Exception:
        for t in reversed(tracks):ad.nla_tracks.remove(t)
        ad.use_nla=old_use;ad.action=old_action
        if old_action and old_slot:ad.action_slot=old_slot
        raise
