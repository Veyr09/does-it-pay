"""Render an HTML or SVG deliverable and report what is actually wrong with it.

Written after three bounty deliverables in one night, every real defect in which was invisible
in the source and obvious in the render: captions bleeding into the next entry, a source
footer 120px past the right edge, rock strata drawn straight across open water, an anemone
floating above the floor it was supposed to be attached to.

    python tools/check_artifact.py submissions/thing.svg
    python tools/check_artifact.py submissions/thing.html --max-bytes 40000 --shot out.png
    python tools/check_artifact.py submissions/thing.svg --rows 108,220,5

Exits non-zero if a hard gate fails, so it can sit in front of a submission rather than beside
it. It cannot tell you whether the thing is beautiful; it can tell you it is not broken.
"""
import argparse
import itertools
import os
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

# Things that disqualify a self-contained deliverable outright in every brief seen so far.
FORBIDDEN_SVG = ('<script', 'foreignObject', '<image', 'data:image', 'xlink:href=\"http')
FORBIDDEN_HTML = ('setInterval(', 'requestAnimationFrame(', 'fetch(', 'localStorage',
                  'sessionStorage', 'XMLHttpRequest', '@keyframes', '<iframe', '<object')
# Namespace declarations are URLs but load nothing.
ALLOWED_URLS = ('http://www.w3.org/2000/svg', 'http://www.w3.org/1999/xlink',
                'http://www.w3.org/1999/xhtml')
SAFE_MARGIN = 6          # keep ink this far inside the stated canvas
DRIFT = 0.5              # bbox touching tolerance, in user units


def fail(msg):
    print(f'  FAIL  {msg}')
    return 1


def ok(msg):
    print(f'  ok    {msg}')
    return 0


def static_checks(path, max_bytes):
    raw = pathlib.Path(path).read_text(encoding='utf-8')
    size = pathlib.Path(path).stat().st_size
    bad = 0
    print(f'{path}')
    if max_bytes:
        bad += ok(f'{size:,} bytes of {max_bytes:,}') if size <= max_bytes else \
            fail(f'{size:,} bytes exceeds the {max_bytes:,} limit')
    else:
        print(f'  ....  {size:,} bytes')

    is_svg = path.lower().endswith('.svg')
    if is_svg:
        try:
            ET.fromstring(raw)
            bad += ok('XML parses')
        except ET.ParseError as e:
            bad += fail(f'XML does not parse: {e}')
        for tag in ('<title', '<desc'):
            bad += ok(f'{tag}> present') if tag in raw else fail(f'no {tag}> element')
        m = re.search(r'viewBox="([^"]+)"', raw)
        print(f'  ....  viewBox {m.group(1) if m else "MISSING"}')

    for token in (FORBIDDEN_SVG if is_svg else FORBIDDEN_HTML):
        if token in raw:
            bad += fail(f'contains {token}')
    urls = [u for u in re.findall(r'https?://[^\s"\'<>)]+', raw)
            if not u.startswith(ALLOWED_URLS)]
    external = re.findall(r'<(?:img|link|iframe|object|embed)[^>]*>|<script[^>]+src', raw)
    bad += ok('loads nothing external') if not external else \
        fail(f'external resource tags: {external[:3]}')
    if urls:
        print(f'  ....  {len(set(urls))} URL(s) in visible text (not fetched): '
              f'{sorted(set(urls))[:3]}')
    return bad, raw


def render_checks(path, canvas, rows, shot, viewport):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('  ....  playwright not installed; skipping render checks')
        return 0
    bad = 0
    uri = pathlib.Path(path).resolve().as_uri()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={'width': viewport[0], 'height': viewport[1]})
        pg.goto(uri)
        pg.wait_for_timeout(450)
        errors = []
        pg.on('pageerror', lambda e: errors.append(str(e)))
        # getBBox() reports an element's OWN user space, before any ancestor transform, so
        # anything inside a <g transform="translate(...)"> looks like it is off-canvas. Compare
        # client rectangles against the <svg>'s own rectangle instead: that is transform-aware
        # and puts every element in one space.
        boxes = pg.evaluate("""() => {
            const svg = document.querySelector('svg');
            if (!svg) return null;
            const r = svg.getBoundingClientRect();
            const vb = svg.viewBox.baseVal;
            const sx = vb && vb.width ? vb.width / r.width : 1;
            const sy = vb && vb.height ? vb.height / r.height : 1;
            const map = e => {
                const b = e.getBoundingClientRect();
                return {txt: (e.textContent || e.tagName).slice(0, 30),
                        x: (b.left - r.left) * sx, y: (b.top - r.top) * sy,
                        w: b.width * sx, h: b.height * sy};
            };
            // An element that is never rendered - anything inside <defs>, or a zero-size
            // node - returns an all-zero client rect, which maps to a large negative
            // coordinate here and looks exactly like something hanging off the canvas.
            const drawn = e => {
                if (e.closest('defs')) return false;
                const b = e.getBoundingClientRect();
                return b.width > 0 || b.height > 0;
            };
            const skip = ['defs','clipPath','title','desc','linearGradient','radialGradient',
                          'stop','svg','style','metadata'];
            return {texts: [...svg.querySelectorAll('text')].filter(drawn).map(map),
                    all: [...svg.querySelectorAll('*')]
                          .filter(e => e.getBoundingClientRect && !skip.includes(e.tagName)
                                  && drawn(e))
                          .map(map)};
        }""")
        if boxes is None:
            print('  ....  no inline <svg>; skipping geometry checks')
        else:
            texts, every = boxes['texts'], boxes['all']
            W, H = canvas
            out = [t for t in texts
                   if t['x'] < -SAFE_MARGIN or t['y'] < -SAFE_MARGIN
                   or t['x'] + t['w'] > W + SAFE_MARGIN or t['y'] + t['h'] > H + SAFE_MARGIN]
            bad += ok(f'{len(texts)} text elements, all inside {W}x{H}') if not out else                 fail(f'{len(out)} text element(s) outside the canvas: '
                     f'{[t["txt"] for t in out[:3]]}')
            overlaps = []
            for a, c in itertools.combinations(texts, 2):
                if (a['x'] < c['x'] + c['w'] - DRIFT and c['x'] < a['x'] + a['w'] - DRIFT
                        and a['y'] < c['y'] + c['h'] - DRIFT
                        and c['y'] < a['y'] + a['h'] - DRIFT):
                    overlaps.append((a['txt'], c['txt']))
            if overlaps:
                print(f'  ....  {len(overlaps)} overlapping text pair(s) - check whether these '
                      f'are headings against their own subtitles: {overlaps[:3]}')
            if rows:
                top, height, count = rows
                crossing = [t['txt'] for i in range(count) for t in texts
                            if top + i * height <= t['y'] < top + (i + 1) * height - 10
                            and t['y'] + t['h'] > top + (i + 1) * height - 10]
                bad += ok('no text crosses its row band') if not crossing else                     fail(f'text crossing into the next row: {crossing[:3]}')
            spill = [e for e in every
                     if e['x'] < -SAFE_MARGIN or e['y'] < -SAFE_MARGIN
                     or e['x'] + e['w'] > W + SAFE_MARGIN or e['y'] + e['h'] > H + SAFE_MARGIN]
            bad += ok(f'all {len(every)} graphics inside the viewBox') if not spill else                 fail(f'{len(spill)} graphic element(s) outside the viewBox: '
                     f'{[e["txt"] for e in spill[:3]]}')

        if path.lower().endswith('.html'):
            pg.set_viewport_size({'width': 360, 'height': 800})
            pg.wait_for_timeout(200)
            w = pg.evaluate('() => [document.documentElement.scrollWidth, window.innerWidth]')
            bad += ok('no horizontal scroll at 360px') if w[0] <= w[1] else \
                fail(f'horizontal scroll at 360px: {w[0]} > {w[1]}')
            pg.set_viewport_size({'width': viewport[0], 'height': viewport[1]})
        bad += ok('no page errors') if not errors else fail(f'page errors: {errors[:2]}')

        if shot:
            pg.wait_for_timeout(200)
            pg.screenshot(path=shot, clip={'x': 0, 'y': 0,
                                           'width': min(canvas[0], viewport[0]),
                                           'height': min(canvas[1], viewport[1])})
            print(f'  ....  screenshot {shot} - now actually look at it')
        b.close()
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('path')
    ap.add_argument('--max-bytes', type=int, default=0)
    ap.add_argument('--canvas', default='', help='WxH of the stated viewBox, e.g. 1000x1500')
    ap.add_argument('--rows', default='', help='top,height,count for per-row containment')
    ap.add_argument('--shot', default='')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    bad, raw = static_checks(args.path, args.max_bytes)
    if args.canvas:
        canvas = tuple(int(v) for v in args.canvas.lower().split('x'))
    else:
        m = re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"', raw)
        canvas = (int(float(m.group(1))), int(float(m.group(2)))) if m else (1000, 1000)
    rows = tuple(int(v) for v in args.rows.split(',')) if args.rows else None
    viewport = (max(320, min(canvas[0], 1600)), max(320, min(canvas[1], 2000)))
    bad += render_checks(args.path, canvas, rows, args.shot, viewport)

    print(f'\n{"PASS" if not bad else str(bad) + " HARD FAILURE(S)"}')
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
