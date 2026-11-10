#!/usr/bin/env python3
"""Build www.rupeshbhandari.com.np into site/.

Renders the home, projects, about and 404 pages from templates/ and content/, copies static/
(brand fonts and images, the stylesheet, the service worker), and writes sitemap.xml and
robots.txt.

The counts on the home page (blog posts, tools, books, datasets) and the latest blog posts are
read from the live sites. When one can't be reached, the value saved in content/snapshot.json
is used instead and the build says so, so a network hiccup never stops a deploy.

    python3 scripts/build.py                     # live counts and posts, snapshot as fallback
    python3 scripts/build.py --offline           # snapshot only
    python3 scripts/build.py --update-snapshot   # also save what was fetched into the snapshot
"""

import argparse
import html
import json
import re
import shutil
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
TEMPLATES = ROOT / "templates"
CONTENT = ROOT / "content"
STATIC = ROOT / "static"
SITE_URL = "https://www.rupeshbhandari.com.np/"
BLOG_URL = "https://blog.rupeshbhandari.com.np/"
TOOLS_URL = "https://tools.rupeshbhandari.com.np/"
BOOKS_URL = "https://books.rupeshbhandari.com.np/"
DATA_URL = "https://data.rupeshbhandari.com.np/"
LATEST_POSTS = 5
ATOM = "{http://www.w3.org/2005/Atom}"

# The four cards under "Everything I publish".
SITES = [
    {"key": "blog", "name": "Blog", "url": BLOG_URL, "unit": ("post", "posts"),
     "description": "Business Central how-tos, Python, finance and the odd essay."},
    {"key": "tools", "name": "Tools", "url": TOOLS_URL, "unit": ("tool", "tools"),
     "description": "Small browser tools for developers, PDFs, finance, networks and Business Central."},
    {"key": "books", "name": "Books", "url": BOOKS_URL, "unit": ("book", "books"),
     "description": "Programming books, free to read online: the Programming for All series and a regular expressions guide."},
    {"key": "data", "name": "Data", "url": DATA_URL, "unit": ("dataset", "datasets"),
     "description": "Nepal's income tax slabs, TDS, VAT, depreciation pools and NEPSE charges as JSON."},
]

# The "Popular tools" cards on the home page, in order, by their id in the tools site's tools.json.
# Names and descriptions come from there, so they match the tools site.
FEATURED_TOOLS = [
    "nepal-salary-tax",
    "vat-tds-calculator",
    "nepse-share-calculator",
    "ad-bs-date-converter",
    "merge-pdf",
    "bc-odata-url-builder",
]

# path in site/, template, <title>, description, which nav link is current
PAGES = [
    ("index.html", "home", "Rupesh Bhandari",
     "Functional Consultant by profession, coder by habit: the blog, tools, books, data and projects of Rupesh Bhandari.", "home"),
    ("projects/index.html", "projects", "Projects · Rupesh Bhandari",
     "Business Central extensions, Nepal tax data and Python projects by Rupesh Bhandari.", "projects"),
    ("about/index.html", "about", "About · Rupesh Bhandari",
     "Rupesh Bhandari: an ACCA-qualified Business Central functional consultant who writes about Business Central, Python and Nepal's tax rules.", "about"),
    ("404.html", "404", "Page not found · Rupesh Bhandari", "This page doesn't exist.", None),
]

# Structured data for search engines, on the home page only: who the site belongs to and the
# profiles that are also him, so they can be tied together.
PERSON = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "Person",
            "@id": SITE_URL + "#person",
            "name": "Rupesh Bhandari",
            "url": SITE_URL,
            "image": SITE_URL + "brand/img/rb-180.png",
            "jobTitle": "Business Central Functional Consultant",
            "description": "ACCA-qualified Microsoft Dynamics 365 Business Central functional consultant who writes about Business Central, Python and Nepal's tax rules.",
            "address": {"@type": "PostalAddress", "addressLocality": "Kathmandu", "addressCountry": "NP"},
            "knowsAbout": ["Microsoft Dynamics 365 Business Central", "AL", "Python", "Accounting", "Nepal taxation"],
            "sameAs": [
                "https://github.com/rpshbhandari",
                "https://www.linkedin.com/in/rpshbhandari",
                "https://twitter.com/rpshbhandari",
                BLOG_URL, TOOLS_URL, BOOKS_URL, DATA_URL,
            ],
        },
        {
            "@type": "WebSite",
            "@id": SITE_URL + "#website",
            "name": "Rupesh Bhandari",
            "url": SITE_URL,
            "publisher": {"@id": SITE_URL + "#person"},
        },
    ],
}


def esc(text):
    return html.escape(str(text), quote=True)


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "rupeshbhandari-home-build"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read()


def sitemap_urls(url):
    return sorted(set(re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", fetch(url).decode("utf-8"))))


def count_blog():
    return sum("/posts/" in u for u in sitemap_urls(BLOG_URL + "sitemap.xml"))


def count_tools():
    return sum(u.rstrip("/") != TOOLS_URL.rstrip("/") for u in sitemap_urls(TOOLS_URL + "sitemap.xml"))


def count_books():
    # Each book is a top-level folder: books.rupeshbhandari.com.np/<book>/...
    return len({u.split("/")[3] for u in sitemap_urls(BOOKS_URL + "sitemap.xml") if u.count("/") > 3 and u.split("/")[3]})


def count_data():
    index = json.loads(fetch(DATA_URL + "v1/index.json"))
    return len({f["dataset"] for f in index["files"]})


def latest_posts():
    feed = ET.fromstring(fetch(BLOG_URL + "feed.xml"))
    posts = []
    for entry in feed.findall(ATOM + "entry")[:LATEST_POSTS]:
        posts.append({
            "title": entry.findtext(ATOM + "title").strip(),
            "url": entry.find(ATOM + "link").get("href"),
            "date": entry.findtext(ATOM + "published")[:10],
            "categories": [c.get("term") for c in entry.findall(ATOM + "category")][:2],
        })
    return posts


def featured_tools():
    catalogue = json.loads(fetch(TOOLS_URL + "tools.json"))
    categories = {c["id"]: c["name"] for c in catalogue["categories"]}
    by_id = {t["id"]: t for t in catalogue["tools"]}
    missing = [i for i in FEATURED_TOOLS if i not in by_id]
    if missing:
        raise ValueError(f"not in tools.json: {', '.join(missing)}")
    return [{
        "name": by_id[i]["name"],
        "description": by_id[i]["description"],
        "category": categories.get(by_id[i]["category"], by_id[i]["category"]),
        "url": TOOLS_URL + by_id[i]["url"],
    } for i in FEATURED_TOOLS]


def gather(snapshot, offline):
    """Return (counts, posts, tools, notes): live values where reachable, the snapshot's otherwise."""
    counts, notes = dict(snapshot["counts"]), []
    sources = {"blog": count_blog, "tools": count_tools, "books": count_books, "data": count_data}
    for key, read in sources.items():
        if offline:
            continue
        try:
            value = read()
            if value <= 0:
                raise ValueError("counted nothing")
            counts[key] = value
        except Exception as err:  # any network or parse failure falls back to the snapshot
            notes.append(f"{key} count: using snapshot ({counts[key]}): {err}")
    posts = snapshot["posts"]
    if not offline:
        try:
            fetched = latest_posts()
            if not fetched:
                raise ValueError("feed has no entries")
            posts = fetched
        except Exception as err:
            notes.append(f"latest posts: using snapshot: {err}")
    tools = snapshot.get("tools", [])
    if not offline:
        try:
            tools = featured_tools()
        except Exception as err:
            notes.append(f"popular tools: using snapshot: {err}")
    if offline:
        notes.append("offline: every value comes from the snapshot")
    return counts, posts, tools, notes


def render(template, values):
    out = template
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", value)
    left = sorted(set(re.findall(r"\{\{\w+\}\}", out)))
    if left:
        sys.exit(f"Unfilled placeholders: {', '.join(left)}")
    return out


def site_card(site, count):
    singular, plural = site["unit"]
    host = site["url"].split("//")[1].rstrip("/")
    return f"""
            <li><a class="card site" href="{esc(site['url'])}">
              <div class="card-top"><span class="ic"><svg aria-hidden="true"><use href="#i-{site['key']}"/></svg></span><span class="tab">{count} {singular if count == 1 else plural}</span></div>
              <h3>{esc(site['name'])}</h3><p>{esc(site['description'])}</p>
              <span class="host">{esc(host)}</span></a></li>"""


def post_row(post):
    day = date.fromisoformat(post["date"])
    return f"""
            <li><a href="{esc(post['url'])}"><span class="pd tab">{day.day} {day.strftime('%b %Y')}</span><span class="pt">{esc(post['title'])}</span><span class="pc">{esc(' · '.join(post['categories']))}</span></a></li>"""


def tool_card(tool):
    return f"""
            <li><a class="card tool" href="{esc(tool['url'])}"><div class="card-top"><span>{esc(tool['category'])}</span></div><h3>{esc(tool['name'])}</h3><p>{esc(tool['description'])}</p></a></li>"""


def project_card(item):
    tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in item.get("tags", []))
    tags = f'<div class="tags">{tags}</div>' if tags else ""
    return f"""
            <li><a class="card" href="{esc(item['url'])}"><div class="card-top"><span>{esc(item['kind'])}</span><span>{esc(item['meta'])}</span></div><h3>{esc(item['name'])}</h3><p>{esc(item['description'])}</p>{tags}</a></li>"""


def project_group(group):
    head = f'<h2 id="h-{group["id"]}">{esc(group["title"])}</h2>'
    if "more" in group:
        more = group["more"]
        head = f'<div class="section-head">{head}<a class="more" href="{esc(more["url"])}">{esc(more["label"])} →</a></div>'
    intro = f'\n          <p class="group-sub">{esc(group["intro"])}</p>' if group.get("intro") else ""
    cards = "".join(project_card(i) for i in group["items"])
    return f"""
        <section class="group" aria-labelledby="h-{group['id']}">
          {head}{intro}
          <ul class="grid">{cards}
          </ul>
        </section>"""


def write_sitemap():
    urls = [SITE_URL, SITE_URL + "projects/", SITE_URL + "about/"]
    entries = "".join(f"\n  <url><loc>{url}</loc></url>" for url in urls)
    (SITE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{entries}\n</urlset>\n',
        encoding="utf-8",
    )
    (SITE / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--offline", action="store_true", help="don't fetch; use content/snapshot.json only")
    parser.add_argument("--update-snapshot", action="store_true", help="save fetched counts and posts into the snapshot")
    args = parser.parse_args()

    snapshot_path = CONTENT / "snapshot.json"
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    projects = json.loads((CONTENT / "projects.json").read_text(encoding="utf-8"))
    counts, posts, tools, notes = gather(snapshot, args.offline)

    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(STATIC, SITE)

    items = [i for g in projects["groups"] for i in g["items"]]
    layout = (TEMPLATES / "layout.html").read_text(encoding="utf-8")
    icons = (TEMPLATES / "icons.html").read_text(encoding="utf-8").strip()
    about = render((CONTENT / "about.html").read_text(encoding="utf-8").split("-->", 1)[-1].strip(),
                   {"blog": str(counts["blog"]), "books": str(counts["books"])})

    # "</" can't appear inside a <script>, so escape it the way JSON allows.
    person = json.dumps(PERSON, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    jsonld = f'\n  <script type="application/ld+json">{person}</script>'

    for path, name, title, description, current in PAGES:
        depth = path.count("/")
        root = "/" if name == "404" else "../" * depth  # 404.html is served at any path, so it uses absolute URLs
        body = render((TEMPLATES / f"{name}.html").read_text(encoding="utf-8"), {
            "root": root,
            "count_blog": str(counts["blog"]),
            "count_tools": str(counts["tools"]),
            "tools": "".join(tool_card(t) for t in tools),
            "sites": "".join(site_card(s, counts[s["key"]]) for s in SITES),
            "posts": "".join(post_row(p) for p in posts),
            "selected": "".join(project_card(i) for i in items if i.get("featured")),
            "groups": "".join(project_group(g) for g in projects["groups"]),
            "about": about,
        })
        page = render(layout, {
            "title": esc(title),
            "description": esc(description),
            "canonical": SITE_URL + (path[: -len("index.html")] if path.endswith("index.html") else path),
            "root": root,
            "home": root or "./",
            "icons": icons,
            "jsonld": jsonld if name == "home" else "",
            "project_count": str(len(items)),
            "current_home": ' aria-current="page"' if current == "home" else "",
            "current_projects": ' aria-current="page"' if current == "projects" else "",
            "current_about": ' aria-current="page"' if current == "about" else "",
            "main": body.rstrip("\n"),
        })
        out = SITE / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")
    write_sitemap()

    if args.update_snapshot:
        snapshot.update({"updated": date.today().isoformat(), "counts": counts, "posts": posts, "tools": tools})
        snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Saved counts, posts and tools into {snapshot_path.relative_to(ROOT)}")

    for note in notes:
        print(f"note: {note}")
    shown = ", ".join(f"{counts[s['key']]} {s['unit'][1]}" for s in SITES)
    print(f"Built {len(PAGES)} pages into {SITE.relative_to(ROOT)}/ ({shown}; {len(posts)} latest posts; {len(tools)} popular tools; {len(items)} projects)")


if __name__ == "__main__":
    main()
