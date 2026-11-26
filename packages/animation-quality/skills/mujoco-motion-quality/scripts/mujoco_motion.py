"""Native CPU inverse-dynamics gate for approved, calibrated MJCF and sampled qpos.
No simulated fallback. Force demand is not measured muscle force or proof of balance.
"""
import argparse, hashlib, importlib.metadata, json, pathlib, sys, xml.etree.ElementTree as ET
import numpy as np
P=pathlib.Path

def require(ok,msg):
    if not ok: raise ValueError(msg)
def sha(p): return hashlib.sha256(P(p).read_bytes()).hexdigest()
def read_clip(p):
    require(P(p).stat().st_size<=32*1024**2,'clip too large')
    with np.load(p,allow_pickle=False) as z:
        t=np.asarray(z['time'],float); q=np.asarray(z['qpos'],float)
    require(t.ndim==1 and 8<=len(t)<=1800 and q.ndim==2 and q.shape[0]==len(t) and 1<=q.shape[1]<=256,'bad clip shape')
    require(np.isfinite(t).all() and np.isfinite(q).all(),'nonfinite clip')
    dt=np.diff(t); require(1/120-1e-9<=dt[0]<=.1+1e-9 and np.allclose(dt,dt[0],rtol=1e-6,atol=1e-9),'CFR 10–120 fps required')
    return t,q,float(dt[0])
def contact_metrics(pos,active,dist):
    return {'missing_frames':int(np.count_nonzero(~active)), 'slip_m':float(np.max(np.linalg.norm(pos-pos[0],axis=1))), 'penetration_m':float(np.max(np.maximum(-dist,0)))}
def nonregress(a,b):
    require(a['contacts'].keys()==b['contacts'].keys(),'contact mapping changed')
    for k in a['contacts']:
        for m,v in a['contacts'][k].items(): require(b['contacts'][k][m]<=v+(0 if m=='missing_frames' else 1e-6),'contact worsened: '+k+'/'+m)
    for k in ('inverse_rms_per_dof','inverse_peak_per_dof'):
        x=np.asarray(a[k]); y=np.asarray(b[k]); require(x.shape==y.shape and np.isfinite(y).all() and np.all(y<=x+np.maximum(1e-6,0.01*x)), 'inverse demand worsened: '+k)
    require(b['penetration_m']<=a['penetration_m']+1e-6,'global penetration worsened')

def load_model(p,cfg):
    require(cfg['rights_confirmed'] is True and cfg['model_sha256']==sha(p),'model approval/hash required')
    require(P(p).stat().st_size<=2*1024**2,'MJCF too large')
    xml=P(p).read_text(); require('<!DOCTYPE' not in xml.upper() and '<!ENTITY' not in xml.upper(),'unsafe XML')
    root=ET.fromstring(xml)
    require(root.tag=='mujoco' and not any(e.tag in ('include','extension','plugin') or 'file' in e.attrib for e in root.iter()),'only self-contained trusted MJCF, no external assets/plugins')
    require(importlib.metadata.version('mujoco')=='3.3.7','isolated mujoco==3.3.7 required')
    import mujoco as mj
    m=mj.MjModel.from_xml_string(xml)
    require(0<m.nq<=256 and m.nv<=256 and m.na==0 and m.nmocap==0 and m.neq==0,'unsupported model: activation/mocap/equality or size')
    require(np.allclose(m.opt.gravity,[0,0,-9.81],atol=1e-5),'calibrated Z-up gravity required')
    return mj,m

def evaluate(mj,m,t,q,dt,cfg):
    require(q.shape==(len(t),m.nq),'qpos does not match native model order')
    hinge=int(mj.mjtJoint.mjJNT_HINGE); slide=int(mj.mjtJoint.mjJNT_SLIDE); free=int(mj.mjtJoint.mjJNT_FREE); ball=int(mj.mjtJoint.mjJNT_BALL)
    for j in range(m.njnt):
        typ=int(m.jnt_type[j]); a=int(m.jnt_qposadr[j]);
        if typ in (free,ball):
            off=a+(3 if typ==free else 0); require(np.allclose(np.linalg.norm(q[:,off:off+4],axis=1),1,atol=1e-6,rtol=0),'nonunit quaternion')
            require(np.all(np.sum(q[1:,off:off+4]*q[:-1,off:off+4],axis=1)>=0),'quaternion sign discontinuity')
            require(not m.jnt_limited[j],'limited ball joint needs native review')
        elif typ in (hinge,slide) and m.jnt_limited[j]:
            lo,hi=m.jnt_range[j]; require(np.all((q[:,a]>=lo-1e-8)&(q[:,a]<=hi+1e-8)),'joint limit violated')
    v=np.empty((len(t)-1,m.nv))
    for i in range(len(v)): mj.mj_differentiatePos(m,v[i],dt,q[i],q[i+1])
    vel=np.vstack([v[0],(v[:-1]+v[1:])/2,v[-1]]); acc=np.gradient(vel,dt,axis=0,edge_order=2)
    require(np.isfinite(vel).all() and np.isfinite(acc).all(),'nonfinite derivatives')
    def ident(kind,name):
        i=mj.mj_name2id(m,kind,name); require(i>=0,'unknown native name: '+name); return i
    contacts=cfg['contacts']; require(isinstance(contacts,list) and len(contacts)<=64,'explicit contacts list required')
    require(bool(contacts) or cfg.get('no_ground_contact_confirmed') is True,'ground contacts must be authored')
    tracks=[]
    for c in contacts:
        a,b=c['start'],c['end'];require(type(a)==type(b)==int and 0<=a<b<len(t),'bad support window')
        foot=ident(mj.mjtObj.mjOBJ_GEOM,c['foot_geom']); floor=ident(mj.mjtObj.mjOBJ_GEOM,c['floor_geom']); site=ident(mj.mjtObj.mjOBJ_SITE,c['site']);
        require(foot!=floor and m.geom_bodyid[floor]==0 and m.site_bodyid[site]==m.geom_bodyid[foot],'support site/geom and static floor required')
        tracks.append((a,b,foot,floor,site,[],[],[]))
    d=mj.MjData(m); forces=[]; penetration=0.; com=[]
    for i in range(len(t)):
        mj.mj_resetData(m,d); d.time=t[i]; d.qpos[:]=q[i];d.qvel[:]=vel[i];mj.mj_forward(m,d)
        require(np.isfinite(d.site_xpos).all() and np.isfinite(d.subtree_com).all(),'nonfinite pose')
        pairs={}
        for k in range(d.ncon):
            c=d.contact[k]; pair=tuple(sorted((int(c.geom1),int(c.geom2))));dist=float(c.dist); require(np.isfinite(dist),'nonfinite contact');pairs[pair]=min(pairs.get(pair,np.inf),dist);penetration=max(penetration,-dist)
        for a,b,foot,floor,site,ps,active,dist in tracks:
            if a<=i<=b:
                dd=pairs.get(tuple(sorted((foot,floor))),None); ps.append(d.site_xpos[site].copy());active.append(dd is not None and dd<=1e-4);dist.append(dd if dd is not None else 0.)
        com.append(d.subtree_com[0].copy()); d.qacc[:]=acc[i]; mj.mj_inverse(m,d); forces.append(d.qfrc_inverse.copy())
    f=np.asarray(forces);require(np.isfinite(f).all(),'nonfinite inverse dynamics')
    return {'contacts':{str(k):contact_metrics(np.asarray(x[5]),np.asarray(x[6]),np.asarray(x[7])) for k,x in enumerate(tracks)}, 'penetration_m':float(penetration),'inverse_rms_per_dof':np.sqrt(np.mean(f*f,axis=0)).tolist(),'inverse_peak_per_dof':np.max(np.abs(f),axis=0).tolist(),'com_xyz_m':np.asarray(com).tolist()}

def main():
    p=argparse.ArgumentParser();p.add_argument('model',type=P);p.add_argument('baseline',type=P);p.add_argument('config',type=P);p.add_argument('--candidate',type=P); a=p.parse_args()
    cfg=json.loads(a.config.read_text()); require(cfg['baseline_sha256']==sha(a.baseline),'baseline hash mismatch'); t,q,dt=read_clip(a.baseline);mj,m=load_model(a.model,cfg); b=evaluate(mj,m,t,q,dt,cfg)
    if a.candidate:
        require(cfg['candidate_sha256']==sha(a.candidate),'candidate hash mismatch');tc,qc,dtc=read_clip(a.candidate);require(np.array_equal(t,tc),'timeline changed');
        j=mj.mj_name2id(m,mj.mjtObj.mjOBJ_JOINT,cfg['edited_joint']);require(j>=0 and int(m.jnt_type[j]) in (int(mj.mjtJoint.mjJNT_HINGE),int(mj.mjtJoint.mjJNT_SLIDE)),'single scalar joint correction only'); col=int(m.jnt_qposadr[j]); radius=float(cfg['max_delta_native']);require(0<radius<=.05 and qc.shape==q.shape,'bad radius/shape');require(np.array_equal(np.delete(q,col,1),np.delete(qc,col,1)) and np.max(np.abs(q[:,col]-qc[:,col]))<=radius+1e-10,'unapproved motion modification');
        locked={0,1,len(t)-2,len(t)-1};
        for c in cfg['contacts']: locked.update(range(c['start'],c['end']+1))
        for k in cfg['anchors']:require(type(k)==int and 0<=k<len(t),'bad anchor');locked.add(k)
        ii=sorted(locked);require(np.array_equal(q[ii],qc[ii]),'anchor changed')
        z=evaluate(mj,m,t,qc,dtc,cfg);nonregress(b,z);print(json.dumps({'status':'native_nonregression_only','before':b,'after':z},allow_nan=False))
    else: print(json.dumps({'status':'native_audit_only','metrics':b},allow_nan=False))
if __name__=='__main__':
    try: main()
    except Exception as e: sys.exit('BLOCKED: '+str(e))
