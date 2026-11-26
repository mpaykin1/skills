"""Measure actual foot drift before/after layered edits; no artistic percentage."""
import argparse,json,math,pathlib

def read(p):
 d=json.loads(p.read_text()); assert d['schema']=='rigify-motion-v1';return d

def drift(c,foot,lo,hi):
 frames={f['frame']:f for f in c['frames']};a=frames[lo];v=c['root_velocity_mps'];assert len(v)==3 and all(math.isfinite(x) for x in v)
 values=[math.dist(a['world'][foot],[frames[i]['world'][foot][j]+v[j]*(frames[i]['time']-a['time']) for j in range(3)]) for i in range(lo,hi+1)]
 assert all(math.isfinite(x) for x in values);return max(values)

def main():
 p=argparse.ArgumentParser();p.add_argument('before',type=pathlib.Path);p.add_argument('after',type=pathlib.Path);p.add_argument('--limit-m',type=float,default=.04);a=p.parse_args();b,c=read(a.before),read(a.after)
 assert b['hero_id']==c['hero_id'] and b['source_sha256']==c['source_sha256'] and set(b['clips'])==set(c['clips'])
 assert isinstance(c.get('layer_recipe_sha256'),str) and len(c['layer_recipe_sha256'])==64
 assert 0<a.limit_m<1;failed=False;count=0
 for name,x in b['clips'].items():
  y=c['clips'][name];assert x['fps']==y['fps'] and x['contacts']==y['contacts'] and x['root_velocity_mps']==y['root_velocity_mps'] and x['events']==y['events'] and [f['frame'] for f in x['frames']]==[f['frame'] for f in y['frames']]
  for foot,intervals in x['contacts'].items():
   for lo,hi in intervals:
    old,new=drift(x,foot,lo,hi),drift(y,foot,lo,hi);count+=1;failed|=new>a.limit_m or new>old+1e-6
    print(f'{name} {foot} {lo}-{hi}: {old:.4f} -> {new:.4f} m')
 assert count,'no measured contacts';print('Visual rear/front/side and attack/air/jump timing review still mandatory.');raise SystemExit(int(failed))
if __name__=='__main__':main()
