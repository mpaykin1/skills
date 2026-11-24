#!/usr/bin/env python3
"""Verify the actually published META GAMES catalog. Network read-only; stdlib only.

Usage:
    python3 verify_live.py --game-url https://playgama.ai/play/<id> --title 'Title' --slug slug
A success exit code means eight live catalog locales, cover, JSON-LD and sitemap passed.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import re
import sys
from urllib.parse import urljoin, urlencode, urlparse, parse_qsl, urlunparse
from urllib.request import Request, urlopen

BASE = "https://mpaykin1.github.io/meta6/playgama-catalog/"
LOCALES = {"en": "", "ru": "ru/", "de": "de/", "fr": "fr/", "ja": "ja/", "ko": "ko/", "es": "es/", "pt-BR": "pt-br/"}
PLAY = re.compile(r"^https://playgama\.ai/play/[a-zA-Z0-9_-]+/?$")
LD = re.compile(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)


def require(ok, why):
    if not ok:
        raise ValueError(why)


def with_rev(url: str, rev: str) -> str:
    u = urlparse(url)
    query = dict(parse_qsl(u.query, keep_blank_values=True))
    query["rev"] = rev
    return urlunparse(u._replace(query=urlencode(query)))


def fetch(url: str, rev: str, timeout: int, *, image=False):
    url = with_rev(url, rev)
    headers = {"User-Agent": "META-GAMES-catalog-live-verifier/1.1",
               "Cache-Control": "no-cache", "Pragma": "no-cache"}
    with urlopen(Request(url, headers=headers), timeout=timeout) as response:
        status = response.status
        content_type = response.headers.get("Content-Type", "")
        # Max 2 MiB of HTML and 8 MiB of cover. Do not assume HEAD is supported.
        data = response.read((8 if image else 2) * 1024 * 1024 + 1)
    require(status == 200, f"HTTP {status} for {url}")
    require(len(data) <= (8 if image else 2) * 1024 * 1024, f"Oversized response {url}")
    if image:
        require(content_type.lower().startswith("image/"), f"Not image MIME ({content_type}): {url}")
        require(len(data) > 1024, f"Image unexpectedly small: {url}")
        # Reject HTML success pages, placeholders and broken WebP/PNG/JPEG headers.
        require(data[:4] == b"RIFF" and data[8:12] == b"WEBP" or
                data.startswith(b"\x89PNG\r\n\x1a\n") or data.startswith(b"\xff\xd8\xff"),
                f"Invalid cover signature: {url}")
        return data
    require("html" in content_type.lower() or "xml" in content_type.lower(),
            f"Not HTML/XML MIME ({content_type}): {url}")
    return data.decode("utf-8", errors="strict")


class Cards(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cards = []
        self.active = None
        self.article_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article":
            if self.active is not None:
                self.article_depth += 1
            else:
                cl = attrs.get("class", "").split()
                if "game-card" in cl or "card" in cl:
                    self.active = {"class": cl, "links": [], "cover": "", "alts": []}
                    self.article_depth = 1
        elif self.active is not None:
            if tag == "a":
                self.active["links"].append({"href": attrs.get("href", ""),
                                               "target": attrs.get("target", ""),
                                               "rel": attrs.get("rel", "")})
            if tag == "img":
                self.active["cover"] = attrs.get("src", "")
                self.active["alts"].append(attrs.get("alt", ""))

    def handle_endtag(self, tag):
        if tag == "article" and self.active is not None:
            self.article_depth -= 1
            if self.article_depth == 0:
                self.cards.append(self.active)
                self.active = None


def read_collection(page: str):
    for m in LD.finditer(page):
        try:
            payload = json.loads(m.group(1))
            graph = payload.get("@graph", [payload]) if isinstance(payload, dict) else payload
            for item in graph if isinstance(graph, list) else [graph]:
                if isinstance(item, dict) and isinstance(item.get("mainEntity"), dict):
                    entity = item["mainEntity"]
                    if entity.get("@type") == "ItemList":
                        return entity
        except (ValueError, TypeError):
            continue
    raise ValueError("Collection ItemList missing/invalid")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-url", required=True)
    parser.add_argument("--title", default=None)
    parser.add_argument("--slug", default=None)
    parser.add_argument("--base", default=BASE)
    parser.add_argument("--rev", default="live-check")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    require(PLAY.fullmatch(args.game_url), "Exact playgama.ai/play/<siteId> URL required")
    base = args.base.rstrip("/") + "/"
    expected_cover = None
    count = None
    for lang, path in LOCALES.items():
        url = urljoin(base, path + "index.html")
        source = fetch(url, args.rev, args.timeout)
        dom = Cards()
        dom.feed(source)
        require(bool(dom.cards), f"{lang}: no game cards in live HTML")
        first = dom.cards[0]
        hrefs = first["links"]
        require(len(hrefs) == 3 and all(a["href"] == args.game_url for a in hrefs),
                f"{lang}: three exact direct Playgama links missing: {hrefs}")
        require(all(a["target"] == "_blank" and "noopener" in a["rel"] and
                    "noreferrer" in a["rel"] for a in hrefs),
                f"{lang}: unsafe/inconsistent launch anchors")
        cover = urljoin(base, first["cover"])
        require(cover.startswith(base + "covers/"), f"{lang}: incorrect cover URL {cover}")
        if args.slug:
            require("/" + args.slug + "." in cover, f"{lang}: wrong cover file {cover}")
        if expected_cover is None:
            expected_cover = cover
        else:
            require(expected_cover == cover, f"{lang}: cover mismatch")
        if args.title:
            require(args.title in source and args.title in str(read_collection(source).get("itemListElement", [])[0]),
                    f"{lang}: title missing")
        data = read_collection(source)
        items = data.get("itemListElement", [])
        total = len(dom.cards)
        require(len(items) == total == data.get("numberOfItems"),
                f"{lang}: HTML={total}, JSON-LD={len(items)} / {data.get('numberOfItems')}")
        first_item = items[0].get("item", items[0])
        require(first_item.get("url") == args.game_url,
                f"{lang}: JSON-LD first game URL differs")
        require([item.get("position") for item in items] == list(range(1, total + 1)),
                f"{lang}: JSON-LD positions differ")
        if count is None:
            count = total
        require(count == total, f"{lang}: inconsistent number of games")
        print(f"OK {lang}: {total} cards, cover, 3 direct links and JSON-LD")

    fetch(expected_cover, args.rev, args.timeout, image=True)
    # Sitemap is XML, not image; fetch validates HTTP and content-type.
    sitemap = fetch(urljoin(base, "sitemap.xml"), args.rev, args.timeout)
    require("<urlset" in sitemap or "<sitemapindex" in sitemap, "Invalid sitemap")
    print(f"LIVE_VERIFIED: {count} games, 8 locales, cover HTTP 200, sitemap HTTP 200")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"NOT_LIVE_VERIFIED: {error}", file=sys.stderr)
        sys.exit(1)
