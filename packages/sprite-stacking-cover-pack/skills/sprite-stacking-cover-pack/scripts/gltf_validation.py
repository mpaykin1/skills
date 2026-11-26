"""Fail-closed Khronos glTF Validator gate; source and candidate independently checked."""
import argparse, hashlib, json, shutil, subprocess
from pathlib import Path

SCHEMA='cover-pack-khronos-validation/1'

def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def gate(record,path):
    if record.get('schema')!=SCHEMA or record.get('sha256')!=digest(path) or record.get('bytes')!=Path(path).stat().st_size:
        raise ValueError('Validation result not bound to GLB')
    r=record['report']; issues=r['issues']
    if not isinstance(r.get('validatorVersion'),str) or not r['validatorVersion']:
        raise ValueError('Missing Khronos validator version')
    for k in ('numErrors','numWarnings','numInfos','numHints'):
        if type(issues.get(k)) is not int or issues[k]<0: raise ValueError('Invalid issue counters')
    if issues.get('truncated') is not False or issues['numErrors'] or issues['numWarnings']:
        raise ValueError('Validator errors, warnings or truncated result; retain source')
    messages=issues.get('messages')
    if not isinstance(messages,list) or len(messages)!=sum(issues[k] for k in ('numErrors','numWarnings','numInfos','numHints')):
        raise ValueError('Incomplete validation messages')
    for m in messages:
        code=str(m.get('code','')).upper()
        if not code or m.get('severity') not in (2,3) or any(x in code for x in ('UNSUPPORTED','UNVALIDATED','NOT_VALIDATED','UNKNOWN_EXTENSION','NOT_SUPPORTED')):
            raise ValueError('Incomplete extension coverage; retain source: '+code)
    return record

def validate(path,node='node'):
    exe=shutil.which(node)
    if not exe: raise RuntimeError('Node.js required for official gltf-validator')
    cmd=[exe,str(Path(__file__).with_name('gltf_validate.mjs')),str(Path(path).resolve())]
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
    if p.returncode: raise RuntimeError('Khronos validator unavailable or failed: '+p.stderr[-2000:])
    return gate(json.loads(p.stdout),path)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--out',required=True);p.add_argument('--node',default='node');a=p.parse_args()
    out=Path(a.out)
    if out.exists(): raise FileExistsError(out)
    result=validate(a.source,a.node);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
