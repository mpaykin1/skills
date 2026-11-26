"""Original, dependency-free validation of reviewed humanoid retarget mapping."""
import argparse, hashlib, json, math, re
from pathlib import Path
REQUIRED={'hips','spine','chest','neck','head'}|{f'{p}_{s}' for s in ('l','r') for p in ('upper_arm','forearm','hand','thigh','shin','foot')}
def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def validate(c,source_bones=None,target_bones=None):
    if not isinstance(c,dict):raise ValueError('configuration object required')
    for k in ('rights_confirmed','mapping_reviewed','rest_pose_reviewed','fk_target_reviewed'):
        if c.get(k) is not True:raise ValueError('missing approval: '+k)
    for k in ('source_sha256','motion_sha256'):
        if not re.fullmatch('[a-f0-9]{64}',str(c.get(k,''))):raise ValueError('invalid '+k)
    for k in ('hero_id','source_rig','target_rig','source_action','new_action','clip'):
        if not isinstance(c.get(k),str) or not c[k].strip():raise ValueError('missing '+k)
    if c['source_rig']==c['target_rig']:raise ValueError('same rig')
    if c.get('pose') not in ('REST','CURRENT'):raise ValueError('explicit pose required')
    if c.get('root_mode') not in ('in_place','world'):raise ValueError('explicit root mode required')
    if type(c.get('auto_scale')) is not bool:raise ValueError('explicit scale policy required')
    fps=c.get('fps'); start=c.get('start');end=c.get('end')
    if type(fps) not in (int,float) or not math.isfinite(fps) or not 1<=fps<=120 or type(start) is not int or type(end) is not int or not 1<=end-start<=3600:raise ValueError('invalid timing')
    rows=c.get('mapping');
    if not isinstance(rows,list) or not 17<=len(rows)<=150:raise ValueError('invalid mapping length')
    seen=[set(),set(),set()]
    for r in rows:
        if not isinstance(r,dict):raise ValueError('invalid mapping row')
        for i,k in enumerate(('role','source','target')):
            v=r.get(k)
            if not isinstance(v,str) or not v.strip() or v in seen[i]:raise ValueError('missing or duplicate '+k)
            seen[i].add(v)
        if source_bones is not None and r['source'] not in source_bones:raise ValueError('unknown source bone '+r['source'])
        if target_bones is not None and r['target'] not in target_bones:raise ValueError('unknown target bone '+r['target'])
    if REQUIRED-seen[0]:raise ValueError('missing roles '+','.join(sorted(REQUIRED-seen[0])))
    return rows
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('config',type=Path);a=p.parse_args();validate(json.loads(a.config.read_text()));print('Mapping structure valid; evaluated motion and licensing are not verified')
