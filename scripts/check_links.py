#!/usr/bin/env python3
"""Check every link in the built site. Internal links: the file must exist and any #anchor must
match an id on the target page. With --external, every outside link must also answer with a
2xx or 3xx status.

    python3 scripts/build.py && python3 scripts/check_links.py
    python3 scripts/check_links.py --external
"""

import argparse
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

SITE = Path(__file__).resolve().parent.parent / "site"
# Hosts that refuse every automated request (LinkedIn answers 999), so checking them only
# ever reports a false failure.
SKIP_HOSTS = {"www.linkedin.com"}


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids = [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        for key in ("href", "src"):
            if a.get(key) and tag in ("a", "link", "script", "img"):
                self.links.append(a[key])


def parse(path):
    page = Page()
    page.feed(path.read_text(encoding="utf-8"))
    return page


def target_file(page_path, link):
    """The file an internal link points at, resolved the way a static host would."""
    path = unquote(urlsplit(link).path)
    base = SITE if path.startswith("/") or page_path.name == "404.html" else page_path.parent
    target = (base / path.lstrip("/")).resolve() if path else page_path
    return target / "index.html" if target.is_dir() else target


def external_ok(url):
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "rupeshbhandari-home-links"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status < 400, response.status
    except Exception as err:
        return False, getattr(err, "code", err)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--external", action="store_true", help="also request every outside link")
    args = parser.parse_args()

    pages = {p: parse(p) for p in SITE.rglob("*.html")}
    problems, external = [], set()
    for path, page in pages.items():
        for link in page.links:
            parts = urlsplit(link)
            if parts.scheme in ("http", "https"):
                if parts.hostname not in SKIP_HOSTS:
                    external.add(link)
                continue
            if parts.scheme in ("mailto", "data") or link.startswith("#i-"):
                continue
            target = target_file(path, link)
            if not target.exists():
                problems.append(f"{path.relative_to(SITE)}: {link} -> missing {target.relative_to(SITE) if SITE in target.parents else target}")
            elif parts.fragment and target.suffix == ".html" and parts.fragment not in parse(target).ids:
                problems.append(f"{path.relative_to(SITE)}: {link} -> no #{parts.fragment}")
    if args.external:
        for url in sorted(external):
            ok, status = external_ok(url)
            if not ok:
                problems.append(f"external: {url} -> {status}")
    for p in problems:
        print(p)
    checked = f"{len(pages)} pages" + (f" and {len(external)} outside links" if args.external else "")
    print(f"{'FAIL' if problems else 'OK'}: checked {checked}, {len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
