# Home

Source for [www.rupeshbhandari.com.np](https://www.rupeshbhandari.com.np): the home page, projects and about pages that point to the blog, tools, books and data sites. It's built by a small Python script and published to GitHub Pages on every push to `main`, and once a day so the latest posts stay current.

## Layout

```
content/
  projects.json   the project cards, by group; "featured": true also puts one under "Selected work" on the home page
  about.html      the About page's text ({{blog}} and {{books}} become the live counts)
  snapshot.json   counts, latest posts and popular tools to fall back on when a live site can't be reached
templates/        layout.html (head, sidebar, theme menu), one file per page, and the sidebar icons
static/           copied as-is: brand/ (fonts, images, palette, shared with tools. and books.), img/social-card.png, home.css, sw.min.js
scripts/
  build.py         builds site/: the pages, sitemap.xml, robots.txt, and the home page's JSON-LD (PERSON);
                   FEATURED_TOOLS picks the "Popular tools" cards by their id in the tools site's tools.json
  check_links.py   checks every internal link in site/ (--external also requests the outside ones)
  social-card.html source of the 1200×630 share image; the command to re-render it is at its top
```

Deploys check internal links only. `.github/workflows/links.yml` checks the outside ones every Monday; a failed run means a link has broken.

## Build and preview

```bash
python3 scripts/build.py && python3 -m http.server -d site 8000
```

Then open <http://localhost:8000>. The build reads the blog's feed and sitemap, the tools and books sitemaps and the data index for the numbers on the home page. Use `--offline` to skip that and use `content/snapshot.json`, or `--update-snapshot` to save what it read.

Before pushing:

```bash
python3 scripts/check_links.py --external
```

## sw.min.js

Until October 2026 this domain was the blog, whose theme cached pages in the browser with a service worker at `/sw.min.js`. This repo serves a replacement at the same address that clears those caches and unregisters itself, so returning visitors see this site instead of a cached copy of the blog. Leave it in place.
