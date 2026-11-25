#!/usr/bin/env python3
"""Isolated, opt-in, hash-locked Python OSS installation for Skill Nexus.
This intentionally does not install into the host / global Python.
"""
import argparse
import re
import subprocess
import sys
import venv
from pathlib import Path

PIN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]*==[A-Za-z0-9][A-Za-z0-9_.!+-]*')
SHA = re.compile(r'--hash=sha256:[a-fA-F0-9]{64}(?=\s|$)')


def vet_lock(raw):
    for n, line in enumerate(raw.splitlines(), 1):
        ln = line.strip()
        if not ln or ln.startswith('#'):
            continue
        if ln.startswith(('-','git+','http:','https:','file:','-e','--')):
            raise ValueError(f'Unsupported source/options at line {n}')
        if not PIN.match(ln):
            raise ValueError(f'Missing exact == version at line {n}')
        if not SHA.search(ln):
            raise ValueError(f'Missing sha256 hash at line {n}')
        if ';' in ln or '\\' in ln:
            raise ValueError(f'Conditional/multiline inputs not supported at line {n}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lock', required=True, type=Path)
    ap.add_argument('--venv', required=True, type=Path)
    ap.add_argument('--execute', action='store_true')
    a = ap.parse_args()
    raw = a.lock.read_text(encoding='utf-8')
    vet_lock(raw)
    if not a.execute:
        print('Validated locked package requirements; no install attempted')
        return
    if a.venv.resolve() == Path(sys.prefix).resolve() or a.venv.resolve() == Path('/').resolve():
        raise SystemExit('Refusing host/global environment')
    venv.create(a.venv, with_pip=True, clear=False)
    exe = a.venv / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    subprocess.run([str(exe), '-m', 'pip', 'install', '--require-hashes', '--only-binary=:all:', '--no-input', '-r', str(a.lock.resolve())], check=True)
    print('Installed to isolated venv; independent execution/rights check still required')


if __name__ == '__main__':
    main()
