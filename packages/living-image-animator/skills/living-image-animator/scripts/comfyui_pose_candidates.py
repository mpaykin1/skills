#!/usr/bin/env python3
"""ComfyUI -> editable full-cel 2D animation candidates.

Calls a real, already-running LOOPBACK ComfyUI server via /prompt,
/history/<id>, /view. Does not render a fake pose, warp a human,
synthesize motion guides or bypass the original Living Image Animator gate.
Outputs source-pixel-identical PNGs for Krita/OpenToonz/Pixelorama.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
import zipfile

from PIL import Image


class ComfyCandidateError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ComfyCandidateError('ComfyUI redirected request; refusing untrusted URL')


def local_server(url: str) -> str:
    v=urlparse(url)
    if v.scheme != 'http' or v.hostname not in ('localhost','127.0.0.1','::1') or v.username or v.password or v.query or v.fragment or v.path not in ('','/'):
        raise ComfyCandidateError('ComfyUI must be an unauthenticated local http://127.0.0.1:PORT server')
    if v.port is None or v.port<1 or v.port>65535:
        raise ComfyCandidateError('ComfyUI port must be explicit')
    return f'http://127.0.0.1:{v.port}'


def safe_filename(s, field='name'):
    if not isinstance(s,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',s):
        raise ComfyCandidateError(f'{field}: use 1..80 ASCII letters, digits, underscore or dash')
    return s


def safe_source(root:Path, rel:str)->Path:
    if not isinstance(rel,str) or not rel or Path(rel).is_absolute() or '\\' in rel or any(p in ('','..','.') for p in rel.split('/')):
        raise ComfyCandidateError('Source path must be safe and relative: '+repr(rel))
    root=root.resolve();p=(root/rel).resolve()
    if root not in p.parents or not p.is_file():
        raise ComfyCandidateError('Required file missing/escaped scene: '+rel)
    return p


def reject_secrets(value):
    if isinstance(value,dict):
        for key,val in value.items():
            if re.search(r'(api[_-]?key|access[_-]?token|password|client[_-]?secret|authorization)',str(key),re.I):
                raise ComfyCandidateError('Workflow contains possible credentials: do not package or submit them')
            reject_secrets(val)
    elif isinstance(value,list):
        for v in value:reject_secrets(v)


def get_scene_jobs(scene:dict, root:Path):
    if not isinstance(scene.get('actors'),list):raise ComfyCandidateError('Scene requires actors list')
    jobs=[];ids=set()
    for actor in scene['actors']:
        aid=safe_filename(actor.get('id'),'actor id')
        if aid in ids:raise ComfyCandidateError('Duplicate actor ID '+aid)
        ids.add(aid)
        box=actor.get('box')
        if not isinstance(box,list) or len(box)!=4 or any(type(v) is not int for v in box) or min(box[2:])<8:
            raise ComfyCandidateError(aid+': box must have original pixel dimensions')
        for i,clip in enumerate(actor.get('clips',[])):
            spec=clip.get('comfyui_candidate')
            if spec is None:continue
            action=safe_filename(clip.get('action'),'action')
            if any(x in clip for x in ('frames','krita_sequence','pixelorama_project','opentoonz_scene')):
                raise ComfyCandidateError(aid+'/'+action+': a clip can have only one primary source')
            if not isinstance(spec,dict):raise ComfyCandidateError('comfyui_candidate must be object')
            count=spec.get('frame_count')
            if type(count) is not int or not 12<=count<=240:raise ComfyCandidateError('Need 12..240 independently generated frame candidates')
            node=str(spec.get('output_node',''))
            if not node or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',node):raise ComfyCandidateError('Output node ID required')
            workflow_path=safe_source(root,spec.get('workflow_api_json'))
            workflow=json.loads(workflow_path.read_text('utf-8'))
            reject_secrets(workflow)
            if 'nodes' in workflow and isinstance(workflow['nodes'],list):
                raise ComfyCandidateError('Export ComfyUI workflow in API format (node ID map), not UI graph format')
            if not isinstance(workflow,dict) or node not in workflow or not all(isinstance(x,dict) and 'class_type' in x and 'inputs' in x for x in workflow.values()):
                raise ComfyCandidateError('ComfyUI API graph must contain selected output node')
            if len(json.dumps(workflow))>1_500_000:raise ComfyCandidateError('ComfyUI graph unusually large')
            jobs.append({'actor':aid,'action':action,'index':i,'spec':spec,'size':tuple(box[2:]),'count':count,
                         'node':node,'workflow':workflow,'workflow_path':workflow_path})
    return jobs


class ComfyServer:
    def __init__(self,url):
        self.base=local_server(url)
        self.opener=build_opener(NoRedirect())
    def request(self,path, data=None, json_response=True, max_bytes=12_000_000):
        req=Request(self.base+path,data=(json.dumps(data).encode('utf-8') if data is not None else None),
                    headers={'Content-Type':'application/json'} if data is not None else {},
                    method='POST' if data is not None else 'GET')
        try:
            with self.opener.open(req,timeout=20) as resp:
                if resp.status!=200:raise ComfyCandidateError('ComfyUI HTTP '+str(resp.status))
                content=resp.read(max_bytes+1)
        except (OSError,ValueError) as e:
            raise ComfyCandidateError('ComfyUI request failed '+path.split('?')[0]+': '+str(e)) from e
        if len(content)>max_bytes:raise ComfyCandidateError('ComfyUI response exceeds size limit')
        if json_response:
            try:return json.loads(content)
            except (UnicodeError,ValueError) as e:raise ComfyCandidateError('Invalid ComfyUI JSON') from e
        return content
    def run(self, graph, output_node, expected_count, timeout=180):
        queued=self.request('/prompt',{'prompt':graph})
        prompt_id=queued.get('prompt_id')
        if not isinstance(prompt_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',prompt_id):
            raise ComfyCandidateError('ComfyUI did not accept workflow: '+str(queued.get('error') or queued.get('node_errors'))[:300])
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            hist=self.request('/history/'+prompt_id)
            record=hist.get(prompt_id)
            if isinstance(record,dict):
                status=record.get('status',{})
                if status.get('status_str')=='error' or status.get('completed') is False and status.get('status_str') in ('error','failed'):
                    raise ComfyCandidateError('ComfyUI graph execution failed')
                if record.get('outputs'):
                    output=record['outputs'].get(output_node, {})
                    images=output.get('images',[])
                    if len(images)!=expected_count:
                        raise ComfyCandidateError(f'{output_node}: {len(images)} output images, expected {expected_count}; never duplicate frames')
                    return prompt_id,images
            time.sleep(.7)
        raise ComfyCandidateError('ComfyUI execution timed out; never substitute synthetic cels')
    def image(self, metadata):
        name=metadata.get('filename'); sub=metadata.get('subfolder',''); kind=metadata.get('type','output')
        if not isinstance(name,str) or not name.lower().endswith('.png') or '/' in name or '\\' in name or name in ('.','..'):
            raise ComfyCandidateError('ComfyUI returned unsafe PNG filename')
        if not isinstance(sub,str) or sub.startswith('/') or '\\' in sub or any(q in ('..','.') for q in sub.split('/')):
            raise ComfyCandidateError('ComfyUI returned unsafe subfolder')
        if kind!='output':raise ComfyCandidateError('Only permanent output images accepted; use SaveImage, not PreviewImage')
        return self.request('/view?'+urlencode({'filename':name,'subfolder':sub,'type':kind}),json_response=False)


def verify_png(raw:bytes,size, label):
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.format!='PNG' or im.mode!='RGBA' or im.size!=size:
                raise ComfyCandidateError(f'{label}: full-cel source-size RGBA PNG {size} required')
            a=im.getchannel('A')
            if a.getextrema() == (255,255) or a.getbbox() is None:
                raise ComfyCandidateError(f'{label}: transparent background and visible figure mandatory')
            digest=hashlib.sha256(im.tobytes()).hexdigest()
            return im.copy(),digest
    except (OSError,ValueError) as e:
        if isinstance(e,ComfyCandidateError):raise
        raise ComfyCandidateError(label+': invalid PNG') from e


def render_candidates(scene_path:Path,out_dir:Path,url:str):
    scene_path=scene_path.resolve(); root=scene_path.parent; scene=json.loads(scene_path.read_text('utf-8'))
    jobs=get_scene_jobs(scene,root)
    if not jobs:raise ComfyCandidateError('No actor clips with comfyui_candidate in source scene')
    client=ComfyServer(url);out=out_dir.resolve(); base=out/'comfyui_candidates'
    base.mkdir(parents=True,exist_ok=True)
    result=[]; paths=[]
    from PIL import Image
    for job in jobs:
        prompt_id,images=client.run(job['workflow'],job['node'],job['count'])
        area=base/'poses'/job['actor']/f'{job["index"]:02d}_{job["action"]}'
        levels=base/'opentoonz_levels'/job['actor']/f'{job["index"]:02d}_{job["action"]}'
        for path in (area,levels):path.mkdir(parents=True,exist_ok=True)
        frame_files=[]; hashes=[]
        for i,info in enumerate(images):
            contents=client.image(info)
            img,pixel_hash=verify_png(contents,job['size'],job['actor']+'/'+job['action']+f'/{i:04d}')
            path=area/f'frame_{i:04d}.png';path.write_bytes(contents)
            exact=levels/f'{job["actor"]}.{i+1:04d}.png';exact.write_bytes(contents)
            frame_files.append(path);paths.extend([path,exact]);hashes.append(pixel_hash)
        if len(set(hashes))<8 or any(hashes[i]==hashes[i-1]==hashes[i-2] for i in range(2,len(hashes))):
            raise ComfyCandidateError(job['actor']+'/'+job['action']+': frozen/repeated characters; re-author action')
        w,h=job['size']; cols=min(8,job['count']); rows=math.ceil(job['count']/cols)
        if cols*w*rows*h>80_000_000:raise ComfyCandidateError('Oversize spritesheet')
        sheet=Image.new('RGBA',(cols*w,rows*h),(0,0,0,0))
        for i,p in enumerate(frame_files):
            with Image.open(p) as pose:sheet.alpha_composite(pose,((i%cols)*w,(i//cols)*h))
        px=base/'pixelorama_import'/job['actor']/f'{job["index"]:02d}_{job["action"]}.png'
        px.parent.mkdir(parents=True,exist_ok=True);sheet.save(px);paths.append(px)
        workflow_dst=base/'workflows'/job['actor']/f'{job["index"]:02d}_{job["action"]}.json'
        workflow_dst.parent.mkdir(parents=True,exist_ok=True)
        workflow_dst.write_text(json.dumps(job['workflow'],ensure_ascii=False,indent=2),'utf-8');paths.append(workflow_dst)
        result.append({'actor_id':job['actor'],'action':job['action'],'output_node':job['node'],
                       'prompt_id':prompt_id,'frames':job['count'],'cell_size':list(job['size']),
                       'grid':[cols,rows],'pixel_sha256':hashes,
                       'poses':str(area.relative_to(base).as_posix()),
                       'opentoonz_levels':str(levels.relative_to(base).as_posix()),
                       'pixelorama_sheet':str(px.relative_to(base).as_posix()),
                       'status':'CANDIDATE_ONLY_NOT_IDENTITY_APPROVED_NOT_ANIMATED'} )
    manifest=base/'manifest.json'
    manifest.write_text(json.dumps({'schema':1,'engine':'ComfyUI local API','stage':'candidate-only',
       'full_pose_validation':'NOT RUN; after approval use Krita/OpenToonz/Pixelorama + original animator',
       'source':'actual downloaded ComfyUI SaveImage output; no generated pose claims without PNGs',
       'clips':result},ensure_ascii=False,indent=2),'utf-8')
    paths.append(manifest)
    zip_path=out/'comfyui_pose_candidates.zip'
    with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for file in paths:z.write(file,file.relative_to(base).as_posix())
    with zipfile.ZipFile(zip_path) as z:
        if z.testzip() is not None:raise ComfyCandidateError('Candidate ZIP corrupted')
    return {'zip':str(zip_path),'clips':len(result),'total_frames':sum(v['frames'] for v in result),'status':'candidates require review and full-pose validation'}


def main():
    p=argparse.ArgumentParser(description='Run actual ComfyUI API workflow and export true RGBA cel CANDIDATES for 2D editor refinement')
    p.add_argument('--scene',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--comfyui-url',default=os.environ.get('COMFYUI_URL','http://127.0.0.1:8188'))
    p.add_argument('--preflight-only',action='store_true')
    a=p.parse_args()
    scene=json.loads(a.scene.read_text('utf-8')); jobs=get_scene_jobs(scene,a.scene.resolve().parent)
    if a.preflight_only:
        local_server(a.comfyui_url)
        print(json.dumps({'candidate_clips':len(jobs),'requires_running_comfyui':True,'final_pose_validation':'not run'},ensure_ascii=False))
    else:
        print(json.dumps(render_candidates(a.scene,a.out,a.comfyui_url),ensure_ascii=False))

if __name__=='__main__':main()
