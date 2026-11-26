#!/usr/bin/env python3
"""Release-blocking visual contrast inspection of REAL emitted game pixels.

Requires: pip install playwright pillow; `playwright install chromium` if needed.
Game must implement the deterministic inspection interface described in
references/visible-effects-release-gate.md. No mock screenshot or self-reported
render status can replace comparing actual enabled/disabled frames.
"""
import argparse
import io
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from PIL import Image, ImageChops

STYLES = ('masonry', 'rock', 'mist', 'arches', 'fragments')
VIEWS = ((1280, 720), (390, 844))
YAW = (0, 90)


def diff_fraction(left_png, right_png):
    a = Image.open(io.BytesIO(left_png)).convert('RGB')
    b = Image.open(io.BytesIO(right_png)).convert('RGB')
    if a.size != b.size:
        raise ValueError('Mismatching image sizes in effect comparison')
    w, h = a.size
    # Compare middle 75% of the image: excludes UI and far screen corners.
    region = (int(w*.125), int(h*.125), int(w*.875), int(h*.875))
    a, b = a.crop(region), b.crop(region)
    diff = ImageChops.difference(a, b)
    rgb = diff.tobytes()
    changed = 0
    for i in range(0, len(rgb), 3):
        if max(rgb[i], rgb[i+1], rgb[i+2]) >= 32:
            changed += 1
    total = a.width * a.height
    return changed / total, changed


def capture(page, file_uri, style, enabled, yaw, t):
    from urllib.parse import urlsplit
    params = urlencode(dict(pngcity_audit=1, effect=style, enabled=int(enabled), yaw=yaw, time=t))
    sep = '&' if '?' in file_uri else '?'
    url = f'{file_uri}{sep}{params}'
    errors = []
    onerror = lambda error: errors.append(str(error))
    page.on('pageerror', onerror)
    try:
        page.goto(url, wait_until='load')
        page.wait_for_function('window.__PNG_CITY_VISIBILITY__?.ready === true', timeout=10000)
        meta = page.evaluate('window.__PNG_CITY_VISIBILITY__')
        if not isinstance(meta, dict) or meta.get('error') or meta.get('effect') != style or bool(meta.get('enabled')) != enabled:
            raise ValueError('Missing or inconsistent runtime effect identity')
        if meta.get('renderer') not in ('webgl2', 'canvas2d'):
            raise ValueError('Renderer mode is unknown')
        data = page.screenshot(type='png', animations='disabled')
        if errors:
            raise RuntimeError('; '.join(errors))
        return data, meta
    finally:
        page.remove_listener('pageerror', onerror)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('html', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--minimum-coverage', type=float, default=.01)
    args = p.parse_args()
    if not args.html.is_file():
        p.error(f'HTML not found: {args.html}')
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('BLOCKED: playwright missing; cannot certify visible effects', file=sys.stderr)
        return 2
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
    failures = []
    rows = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=['--enable-webgl','--use-gl=angle','--use-angle=swiftshader'])
        try:
            for w, h in VIEWS:
                page = browser.new_page(viewport={'width': w, 'height': h}, device_scale_factor=1)
                for style in STYLES:
                    for yaw in YAW:
                        key=f'{style}_{yaw}_{w}x{h}'
                        try:
                            off, meta_off = capture(page,args.html.resolve().as_uri(),style,False,yaw,2.0)
                            on, meta_on = capture(page,args.html.resolve().as_uri(),style,True,yaw,2.0)
                            fraction, pixels = diff_fraction(off, on)
                            if fraction < args.minimum_coverage or pixels < 70:
                                failures.append(f'{key}: invisible foundation ({fraction:.4%} changed, {pixels} pixels)')
                            if meta_on['renderer'] != meta_off['renderer']:
                                failures.append(f'{key}: renderer switched between comparisons')
                            if style in ('mist','fragments'):
                                later, _ = capture(page,args.html.resolve().as_uri(),style,True,yaw,3.2)
                                motion, moved = diff_fraction(on,later)
                                if motion < .0015 or moved < 70:
                                    failures.append(f'{key}: effect has no perceptible motion ({motion:.4%})')
                            if args.output:
                                (args.output/f'{key}_on.png').write_bytes(on)
                                (args.output/f'{key}_off.png').write_bytes(off)
                            rows.append(dict(effect=style, yaw=yaw, viewport=[w,h], change_fraction=fraction, renderer=meta_on['renderer']))
                        except Exception as exc:
                            failures.append(f'{key}: {exc}')
                page.close()
        finally:
            browser.close()
    print(json.dumps({'accepted':not failures,'observations':rows,'blockers':failures},indent=2,ensure_ascii=False))
    return 1 if failures else 0

if __name__=='__main__':
    sys.exit(main())
