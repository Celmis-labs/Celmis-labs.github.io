#!/usr/bin/env python3
"""Render the documentation that lives in the Celmis repository into pages of this site.

The markdown in the product repository stays the single source of truth: nothing here
is hand-written prose. Run this after the docs change, then commit the result.

    python3 build.py [--source ../Celmis]
"""
import argparse
import datetime
import html
import pathlib
import re
import shutil
import sys

try:
    from markdown_it import MarkdownIt
except ImportError:
    sys.exit("markdown-it-py is required:  pip3 install markdown-it-py")

REPO = "https://github.com/Celmis-labs/Celmis"
SITE = "https://celmis-labs.github.io"

# Only English sources are published: the site is English for now, and three of the
# operational runbooks (deployment, Hetzner, Railway) are written in Ukrainian.
PAGES = [
    dict(slug="guide", src="README.md", title="Guide",
         blurb="What Celmis is, what it does, and how to run it — the complete "
               "documentation, from a first install to the architecture.",
         note="the full product documentation"),
    dict(slug="litellm", src="docs/LITELLM_GATEWAY.md", title="LiteLLM gateway",
         blurb="Put a single exit door in front of every model provider, so the "
               "application never holds a tenant's real provider key on the call path.",
         note="operator runbook"),
    dict(slug="oracle-ci", src="docs/ORACLE_CICD.md", title="Free CI/CD on Oracle",
         blurb="Push to main, and GitHub Actions builds and restarts the stack on an "
               "Oracle Always Free ARM box over SSH — inside the free minutes.",
         note="deployment"),
    dict(slug="backup", src="docs/BACKUP_RESTORE.md", title="Backup and restore",
         blurb="What each store holds, how to take a consistent copy of it, and how to "
               "put it back.",
         note="runbook"),
    dict(slug="key-rotation", src="docs/KEY_ROTATION.md", title="JWT key rotation",
         blurb="Rotate the session and MCP signing secrets with no downtime, using a "
               "dual-secret window.",
         note="runbook"),
]


# Pieces written for this site, rendered into /writing/<slug>/. Unlike the documentation
# these are not mirrors of anything — the site is where they live, which is what lets a
# syndicated copy elsewhere point its canonical URL back here.
WRITING = [
    dict(slug="mcp", path="mcp", src="content/mcp.md",
         title="MCP server",
         blurb="Eighteen tools over the same index, under the same access rules — for "
               "Claude Code, Cursor, and any other MCP client.",
         date="2026-08-28"),
    dict(slug="one-question-two-repositories",
         src="content/one-question-two-repositories.md",
         title="Introducing Celmis",
         blurb="Self-hosted code intelligence over a symbol graph: what it does, what it "
               "refuses to claim, and how to run it on one machine.",
         date="2026-08-27"),
    dict(slug="remembering-the-conversation-is-not-knowing-the-code",
         src="content/remembering-the-conversation-is-not-knowing-the-code.md",
         title="A memory server remembers your conversation. That is not the same as "
               "knowing your code.",
         blurb="MCP has no memory primitive, and the July 2026 revision deprecated two of "
               "its three client features. Conversation is personal, stated and durable; "
               "code knowledge is shared, derived and perishable. Same word, opposite "
               "requirements.",
         date="2026-09-01"),
    dict(slug="documentation-that-goes-stale-loudly",
         src="content/documentation-that-goes-stale-loudly.md",
         title="The wiki cannot fail. That is what is wrong with it.",
         blurb="Documentation with no build has no failure mode: it decays into a "
               "confident wrong answer that reads exactly like a right one. What an "
               "artefact with a provenance record does instead.",
         date="2026-09-01"),
]


def slugify(text: str) -> str:
    """Match GitHub's heading anchors, so in-document links keep working."""
    s = re.sub(r"<[^>]+>", "", text).strip().lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    return re.sub(r"[\s_]+", "-", s).strip("-")


def rewrite_links(body: str) -> str:
    """Images come from this site; every other repository path goes back to GitHub."""
    body = re.sub(r'src="docs/images/([^"]+)"', r'src="/img/\1"', body)
    body = re.sub(r'src="images/([^"]+)"', r'src="/img/\1"', body)

    def fix(m):
        href = m.group(1)
        if href.startswith(("http://", "https://", "#", "mailto:", "/")):
            return m.group(0)
        target = href.lstrip("./")
        while target.startswith("../"):
            target = target[3:]
        return 'href="%s/blob/main/%s"' % (REPO, target)

    return re.sub(r'href="([^"]+)"', fix, body)


def decorate(body: str):
    """Add heading ids and hover anchors, collect a contents list, make tables scroll."""
    toc = []
    seen = {}

    def heading(m):
        level, attrs, text = m.group(1), m.group(2), m.group(3)
        base = slugify(text) or "section"
        seen[base] = seen.get(base, 0) + 1
        hid = base if seen[base] == 1 else "%s-%d" % (base, seen[base] - 1)
        if level in ("2", "3"):
            toc.append((level, hid, re.sub(r"<[^>]+>", "", text)))
        anchor = '<a class="anchor" href="#%s" aria-label="Link to this section">#</a>' % hid
        return '<h%s id="%s"%s>%s%s</h%s>' % (level, hid, attrs, anchor, text, level)

    body = re.sub(r"<h([2-4])([^>]*)>(.*?)</h\1>", heading, body, flags=re.S)
    body = body.replace("<table>", '<div class="tablewrap"><table>')
    body = body.replace("</table>", "</table></div>")
    return body, toc


def drop_section(md_text: str, heading: str) -> str:
    """Remove a whole `## heading` block. The sidebar already lists the contents, so the
    document's own table of contents would only repeat it."""
    lines = md_text.split("\n")
    out, skipping = [], False
    for line in lines:
        if line.startswith("## "):
            skipping = slugify(line[3:]) == slugify(heading)
            if skipping:
                continue
        elif skipping and line.startswith("#"):
            skipping = False
        if not skipping:
            out.append(line)
    return "\n".join(out)


def first_paragraph(md_text: str) -> str:
    for block in md_text.split("\n\n"):
        b = block.strip()
        if b and not b.startswith(("#", "|", "`", "<", ">", "-", "*", "!")):
            return re.sub(r"\s+", " ", re.sub(r"[*_`\[\]]", "", b))[:300]
    return ""


NAV = """<header class="bar" id="bar">
  <div class="wrap">
    <a class="mark" href="/"><span class="core"><i></i></span>celmis</a>
    <nav>
      <a href="/docs/">Docs</a>
      <a href="/#uses" class="opt">Uses</a>
      <a href="/#start">Install</a>
      <a href="%s">GitHub</a>
      <button class="tog" id="tog" type="button" aria-label="Switch colour theme">
        <svg class="sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.6v2.3M12 19.1v2.3M21.4 12h-2.3M4.9 12H2.6M18.7 5.3l-1.6 1.6M6.9 17.1l-1.6 1.6M18.7 18.7l-1.6-1.6M6.9 6.9L5.3 5.3"/></svg>
        <svg class="moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20.5 14.4A8.6 8.6 0 1 1 9.6 3.5a6.9 6.9 0 0 0 10.9 10.9z"/></svg>
      </button>
    </nav>
  </div>
</header>""" % REPO

FOOT = """<footer>
  <div class="wrap fgrid">
    <div>
      <p><strong>Celmis</strong> is free software under the GNU Affero General Public
        License v3.0, with one exception noted in the licence file. If you run it for
        others over a network, they are entitled to its source.</p>
      <p style="margin:0">Built by <a href="https://github.com/Celmis-labs">Celmis Labs</a>.</p>
    </div>
    <nav>
      <a href="/docs/">Documentation</a>
      <a href="%s">Source</a>
      <a href="%s#results">Benchmark results</a>
      <a href="%s/blob/main/LICENSE">Licence</a>
    </nav>
  </div>
</footer>""" % (REPO, REPO, REPO)

THEME_JS = """<script>
(function(){var r=document.documentElement;
try{var v=localStorage.getItem('celmis-theme');if(v==='dark'||v==='light')r.setAttribute('data-theme',v);}catch(e){}
function dark(){var a=r.getAttribute('data-theme');return a?a==='dark':matchMedia('(prefers-color-scheme: dark)').matches;}
var t=document.getElementById('tog');
if(t)t.addEventListener('click',function(){var n=dark()?'light':'dark';r.setAttribute('data-theme',n);
try{localStorage.setItem('celmis-theme',n);}catch(e){}});
var b=document.getElementById('bar');
function s(){b.classList.toggle('stuck',scrollY>8);}s();addEventListener('scroll',s,{passive:true});
/* mark the contents entry for the section being read */
var links=[].slice.call(document.querySelectorAll('.toc a'));
if(links.length&&'IntersectionObserver'in window){
 var map={};
 links.forEach(function(a){var el=document.getElementById(decodeURIComponent(a.hash.slice(1)));
  if(el)map[el.id]=a;});
 var io=new IntersectionObserver(function(es){es.forEach(function(e){
  if(!e.isIntersecting)return;
  links.forEach(function(a){a.classList.remove('on');});
  var a=map[e.target.id];if(a)a.classList.add('on');});},
  {rootMargin:'-70px 0px -72% 0px',threshold:0});
 Object.keys(map).forEach(function(id){var el=document.getElementById(id);if(el)io.observe(el);});
}
})();
</script>"""


def shell(title, desc, canonical, head_extra, body):
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<meta name="theme-color" content="#FBFCFB" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#080A09" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="https://celmis-labs.github.io/img/og-celmis-2.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://celmis-labs.github.io/img/og-celmis-2.png">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='7' fill='%230B0F0D'/><circle cx='16' cy='16' r='4.5' fill='%233DBE83'/><circle cx='16' cy='16' r='9.5' fill='none' stroke='%233DBE83' stroke-opacity='.4' stroke-width='1.6'/></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@75..125,400..700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<link rel="stylesheet" href="/assets/site.css">
{head_extra}
</head>
<body>
{nav}
{body}
{foot}
{js}
</body>
</html>
""".format(title=html.escape(title), desc=html.escape(desc), canonical=canonical,
           head_extra=head_extra, nav=NAV, body=body, foot=FOOT, js=THEME_JS)


def copy_images(src_root: pathlib.Path, out_root: pathlib.Path) -> None:
    """Bring every referenced picture across, and say what is missing.

    `rewrite_links` turns `docs/images/x.png` into `/img/x.png` and NOTHING
    copied the file. So a screenshot added to the product repository rendered
    as a broken image here until somebody remembered to copy it by hand, and
    for `alert-to-fix.png` nobody did: the guide page has been serving a 404
    in the middle of the alerts section. It was not visible in the build log,
    because the build never looked.

    The listing is printed either way. A silent copy is how the last one went
    unnoticed for as long as it did.
    """
    src_dir = src_root / "docs" / "images"
    out_dir = out_root / "img"
    if not src_dir.is_dir():
        print("  no docs/images in the source tree — nothing to copy")
        return
    out_dir.mkdir(exist_ok=True)

    wanted = set()
    for page in PAGES:
        src = src_root / page["src"]
        if src.exists():
            wanted |= set(re.findall(r"\]\((?:docs/)?images/([^)]+)\)",
                                    src.read_text(encoding="utf-8")))

    copied, missing = [], []
    for name in sorted(wanted):
        origin = src_dir / name
        if not origin.is_file():
            missing.append(name)
            continue
        target = out_dir / name
        if not target.exists() or target.read_bytes() != origin.read_bytes():
            shutil.copy2(origin, target)
            copied.append(name)

    orphans = sorted(p.name for p in out_dir.iterdir()
                     if p.is_file() and p.name not in wanted
                     and p.name.startswith(("agent-", "alert-", "ask-", "compliance-",
                                            "first-", "mcp-", "pr-", "project-",
                                            "session-", "fix-")))
    print(f"  images: {len(wanted)} referenced, {len(copied)} copied")
    for name in copied:
        print(f"    + {name}")
    for name in orphans:
        print(f"    orphan in img/ (nothing references it): {name}")
    if missing:
        raise SystemExit(
            "  MISSING, and the page would serve a 404 for each:\n    "
            + "\n    ".join(missing))


def build():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(pathlib.Path.home() / "Desktop" / "Celmis"))
    args = ap.parse_args()
    src_root = pathlib.Path(args.source)
    out_root = pathlib.Path(__file__).parent

    copy_images(src_root, out_root)

    md = MarkdownIt("commonmark", {"html": True, "linkify": False})
    md.enable("table").enable("strikethrough")

    built = []
    for i, page in enumerate(PAGES):
        src = src_root / page["src"]
        if not src.exists():
            print("  missing, skipped:", src)
            continue
        text = drop_section(src.read_text(), "Table of contents")
        body, toc = decorate(rewrite_links(md.render(text)))
        desc = page["blurb"]

        toc_html = ""
        if len(toc) > 2:
            items = "".join(
                '<li><a class="%s" href="#%s">%s</a></li>'
                % ("lvl3" if lvl == "3" else "lvl2", hid, html.escape(txt))
                for lvl, hid, txt in toc)
            toc_html = ('<aside class="toc"><span class="k">On this page</span>'
                        '<ol>%s</ol></aside>' % items)

        prev_page = PAGES[i - 1] if i else None
        next_page = PAGES[i + 1] if i + 1 < len(PAGES) else None
        nav_bits = []
        if prev_page:
            nav_bits.append('<a href="/docs/%s/">← %s</a>' % (prev_page["slug"], html.escape(prev_page["title"])))
        else:
            nav_bits.append('<a href="/docs/">← All documentation</a>')
        if next_page:
            nav_bits.append('<a href="/docs/%s/">%s →</a>' % (next_page["slug"], html.escape(next_page["title"])))

        canonical = "%s/docs/%s/" % (SITE, page["slug"])
        ld = ('<script type="application/ld+json">{"@context":"https://schema.org",'
              '"@type":"TechArticle","headline":%s,"description":%s,"url":%s,'
              '"inLanguage":"en","isPartOf":{"@type":"WebSite","name":"Celmis","url":"%s/"},'
              '"publisher":{"@type":"Organization","name":"Celmis Labs","url":"%s/"},'
              '"license":"https://www.gnu.org/licenses/agpl-3.0.html"}</script>'
              % (_json(page["title"] + " — Celmis"), _json(desc), _json(canonical), SITE, SITE))

        content = """<main class="wrap">
  <div class="dochead">
    <p class="crumbs"><a href="/">Celmis</a><span>/</span><a href="/docs/">Docs</a><span>/</span>{title}</p>
    <h1 class="docttl">{title}</h1>
    <p class="docsub">{blurb}</p>
    <p class="docmeta"><span>{note}</span><span>source: <a href="{repo}/blob/main/{src}">{src}</a></span></p>
  </div>
  <div class="doclayout">
    <article class="prose">
{body}
      <div class="docnav">{navbits}</div>
    </article>
    {toc}
  </div>
</main>""".format(title=html.escape(page["title"]), blurb=html.escape(page["blurb"]),
                  note=html.escape(page["note"]), repo=REPO, src=page["src"],
                  body=body, navbits="".join(nav_bits), toc=toc_html)

        out = out_root / "docs" / page["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(shell(page["title"] + " — Celmis", desc, canonical, ld, content))
        built.append((page, len(body)))
        print("  %-14s %6d bytes  %2d headings" % (page["slug"], len(body), len(toc)))

    # pieces written for this site
    for w in WRITING:
        src = out_root / w["src"]
        if not src.exists():
            print("  missing, skipped:", src)
            continue
        body, toc = decorate(rewrite_links(md.render(src.read_text())))
        seg = w.get("path") or ("writing/" + w["slug"])
        canonical = "%s/%s/" % (SITE, seg)
        toc_html = ""
        if len(toc) > 2:
            items = "".join(
                '<li><a class="%s" href="#%s">%s</a></li>'
                % ("lvl3" if lvl == "3" else "lvl2", hid, html.escape(txt))
                for lvl, hid, txt in toc)
            toc_html = ('<aside class="toc"><span class="k">On this page</span>'
                        '<ol>%s</ol></aside>' % items)
        ld = ('<script type="application/ld+json">{"@context":"https://schema.org",'
              '"@type":"Article","headline":%s,"description":%s,"url":%s,'
              '"datePublished":%s,"dateModified":%s,"inLanguage":"en",'
              '"author":{"@type":"Organization","name":"Celmis Labs"},'
              '"publisher":{"@type":"Organization","name":"Celmis Labs","url":"%s/"}}</script>'
              % (_json(w["title"]), _json(w["blurb"]), _json(canonical),
                 _json(w["date"]), _json(w["date"]), SITE))
        content = """<main class="wrap">
  <div class="dochead">
    <p class="crumbs"><a href="/">Celmis</a><span>/</span>Writing</p>
    <h1 class="docttl">{title}</h1>
    <p class="docsub">{blurb}</p>
    <p class="docmeta"><span>{date}</span></p>
  </div>
  <div class="doclayout">
    <article class="prose">
{body}
      <div class="docnav"><a href="/">← Celmis</a><a href="/docs/">Documentation →</a></div>
    </article>
    {toc}
  </div>
</main>""".format(title=html.escape(w["title"]), blurb=html.escape(w["blurb"]),
                  date=w["date"], body=body, toc=toc_html)
        page = out_root.joinpath(*seg.split("/")) / "index.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(shell(w["title"] + " — Celmis", w["blurb"], canonical, ld, content))
        print("  %-40s %6d bytes" % (seg, len(body)))

    cards = "".join(
        '<li><a href="/docs/{slug}/"><span class="t">{title} <span class="arw">→</span></span>'
        '<p>{blurb}</p><span class="n">{note}</span></a></li>'.format(
            slug=p["slug"], title=html.escape(p["title"]),
            blurb=html.escape(p["blurb"]), note=html.escape(p["note"]))
        for p, _ in built)

    index_body = """<main class="wrap">
  <div class="dochead">
    <p class="crumbs"><a href="/">Celmis</a><span>/</span>Docs</p>
    <h1 class="docttl">Documentation</h1>
    <p class="docsub">Every page here is generated from the markdown in the
      <a href="{repo}">product repository</a>, so it cannot drift from the code it
      describes. Start with the guide.</p>
  </div>
  <section style="border-top:0;padding-top:0">
    <ul class="doccards">{cards}</ul>
    <p class="small dim" style="margin-top:34px;max-width:66ch">Three further runbooks —
      deployment and testing, Hetzner, and Railway — are written in Ukrainian and live in
      <a href="{repo}/tree/main/docs">the repository</a> until they are translated.</p>
  </section>
</main>""".format(repo=REPO, cards=cards)

    ld_index = ('<script type="application/ld+json">{"@context":"https://schema.org",'
                '"@type":"CollectionPage","name":"Celmis documentation",'
                '"url":"%s/docs/","inLanguage":"en",'
                '"publisher":{"@type":"Organization","name":"Celmis Labs","url":"%s/"}}</script>'
                % (SITE, SITE))
    (out_root / "docs").mkdir(exist_ok=True)
    (out_root / "docs" / "index.html").write_text(shell(
        "Documentation — Celmis",
        "Complete Celmis documentation: the guide, the LiteLLM gateway runbook, free "
        "CI/CD on Oracle, backup and restore, and JWT key rotation.",
        SITE + "/docs/", ld_index, index_body))

    urls = [("%s/" % SITE, "1.0"), ("%s/docs/" % SITE, "0.9")]
    urls += [("%s/docs/%s/" % (SITE, p["slug"]), "0.8") for p, _ in built]
    # hand-written pages, plus anything one level under writing/
    root = pathlib.Path(__file__).parent
    urls += [("%s/%s/" % (SITE, d.name), "0.9")
             for d in sorted(root.iterdir())
             if d.is_dir() and not d.name.startswith((".", "_"))
             and d.name not in ("docs", "img", "assets", "content", "writing")
             and (d / "index.html").exists()]
    # the writing index itself, now that it exists — it was 404 while the articles
    # under it were 200, which broke the one path a reader trims a URL to
    if (root / "writing" / "index.html").exists():
        urls.append(("%s/writing/" % SITE, "0.9"))
    urls += [("%s/writing/%s/" % (SITE, d.name), "0.9")
             for d in sorted((root / "writing").iterdir())
             if d.is_dir() and (d / "index.html").exists()] if (root / "writing").exists() else []
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    # lastmod is derived from the file that actually backs each URL, not written down
    # here. A literal date meant every rebuild emitted the same day forever, which told
    # the crawlers the site never changes and cancelled out the daily docs rebuild.
    def _lastmod(loc):
        seg = loc[len(SITE):].strip("/")
        f = (out_root / seg / "index.html") if seg else (out_root / "index.html")
        try:
            return datetime.date.fromtimestamp(f.stat().st_mtime).isoformat()
        except OSError:
            return datetime.date.today().isoformat()

    for loc, pri in urls:
        sm.append("  <url><loc>%s</loc><lastmod>%s</lastmod>"
                  "<changefreq>weekly</changefreq><priority>%s</priority></url>"
                  % (loc, _lastmod(loc), pri))
    sm.append("</urlset>")
    body = "\n".join(sm) + "\n"
    # Three files, one list. sitemap.xml is what Bing already reads successfully and is
    # left where it is. sitemap-pages.xml is the same bytes at a path Google holds no
    # cached fetch failure against, and sitemap-index.xml points at that — submitting an
    # index gives the crawler a fresh record instead of replaying a stale error against
    # a URL it decided about when this site was two days old.
    (out_root / "sitemap.xml").write_text(body)
    (out_root / "sitemap-pages.xml").write_text(body)
    newest = max((datetime.date.fromtimestamp(f.stat().st_mtime)
                  for f in out_root.rglob("index.html")), default=datetime.date.today())
    (out_root / "sitemap-index.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <sitemap><loc>%s/sitemap-pages.xml</loc><lastmod>%s</lastmod></sitemap>\n'
        '</sitemapindex>\n' % (SITE, newest.isoformat()))
    print("  sitemap: %d urls → sitemap.xml, sitemap-pages.xml, sitemap-index.xml"
          % len(urls))


def _json(s):
    import json
    return json.dumps(s, ensure_ascii=False)


if __name__ == "__main__":
    print("building documentation pages")
    build()
    print("done")
