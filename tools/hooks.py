"""MkDocs hooks. Pages whose front matter says robots: noindex are left out of sitemap.xml and sitemap.xml.gz."""
import gzip, os, re

_hidden = set()


def on_page_markdown(markdown, page, config, files):
    if "noindex" in str(page.meta.get("robots", "")):
        _hidden.add(page.canonical_url)
    return markdown


def on_post_build(config):
    path = os.path.join(config["site_dir"], "sitemap.xml")
    if not _hidden or not os.path.exists(path):
        return
    xml = open(path, encoding="utf-8").read()
    for url in _hidden:
        xml = re.sub(r"\s*<url>\s*<loc>" + re.escape(url) + r"</loc>.*?</url>", "", xml, flags=re.S)
    open(path, "w", encoding="utf-8").write(xml)
    with gzip.open(path + ".gz", "wb") as f:
        f.write(xml.encode("utf-8"))
