#!/usr/bin/env python3
"""META GAMES catalog updater. Offline/local only; Git/PR/deployment are agent tasks."""
from __future__ import annotations

import argparse
import datetime
import html as html_lib
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

BASE = "https://mpaykin1.github.io/meta6/playgama-catalog/"
LOCALES = {"en": "", "ru": "ru/", "de": "de/", "fr": "fr/", "ja": "ja/", "ko": "ko/", "es": "es/", "pt-BR": "pt-br/"}
GENRES = {"action", "adventure", "horror", "arcade", "story"}
CARD = re.compile(r'<article\s+class="(?:game-card|card)(?:\s+[\w-]+)*"[^>]*>[\s\S]*?</article>')
ANCHOR_CARD = re.compile(r'<a\s+class="card(?:\s+[\w-]+)*"[^>]*>[\s\S]*?</a>')
LD = re.compile(r'<script\s+type="application/ld\+json">([\s\S]*?)</script>')
PLAY = re.compile(r'^https://playgama\.ai/play/[a-zA-Z0-9_-]+/?$')


def must(condition: bool, message: str):
    if not condition:
        raise ValueError(message)


def one_change(source: str, pattern: str, repl: str, *, flags=0, optional=False) -> str:
    updated, n = re.subn(pattern, lambda m: repl, source, count=1, flags=flags)
    must(n == 1 or optional, f"Missing expected structure: {pattern[:70]}")
    return updated


def set_meta(text: str, key: str, value: str, *, optional=False) -> str:
    escaped = html_lib.escape(value, quote=True)
    pat = rf'(<meta\s+{re.escape(key)}\s+content=")[^"]*(")'
    updated, n = re.subn(pat, lambda m: m.group(1) + escaped + m.group(2), text, count=1)
    must(n == 1 or optional, f"No meta tag {key}")
    return updated


def set_ld(text: str, fun) -> str:
    m = LD.search(text)
    must(bool(m), "JSON-LD missing")
    d = json.loads(m.group(1))
    fun(d)
    serialized = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace('<', '\\u003c')
    return text[:m.start(1)] + serialized + text[m.end(1):]


def parse_ld(text: str) -> dict:
    m = LD.search(text)
    must(bool(m), "JSON-LD missing")
    return json.loads(m.group(1))


def local_copy(image: Path, output: Path):
    must(image.exists() and image.is_file(), f"Cover is unavailable: {image}")
    suffix = image.suffix.lower()
    must(suffix in (".png", ".jpg", ".jpeg", ".webp"), "Cover must be PNG, JPG or WebP")
    if not output.exists():
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(image, output)
    elif output.read_bytes() != image.read_bytes():
        raise ValueError("Existing cover has different bytes: refusing to overwrite")


def slug_card(text: str, slug: str) -> str:
    return re.sub(r'(class="(?:game-card|card))\s+[\w-]+', rf'\1 {slug}', text, count=1)


def replace_links(card: str, url: str) -> str:
    def swap(m):
        tag = m.group(0)
        tag = re.sub(r'\bhref="[^"]*"', f'href="{url}"', tag)
        if 'href=' not in tag:
            tag = tag[:-1] + f' href="{url}">'
        tag = re.sub(r'\s+target="[^"]*"', '', tag)
        tag = re.sub(r'\s+rel="[^"]*"', '', tag)
        return tag[:-1] + ' target="_blank" rel="noopener noreferrer">'
    card = re.sub(r'<a\b[^>]*>', swap, card)
    # No intermediate detail/other-site links within a game card.
    card = re.sub(r'<a\s+class="(?:details|details-link|more)"[^>]*>[\s\S]*?</a>', '', card)
    return card


def new_card_from_template(template: str, cfg: dict, game: dict, cover_url: str) -> str:
    card = slug_card(template, game['slug'])
    card = re.sub(r'\s+data-game-status="[^"]+"', '', card)
    card = card.replace('>', ' data-game-status="playgama-direct">', 1) if card.startswith('<article') else card
    card = replace_links(card, game['playgama_url'])
    # Preserve template structures across EN/RU/DE/FR/JA/KO/ES/PT-BR.
    card = re.sub(r'(<img\b[^>]*\bsrc=")[^"]+("[^>]*>)', lambda m: m.group(1) + cover_url + m.group(2), card, count=1)
    card = re.sub(r'(<img\b[^>]*\balt=")[^"]*(")', lambda m: m.group(1) + html_lib.escape(cfg['alt'], quote=True) + m.group(2), card, count=1)
    card = re.sub(r'(<a\s+class="art"[^>]*\baria-label=")[^"]*(")', lambda m: m.group(1) + html_lib.escape(cfg['aria'], quote=True) + m.group(2), card, count=1)
    card = re.sub(r'(<p\s+class="(?:tag|genre)">)[\s\S]*?(</p>)', lambda m: m.group(1) + html_lib.escape(cfg['tag']) + m.group(2), card, count=1)
    card = re.sub(r'(<p\s+class="desc">)[\s\S]*?(</p>)', lambda m: m.group(1) + html_lib.escape(cfg['description']) + m.group(2), card, count=1)
    # Text in h3 is the title; leave a nested title anchor if one exists.
    card = re.sub(r'(<h3>)([\s\S]*?)(</h3>)', lambda m: m.group(1) + (re.sub(r'(?<=>)[^<]+(?=</a>)', html_lib.escape(game['title']), m.group(2), count=1) if '<a ' in m.group(2) else html_lib.escape(game['title'])) + m.group(3), card, count=1)
    # Some templates have h2 title instead of h3 (genre pages).
    if '<h3>' not in card:
        card = re.sub(r'(<h2>)([\s\S]*?)(</h2>)', lambda m: m.group(1) + (re.sub(r'(?<=>)[^<]+(?=</a>)', html_lib.escape(game['title']), m.group(2), count=1) if '<a ' in m.group(2) else html_lib.escape(game['title'])) + m.group(3), card, count=1)
    card = re.sub(r'(?<=aria-label=")[^"]+(?=")', html_lib.escape(cfg['aria'], quote=True), card)
    card = re.sub(r'<img([^>]*?)loading="lazy"([^>]*?)>', r'<img\1loading="eager"\2>', card, count=1)
    if 'fetchpriority=' not in card:
        card = re.sub(r'(<img\b[^>]*?)(>)', r'\1 fetchpriority="high"\2', card, count=1)
    must(game['playgama_url'] in card and cover_url in card and game['title'] in card, "New card missing data")
    return card


def anchor_hrefs(card: str) -> list[str]:
    return re.findall(r'<a\b[^>]*\bhref="([^"]+)"', card)


def validate_direct(card: str, url: str, *, n=3):
    links = anchor_hrefs(card)
    must(len(links) == n and all(link == url for link in links), f"Expected {n} direct Playgama anchors, got {links}")
    must(all('target="_blank"' in m and 'rel="noopener noreferrer"' in m
             for m in re.findall(r'<a\b[^>]*>', card)), "Missing safe external link attributes")
    must('/games/' not in card and 'class="details' not in card and 'class="more' not in card,
         "New card includes forbidden intermediary page")


def refresh_count(text: str, old: int, new: int) -> str:
    # Target only labels, not arbitrary numbers in content or URLs.
    text = re.sub(r'(<div\s+class="stats">[\s\S]*?</div>)',
                  lambda m: m.group(1).replace(f'<b>{old}</b>', f'<b>{new}</b>'), text, count=1)
    text = re.sub(r'(<span\s+class="count">[\s\S]*?</span>)',
                  lambda m: re.sub(rf'\b{old}\b', str(new), m.group(1)), text, count=1)
    text = re.sub(r'(<footer>[\s\S]*?</footer>)',
                  lambda m: re.sub(rf'\b{old}\b', str(new), m.group(1)), text, count=1)
    return text


def add_home(content: str, cfg: dict, game: dict, cover_url: str) -> str:
    cards = list(CARD.finditer(content))
    must(cards, 'No game cards found')
    old = len(cards)
    must(game['title'] not in content, f"Game title already appears: {game['title']} — verify instead")
    template = cards[0].group(0)
    must(len(anchor_hrefs(template)) >= 2, 'First card is not expected catalog template')
    new_card = new_card_from_template(template, cfg, game, cover_url)
    validate_direct(new_card, game['playgama_url'])
    old_card = template.replace('loading="eager"', 'loading="lazy"').replace(' fetchpriority="high"', '')
    content = content[:cards[0].start()] + new_card + '\n' + old_card + content[cards[0].end():]
    def update_ld(d):
        lst = d['mainEntity']['itemListElement']
        must(len(lst) == old, 'JSON-LD and visible cards disagree before change')
        for item in lst:
            item['position'] += 1
        lst.insert(0, {'@type': 'ListItem', 'position': 1, 'item': {
            '@type': 'VideoGame', 'name': game['title'], 'url': game['playgama_url'],
            'image': cover_url, 'description': cfg['description'],
            'genre': game['genres'], 'gamePlatform': 'Web browser', 'isAccessibleForFree': True}})
        d['mainEntity']['numberOfItems'] = old + 1
        d['description'] = cfg['seo']
        if 'name' in d:
            d['name'] = re.sub(rf'\b{old}\b', str(old + 1), d['name'])
    content = set_ld(content, update_ld)
    content = re.sub(r'(<title>)([\s\S]*?)(</title>)', lambda m: m.group(1) + re.sub(rf'\b{old}\b', str(old + 1), m.group(2)) + m.group(3), content, count=1)
    content = set_meta(content, 'name="description"', cfg['seo'])
    content = set_meta(content, 'property="og:description"', cfg['seo'])
    content = set_meta(content, 'name="twitter:description"', cfg['seo'], optional=True)
    for tag in ('property="og:title"', 'name="twitter:title"'):
        content = re.sub(rf'(<meta\s+{re.escape(tag)}\s+content=")[^"]*(")',
                         lambda m: m.group(1) + re.sub(rf'\b{old}\b', str(old + 1), m.group(0).split('content="', 1)[1].rsplit('"', 1)[0]) + m.group(2), content, count=1)
    content = set_meta(content, 'property="og:image"', cover_url, optional=True)
    content = set_meta(content, 'name="twitter:image"', cover_url, optional=True)
    content = set_meta(content, 'property="og:image:alt"', cfg['alt'], optional=True)
    content = refresh_count(content, old, old + 1)
    content = content.replace('</style>', f'.game-card.{game["slug"]} .art img,.card.{game["slug"]} .art img{{object-fit:contain;background:#151119}}\n</style>')
    must(len(CARD.findall(content)) == old + 1, 'DOM count did not increase by one')
    return content


def add_genre(content: str, cfg: dict, game: dict, cover_url: str, main_count: int) -> str:
    dom = list(CARD.finditer(content))
    is_en_anchor = False
    if not dom:
        dom = list(ANCHOR_CARD.finditer(content))
        is_en_anchor = True
    must(dom, 'Genre page has no matching game card')
    old = len(dom)
    template = dom[0].group(0)
    if is_en_anchor:
        new_card = re.sub(r'class="card(?:\s+[\w-]+)?"', f'class="card {game["slug"]}"', template, count=1)
        new_card = replace_links(new_card, game['playgama_url'])
        new_card = re.sub(r'(<img\b[^>]*\bsrc=")[^"]+"', lambda m: m.group(1) + cover_url + '"', new_card, count=1)
        new_card = re.sub(r'(<img\b[^>]*\balt=")[^"]+"', lambda m: m.group(1) + html_lib.escape(cfg['alt'], quote=True) + '"', new_card, count=1)
        new_card = re.sub(r'<small>[\s\S]*?</small>', f'<small>{html_lib.escape(cfg["tag"])}</small>', new_card, count=1)
        new_card = re.sub(r'<h2>[\s\S]*?</h2>', f'<h2>{html_lib.escape(game["title"])}</h2>', new_card, count=1)
        new_card = re.sub(r'(<p>)[\s\S]*?(</p>)', lambda m: m.group(1) + html_lib.escape(cfg['description']) + m.group(2), new_card, count=1)
        new_card = new_card.replace('loading="lazy"', 'loading="eager"')
        if 'fetchpriority=' not in new_card:
            new_card = re.sub(r'(<img\b[^>]*)(>)', r'\1 fetchpriority="high"\2', new_card, count=1)
        validate_direct(new_card, game['playgama_url'], n=1)
    else:
        new_card = re.sub(r'(<article\s+class="card)(\s+[\w-]+)?(")', rf'\1 {game["slug"]}\3', template, count=1)
        new_card = replace_links(new_card, game['playgama_url'])
        new_card = re.sub(r'<a\s+class="(?:details|details-link|more)"[^>]*>[\s\S]*?</a>', '', new_card)
        new_card = re.sub(r'(<img\b[^>]*\bsrc=")[^"]+"', lambda m: m.group(1) + cover_url + '"', new_card, count=1)
        new_card = re.sub(r'(<img\b[^>]*\balt=")[^"]+"', lambda m: m.group(1) + html_lib.escape(cfg['alt'], quote=True) + '"', new_card, count=1)
        new_card = re.sub(r'(<h2>)[\s\S]*?(</h2>)', lambda m: m.group(1) + f'<a href="{game["playgama_url"]}" target="_blank" rel="noopener noreferrer">{html_lib.escape(game["title"])}</a>' + m.group(2), new_card, count=1)
        new_card = re.sub(r'(<div\s+class="(?:info|copy)">[\s\S]*?<p>)[\s\S]*?(</p>)', lambda m: m.group(1) + html_lib.escape(cfg['description']) + m.group(2), new_card, count=1)
        new_card = new_card.replace('loading="lazy"', 'loading="eager"')
        if 'fetchpriority=' not in new_card:
            new_card = re.sub(r'(<img\b[^>]*)(>)', r'\1 fetchpriority="high"\2', new_card, count=1)
        validate_direct(new_card, game['playgama_url'])
    old_card = template.replace('loading="eager"', 'loading="lazy"').replace(' fetchpriority="high"', '')
    content = content[:dom[0].start()] + new_card + old_card + content[dom[0].end():]
    def update_ld(d):
        lst = d['mainEntity']['itemListElement']
        must(len(lst) == old, 'Genre JSON-LD does not match visible card count')
        for i in lst:
            i['position'] += 1
        lst.insert(0, {'@type': 'ListItem', 'position': 1, 'name': game['title'], 'url': game['playgama_url']})
        d['mainEntity']['numberOfItems'] = old + 1
    content = set_ld(content, update_ld)
    # The genre breadcrumb sometimes refers to the old whole-catalog total.
    content = re.sub(r'(<nav\s+class="crumbs"[^>]*>[\s\S]*?</nav>)',
                     lambda m: re.sub(rf'\b{main_count - 1}\b', str(main_count), m.group(1)), content, count=1)
    content = re.sub(r'(<footer>[\s\S]*?</footer>)',
                     lambda m: re.sub(rf'\b{main_count - 1}\b', str(main_count), m.group(1)), content, count=1)
    content = re.sub(r'(<p><a\s+[^>]*>[^<]*</a></p>)',
                     lambda m: re.sub(rf'\b{main_count - 1}\b', str(main_count), m.group(1)), content)
    if cfg.get('genre_intro'):
        content = re.sub(r'(<p\s+class="(?:intro|lead)">)[\s\S]*?(</p>)',
                         lambda m: m.group(1) + html_lib.escape(cfg['genre_intro']) + m.group(2), content, count=1)
    must(len(CARD.findall(content)) == old + 1 if not is_en_anchor else len(ANCHOR_CARD.findall(content)) == old + 1,
         'Genre card count failed')
    return content


def update_inventory(content: str, game: dict, cover_url: str) -> str:
    inv = json.loads(content)
    records = inv.get('games', []) + inv.get('pendingGames', [])
    must(not any(g.get('slug') == game['slug'] or g.get('title', '').casefold() == game['title'].casefold() for g in records), 'Game already exists in inventory')
    entry = {'title': game['title'], 'slug': game['slug'], 'coverUrl': cover_url,
             'playgamaUrl': game['playgama_url'], 'source': 'Owner-supplied cover and verified/direct game URL',
             'verification': game['verification'], 'indexable': True}
    inv['pendingGames'] = [entry] + inv.get('pendingGames', [])
    return json.dumps(inv, ensure_ascii=False, indent=2) + '\n'


def update_sitemap(content: str, date: str, dirs: set[str]) -> str:
    for suffix in dirs:
        url = BASE + suffix
        pat = re.compile(r'(<url>\s*<loc>' + re.escape(url) + r'</loc>\s*<lastmod>)([^<]+)(</lastmod>)')
        content, count = pat.subn(lambda m: m.group(1) + date + m.group(3), content, count=1)
        must(count == 1, f'Sitemap entry not found: {url}')
    ET.fromstring(content)
    return content


def parse_game(path: Path) -> dict:
    game = json.loads(path.read_text('utf-8'))
    must(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', game['slug']) is not None, 'Invalid slug')
    must(PLAY.fullmatch(game['playgama_url']) is not None, 'Direct Playgama play URL required')
    must(bool(game['title']) and 'REPLACE' not in game['playgama_url'] and game['title'] != 'Название новой игры — заполнить по фактам', 'Replace example with real facts')
    must(game.get('genres') and all(g in GENRES for g in game['genres']), 'Unknown or missing genre')
    must(set(game['locales']) == set(LOCALES), 'Exactly eight translations required')
    must(all(all(v.get(f) for f in ('tag', 'description', 'alt', 'aria', 'seo')) for v in game['locales'].values()), 'Missing localized field')
    must(bool(game.get('verification')), 'State who verified the Playgama URL/status')
    return game


def verify(root: Path, game: dict):
    catalog = root / 'playgama-catalog'
    cover_dir = catalog / 'covers'
    matches = list(cover_dir.glob(game['slug'] + '.*'))
    must(len(matches) == 1, 'Exactly one cover file expected')
    cover_url = BASE + 'covers/' + matches[0].name
    totals = set()
    for lang, suffix in LOCALES.items():
        c = (catalog / suffix / 'index.html').read_text('utf-8')
        cards = CARD.findall(c)
        must(cards and game['title'] in cards[0], f'{lang}: not first')
        must(cover_url in cards[0], f'{lang}: missing cover')
        validate_direct(cards[0], game['playgama_url'])
        d = parse_ld(c)
        must(len(d['mainEntity']['itemListElement']) == len(cards) == d['mainEntity']['numberOfItems'], f'{lang}: JSON-LD/card mismatch')
        first = d['mainEntity']['itemListElement'][0]['item']
        must(first['name'] == game['title'] and first['url'] == game['playgama_url'], f'{lang}: incorrect JSON-LD first')
        must(all(item['position'] == i for i, item in enumerate(d['mainEntity']['itemListElement'], 1)), f'{lang}: broken JSON-LD positions')
        must('lore.html' in c and 'canonical' in c and 'hreflang' in c, f'{lang}: lore/canonical/hreflang missing')
        totals.add(len(cards))
        for genre in game['genres']:
            p = catalog / suffix / 'genres' / genre / 'index.html'
            if p.exists():
                gc = p.read_text('utf-8')
                cards_genre = CARD.findall(gc) or ANCHOR_CARD.findall(gc)
                must(cards_genre and game['title'] in cards_genre[0], f'{lang}/{genre}: not first')
                validate_direct(cards_genre[0], game['playgama_url'], n=1 if cards_genre[0].startswith('<a ') else 3)
                gd = parse_ld(gc)
                must(len(cards_genre) == gd['mainEntity']['numberOfItems'], f'{lang}/{genre}: count mismatch')
    must(len(totals) == 1, 'Inconsistent locale card totals')
    inventory = json.loads((catalog / 'playgama-inventory.json').read_text('utf-8'))
    must(sum(x.get('slug') == game['slug'] for x in inventory.get('games', []) + inventory.get('pendingGames', [])) == 1, 'Inventory missing or duplicate game')
    ET.fromstring((catalog / 'sitemap.xml').read_text('utf-8'))
    must(not (catalog / 'games' / game['slug']).exists(), 'Forbidden intermediary page exists')
    return totals.pop()


def add(root: Path, game: dict, image: Path, date: str):
    catalog = root / 'playgama-catalog'
    must(catalog.is_dir(), f'Not META GAMES root: {root}')
    must(not (catalog / 'games' / game['slug']).exists(), 'Forbidden intermediary page already exists')
    target = catalog / 'covers' / (game['slug'] + image.suffix.lower())
    must(not any((catalog / 'covers').glob(game['slug'] + '.*')), 'Cover already exists; use verify')
    # Stage all textual transforms in memory first: if one locale cannot be updated, write nothing.
    cover_url = BASE + 'covers/' + target.name
    changed: dict[Path, str] = {}
    dirs = set()
    counts = set()
    for lang, suffix in LOCALES.items():
        p = catalog / suffix / 'index.html'
        must(p.exists(), f'Missing language page: {lang}')
        updated = add_home(p.read_text('utf-8'), game['locales'][lang], game, cover_url)
        changed[p] = updated
        counts.add(len(CARD.findall(updated)))
        dirs.add(suffix)
    must(len(counts) == 1, 'Main page count differs across languages')
    new_count = counts.pop()
    for lang, suffix in LOCALES.items():
        for genre in game['genres']:
            p = catalog / suffix / 'genres' / genre / 'index.html'
            if not p.exists():
                continue
            updated = add_genre(p.read_text('utf-8'), game['locales'][lang], game, cover_url, new_count)
            changed[p] = updated
            dirs.add(suffix + 'genres/' + genre + '/')
    p = catalog / 'playgama-inventory.json'
    changed[p] = update_inventory(p.read_text('utf-8'), game, cover_url)
    p = catalog / 'sitemap.xml'
    changed[p] = update_sitemap(p.read_text('utf-8'), date, dirs)
    local_copy(image, target)
    for p, content in changed.items():
        p.write_text(content, encoding='utf-8')
    return len(changed), new_count


def main():
    cli = argparse.ArgumentParser(description='META GAMES Playgama catalog updater (offline)')
    sub = cli.add_subparsers(dest='command', required=True)
    for cmd in ('add', 'verify'):
        sp = sub.add_parser(cmd)
        sp.add_argument('--root', type=Path, required=True, help='Root of a checked-out mpaykin1/meta6 repository')
        sp.add_argument('--game', type=Path, required=True, help='Fully verified and translated JSON metadata')
        if cmd == 'add':
            sp.add_argument('--image', type=Path, required=True, help='Owner-supplied cover image')
            sp.add_argument('--date', default=datetime.datetime.now(datetime.timezone.utc).date().isoformat())
    args = cli.parse_args()
    game = parse_game(args.game)
    if args.command == 'add':
        changed, count = add(args.root, game, args.image, args.date)
        verify(args.root, game)
        print(f'Updated {changed} catalog files, {count} games; no git push performed.')
    else:
        count = verify(args.root, game)
        print(f'Catalog structure valid for {game["title"]}: {count} games across 8 languages.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, FileNotFoundError, ET.ParseError) as exc:
        print(f'CATALOG_BLOCKED: {exc}', file=sys.stderr)
        sys.exit(2)
