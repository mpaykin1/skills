"""Reject mismatched source, budget and approval metadata before consuming refined poses."""
import argparse,json,math,re
from pathlib import Path

def verify(m,pack):
    if m.get('schema')!='meta-opensubdiv-v1': raise ValueError('schema')
    for k in ('parent_sha256','derived_sha256','recipe_sha256'):
        if not re.fullmatch('[0-9a-f]{64}',m.get(k,'')): raise ValueError(k)
    if not m.get('hero_id') or m.get('visual_approved') is not True: raise ValueError('visual approval absent')
    if pack.get('hero_id')!=m['hero_id'] or pack.get('source_sha256')!=m['derived_sha256'] or pack.get('subdiv_recipe_sha256')!=m['recipe_sha256']: raise ValueError('pose source mismatch')
    limit=m['max_total_triangles'];tol=m['max_bounds_shift_m'];frames=m['frames']
    if not frames or not isinstance(limit,int) or not 0<limit<=2000000 or not math.isfinite(tol) or not 0<tol<=.05: raise ValueError('invalid metadata')
    names={e['object'] for e in m['meshes']}
    for r in frames:
        if set(r['before'])!=names or set(r['after'])!=names: raise ValueError('missing mesh')
        if sum(v['triangles'] for v in r['after'].values())>limit: raise ValueError('triangle budget')
        for n,b in r['before'].items():
            a=r['after'][n]
            for k in ('min','max'):
                if len(a[k])!=3 or len(b[k])!=3 or not all(math.isfinite(x) for x in a[k]+b[k]) or max(abs(x-y) for x,y in zip(a[k],b[k]))>tol: raise ValueError('extent drift')
    return True
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('subdiv',type=Path);p.add_argument('pack',type=Path);a=p.parse_args();verify(json.loads(a.subdiv.read_text()),json.loads(a.pack.read_text()));print('metadata compatible; real visual review is separate')
