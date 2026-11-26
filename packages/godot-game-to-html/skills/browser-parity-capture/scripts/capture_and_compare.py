#!/usr/bin/env python3
"""Playwright Chromium captures two *real* Godot/Unity/Three/Pixi web renderers,
then delegates aligned PNG comparison to the existing Pixelmatch skill.

Original project, browser games, source textures and scenes are NEVER changed.
Web builds are served via short-lived loopback HTTP with Godot isolation headers.

Required separately installed: playwright==1.65.1 + Chromium Playwright browser,
node/npm and existing Pixelmatch/pngjs module for comparison. No network dependencies
at the HTML game runtime; this tool runs only on the developer's machine.
"""
from __future__ import annotations
import argparse
import asyncio
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import subprocess
import sys
from threading import Thread
from urllib.parse import urlparse

SKILL_ROOT = Path(__file__).resolve().parents[2]
PIXELMATCH = SKILL_ROOT / 'visual-parity-guard' / 'scripts' / 'visual_parity.py'
MAX_STEPS = 100
MAX_WAIT_MS = 20000
MAX_SCREENSHOTS = 40
FILE_SAFE = re.compile(r'^[a-zA-Z0-9_-]{1,50}$')


class GameHandler(SimpleHTTPRequestHandler):
    """Scope files to exactly one source build directory; no write endpoints."""
    def __init__(self, *args, directory, **kwargs):
        super().__init__(*args, directory=str(directory), **kwargs)

    def log_message(self, *_):
        pass

    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy', 'same-origin')
        self.send_header('Cross-Origin-Embedder-Policy', 'require-corp')
        self.send_header('Cross-Origin-Resource-Policy', 'same-origin')
        self.send_header('Cache-Control', 'no-store')
        request_path = urlparse(self.path).path
        if request_path.endswith('.br'):
            self.send_header('Content-Encoding', 'br')
        elif request_path.endswith('.gz'):
            self.send_header('Content-Encoding', 'gzip')
        super().end_headers()

    def guess_type(self, path):
        base = path[:-3] if path.endswith('.br') else path[:-3] if path.endswith('.gz') else path
        if base.endswith('.wasm'): return 'application/wasm'
        if base.endswith('.pck'): return 'application/octet-stream'
        if base.endswith('.js'): return 'text/javascript'
        if base.endswith('.data'): return 'application/octet-stream'
        return super().guess_type(base)

    def send_head(self):
        # SimpleHTTPRequestHandler can resolve symlinks outside the directory.
        source = Path(self.directory).resolve()
        target = Path(self.translate_path(self.path)).resolve()
        if not target.is_relative_to(source):
            self.send_error(403, 'Resource outside exported game directory')
            return None
        result = super().send_head()
        return result


def parse_input(raw: str):
    url = urlparse(raw)
    if url.scheme in ('https', 'http'):
        if not url.netloc or url.username or url.password:
            raise ValueError('Invalid game URL')
        return {'url': raw, 'folder': None, 'server': None}
    if url.scheme and url.scheme != 'file':
        raise ValueError('Use a local Web build or an explicit http(s) URL')
    path = Path(url.path if url.scheme == 'file' else raw).expanduser().resolve(strict=True)
    if path.is_dir():
        entry = path / 'index.html'
        if not entry.is_file():
            raise ValueError(f'No index.html in Web build: {path}')
    elif path.is_file() and path.suffix.lower() == '.html':
        entry = path
        path = entry.parent
    else:
        raise ValueError('Local input must be an HTML entry or a folder with index.html')
    return {'url': None, 'folder': path, 'entry': entry.name, 'server': None}


def scenario_from_file(file: Path | None):
    if not file:
        return {'steps': [{'action': 'screenshot', 'name': '00-start'}]}
    obj = json.loads(file.read_text(encoding='utf-8'))
    if not isinstance(obj, dict) or not isinstance(obj.get('steps'), list):
        raise ValueError('Scenario JSON requires {"steps":[...]}')
    steps = obj['steps']
    if len(steps) > MAX_STEPS: raise ValueError('Scenario exceeds 100 actions')
    images = 0
    used = set()
    for i, step in enumerate(steps):
        if not isinstance(step, dict) or step.get('action') not in ('screenshot', 'press', 'hold', 'click', 'wait'):
            raise ValueError(f'Unsupported step #{i}')
        action = step['action']
        if action == 'screenshot':
            name = step.get('name')
            if not isinstance(name, str) or not FILE_SAFE.fullmatch(name) or name in used:
                raise ValueError('Every screenshot must have a unique ASCII name (letters/numbers/_/-)')
            images += 1
            used.add(name)
        elif action in ('press','hold'):
            if not isinstance(step.get('key'), str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,20}|Arrow(?:Up|Down|Left|Right)|Space|Enter|Escape',step['key']):
                raise ValueError(f'Invalid keyboard key at step #{i}')
        elif action == 'click':
            if not all(isinstance(step.get(k), int) and step[k] >= 0 for k in ('x','y')):
                raise ValueError('Click steps require integer screen x/y')
        if action in ('hold', 'wait'):
            ms = step.get('ms')
            if not isinstance(ms, int) or not 0 <= ms <= MAX_WAIT_MS:
                raise ValueError(f'Invalid wait/hold milliseconds at step #{i}')
    if images == 0 or images > MAX_SCREENSHOTS:
        raise ValueError('Scenario needs 1–40 screenshot actions')
    return obj


def start_server(entry):
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(GameHandler,directory=entry['folder']))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    entry['server'] = server
    entry['url'] = f"http://127.0.0.1:{server.server_address[1]}/{entry['entry']}"


async def snapshot(browser, entry, label: str, target: Path, steps: list, vp, dpr, ready, initial_ms, timeout_ms):
    context = await browser.new_context(viewport=vp, device_scale_factor=dpr, accept_downloads=False,
                                        service_workers='block', ignore_https_errors=False)
    page = await context.new_page()
    errors = []
    page.on('pageerror', lambda exc: errors.append(str(exc)))
    try:
        response = await page.goto(entry['url'], wait_until='domcontentloaded', timeout=timeout_ms)
        if response and response.status >= 400:
            raise RuntimeError(f'{label}: page returned HTTP {response.status}')
        if ready:
            await page.locator(ready).first.wait_for(state='visible', timeout=timeout_ms)
        await asyncio.sleep(initial_ms / 1000)
        if errors:
            raise RuntimeError(f'{label}: browser JavaScript error: {errors[0][:250]}')
        for step in steps:
            action = step['action']
            if action == 'wait':
                await asyncio.sleep(step['ms']/1000)
            elif action == 'press':
                await page.keyboard.press(step['key'])
            elif action == 'hold':
                await page.keyboard.down(step['key'])
                try: await asyncio.sleep(step['ms']/1000)
                finally: await page.keyboard.up(step['key'])
            elif action == 'click':
                if step['x'] >= vp['width'] or step['y'] >= vp['height']:
                    raise ValueError('Scenario click is outside viewport')
                await page.mouse.click(step['x'],step['y'])
            elif action == 'screenshot':
                dest = target/(step['name']+'.png')
                await page.screenshot(path=str(dest), type='png', full_page=False, animations='allow', timeout=timeout_ms)
                if not dest.is_file() or dest.stat().st_size < 100:
                    raise RuntimeError(f'{label}: empty screenshot {dest}')
        if errors:
            raise RuntimeError(f'{label}: browser JavaScript error: {errors[0][:250]}')
    finally:
        await context.close()


async def browser_capture(original, candidate, baseline, optimized, steps, args):
    try:
        from playwright.async_api import async_playwright
    except ImportError as error:
        raise RuntimeError('Install official Playwright Python 1.65.1 and its Chromium browser first') from error
    async with async_playwright() as p:
        browser_type = getattr(p, args.browser)
        browser = await browser_type.launch(headless=not args.headed, **({'executable_path': args.browser_executable} if args.browser_executable else {}))
        try:
            viewport = {'width': args.width, 'height': args.height}
            # Separate fresh contexts; identical browser, viewport, DPR, and action sequence.
            await snapshot(browser,original,'original',baseline,steps,viewport,args.dpr,args.ready_selector,args.initial_wait_ms,args.timeout_ms)
            await snapshot(browser,candidate,'candidate',optimized,steps,viewport,args.dpr,args.ready_selector,args.initial_wait_ms,args.timeout_ms)
        finally:
            await browser.close()


def main():
    p=argparse.ArgumentParser(description='Playwright real-browser frame capture -> existing Pixelmatch guard; originals untouched')
    p.add_argument('--original',required=True,help='Original Godot/Unity Web URL, HTML, or exported directory')
    p.add_argument('--candidate',required=True,help='Candidate Web URL, HTML, or exported directory')
    p.add_argument('--out',type=Path,required=True,help='NEW, separate destination folder')
    p.add_argument('--scenario',type=Path,help='Optional explicit aligned interaction/screenshot JSON')
    p.add_argument('--browser',choices=['chromium','firefox','webkit'],default='chromium')
    p.add_argument('--width',type=int,default=1280)
    p.add_argument('--height',type=int,default=720)
    p.add_argument('--dpr',type=float,default=1)
    p.add_argument('--ready-selector',default='canvas',help='Wait for same selector on both builds, default canvas')
    p.add_argument('--initial-wait-ms',type=int,default=1500)
    p.add_argument('--timeout-ms',type=int,default=30000)
    p.add_argument('--max-ratio',type=float,default=.03)
    p.add_argument('--threshold',type=float,default=.10)
    p.add_argument('--capture-only',action='store_true',help='Capture PNG only, do not assert visual parity')
    p.add_argument('--no-install',action='store_true',help='Do not auto-install Pixelmatch dependencies')
    p.add_argument('--headed',action='store_true',help='Show Chromium window for manual investigation')
    p.add_argument('--browser-executable',help='Explicit trusted installed Chromium/browser executable if bundled browser absent')
    args=p.parse_args()
    if not 320<=args.width<=4096 or not 240<=args.height<=2160 or not .5<=args.dpr<=3:
        p.error('Invalid viewport or DPR')
    if not 0<=args.initial_wait_ms<=MAX_WAIT_MS or not 1000<=args.timeout_ms<=120000:
        p.error('Invalid timeout')
    if not 0<=args.max_ratio<=1 or not 0<=args.threshold<=1:
        p.error('Similarity ratio/threshold must be in [0,1]')
    original=parse_input(args.original)
    candidate=parse_input(args.candidate)
    out=args.out.expanduser().resolve()
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        p.error('Output must be a fresh directory: refusing overwrite')
    for inp in (original,candidate):
        folder=inp['folder']
        if folder and (out==folder or folder in out.parents or out in folder.parents):
            p.error('Capture output must not overlap either input game directory')
    scenario=scenario_from_file(args.scenario)
    steps=scenario['steps']
    if args.browser!='chromium':
        print('WARNING: Godot/Unity WebGL compatibility is primarily verified with Chromium here',file=sys.stderr)
    if args.scenario is None:
        print('NOTE: only one initial scene frame captured; this does not establish full-game visual fidelity')
    out.mkdir(parents=True,exist_ok=True)
    baseline=out/'baseline'; optimized=out/'candidate'
    baseline.mkdir(); optimized.mkdir()
    try:
        for entry in (original,candidate):
            if entry['folder']: start_server(entry)
        asyncio.run(browser_capture(original,candidate,baseline,optimized,steps,args))
    finally:
        for entry in (original,candidate):
            server=entry['server']
            if server:
                server.shutdown()
                server.server_close()
    print('PLAYWRIGHT captured aligned screenshots:',baseline,optimized)
    if args.capture_only:
        print('CAPTURE ONLY: no visual parity claim; compare only deterministically aligned frames')
        return
    if not PIXELMATCH.is_file():
        raise RuntimeError('Existing Pixelmatch visual_parity.py module missing; cannot compare')
    cmd=[sys.executable,str(PIXELMATCH),'--baseline',str(baseline),'--candidate',str(optimized),
         '--max-ratio',str(args.max_ratio),'--threshold',str(args.threshold)]
    if args.no_install:cmd.append('--no-install')
    subprocess.run(cmd,check=True,timeout=360)
    print('BROWSER + PIXELMATCH: frame gate passed; not a guarantee of whole-game fidelity')


if __name__=='__main__':
    try: main()
    except Exception as exc:
        sys.exit('ERROR: '+str(exc))
