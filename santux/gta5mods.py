"""Read-only client for gta5-mods.com (no public API, so this parses its HTML).

Requests to www.gta5-mods.com are throttled in util.Http: the site blocks an IP for a minute
after a burst of page loads.
"""
import html
import re
import urllib.parse
from dataclasses import dataclass, field
from html.parser import HTMLParser

from . import util

BASE = "https://www.gta5-mods.com"
CATEGORIES = {
    "all": "All",
    "scripts": "Scripts",
    "vehicles": "Vehicles",
    "weapons": "Weapons",
    "player": "Player",
    "maps": "Maps",
    "misc": "Misc",
    "tools": "Tools",
    "paintjobs": "Paint Jobs",
}
# Sort orders shared by browsing and search ("" is the site's default: relevance for search).
SORTS = {
    "": "Relevance",
    "most-downloaded": "Most downloaded",
    "most-liked": "Most liked",
    "highest-rated": "Highest rated",
    "latest": "Recently updated",
    "latest-uploads": "Newest",
}


@dataclass
class ModSummary:
    url: str
    title: str
    image: str = ""
    version: str = ""
    author: str = ""
    downloads: str = ""
    likes: str = ""
    rating: str = ""
    categories: list = field(default_factory=list)

    @property
    def slug(self):
        return self.url.rstrip("/").rsplit("/", 1)[-1]

    @property
    def category(self):
        return urllib.parse.urlsplit(self.url).path.strip("/").split("/")[0]


@dataclass
class ModFile:
    label: str            # "3.4.1"
    current: bool
    downloads: str
    size: str
    date: str
    page: str             # /misc/blood-gore/download/192184
    sha256: str = ""      # from the VirusTotal link, when the site has scanned it


@dataclass
class ModDetails:
    url: str
    title: str
    version: str
    author: str
    description: str
    images: list
    files: list
    downloads: str = ""
    updated: str = ""

    @property
    def slug(self):
        return self.url.rstrip("/").rsplit("/", 1)[-1]


def _txt(s):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", s or "")).split())


def _abs(url):
    return urllib.parse.urljoin(BASE, url)


def parse_list(page):
    """ModSummary for each card in a listing or search page."""
    out = []
    # Cards after "More mods by" belong to a mod page's sidebar, not to a listing.
    blocks = page.split('<div class="file-list-obj">')[1:]
    for b in blocks:
        m = re.search(r'<a href="([^"]+)" title="([^"]*)" class="preview', b)
        if not m:
            continue
        s = ModSummary(_abs(m.group(1)), html.unescape(m.group(2)))
        if (im := re.search(r'<img[^>]+src="([^"]+)"', b)):
            s.image = im.group(1)
        if (v := re.search(r'class="version"[^>]*title="([^"]*)"', b)):
            s.version = html.unescape(v.group(1))
        if (a := re.search(r'class="bottom-by">By</span>\s*<a [^>]*title="([^"]*)"', b)):
            s.author = html.unescape(a.group(1))
        if (d := re.search(r'title="([\d,]+) Downloads"', b)):
            s.downloads = d.group(1)
        if (l := re.search(r'title="([\d,]+) Likes"', b)):
            s.likes = l.group(1)
        if (r := re.search(r'title="([\d.]+) star rating"', b)):
            s.rating = r.group(1)
        if (c := re.search(r'<ul class="categories">(.*?)</ul>', b, re.S)):
            s.categories = [_txt(x) for x in re.findall(r"<li>(.*?)</li>", c.group(1), re.S)]
        out.append(s)
    return out


def listing_url(query="", category="all", sort="", page=1):
    if query.strip():
        q = urllib.parse.quote_plus(query.strip())
        path = "/search/" + (f"{category}/" if category != "all" else "") + q
        if sort:
            path += "/" + sort
    else:
        path = f"/{category}/" + (sort or "most-downloaded")
    return BASE + path + (f"?page={page}" if page > 1 else "")


def _apply_adult_filter():
    """The site hides adult mods unless an `adult_filter` cookie is set (its "Show Adult Content"
    switch). Match it to the user's setting before each page load."""
    show = bool(util.settings().get("show_adult", False))
    have = any(c.name == "adult_filter" and "gta5-mods.com" in c.domain for c in util.http.cookies)
    if show and not have:
        util.http.text(BASE + "/adult_filter", referer=BASE + "/")
    elif not show and have:
        for c in list(util.http.cookies):
            if c.name == "adult_filter":
                util.http.cookies.clear(c.domain, c.path, c.name)


def search(query="", category="all", sort="", page=1):
    """Returns (results, has_next_page). An empty query browses the category."""
    _apply_adult_filter()
    url = listing_url(query, category, sort, page)
    results = parse_list(util.http.text(url))
    # The site loads further pages with JavaScript, so there's no "next" link to look for.
    return results, len(results) >= 10


class _Description(HTMLParser):
    """Text of the first element whose class includes description-body."""

    BLOCK = {"br", "p", "div", "li", "h1", "h2", "h3", "h4", "tr", "hr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.done = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        a = dict(attrs)
        if self.depth == 0:
            if "description-body" in (a.get("class") or ""):
                self.depth = 1
            return
        if tag not in ("br", "img", "hr", "input"):
            self.depth += 1
        if tag in self.BLOCK:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("• ")

    def handle_endtag(self, tag):
        if self.depth and not self.done:
            self.depth -= 1
            if self.depth == 0:
                self.done = True
            elif tag in self.BLOCK:
                self.parts.append("\n")

    def handle_data(self, data):
        if self.depth and not self.done:
            self.parts.append(data)

    def text(self):
        t = "".join(self.parts)
        t = re.sub(r"[ \t]+", " ", t)
        t = re.sub(r" *\n *", "\n", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t.strip().removesuffix("Show Full Description").strip()


def details(url):
    _apply_adult_filter()
    page = util.http.text(url)
    m = re.search(r"<h1>\s*(.*?)<span class=\"version\">(.*?)</span>", page, re.S)
    title = _txt(m.group(1)) if m else _txt((re.search(r"<title>(.*?)</title>", page, re.S) or [None, ""])[1])
    version = _txt(m.group(2)) if m else ""
    author = ""
    if (a := re.search(r'<a class="username" href="/users/[^"]+">([^<]+)</a>', page)):
        author = html.unescape(a.group(1))
    p = _Description()
    p.feed(page)
    images = []
    for im in re.findall(r'https://img\.gta5-mods\.com/q\d+/images/[^"\s\']+', page):
        if im not in images and "/avatars/" not in im:
            images.append(im)
    files = []
    for blk in page.split('file-version-container')[1:]:
        blk = blk.split("</p>", 1)[0] + blk.split("</p>", 1)[-1][:1200]
        dl = re.search(r'href="([^"]+/download/\d+)"', blk)
        if not dl or any(f.page == dl.group(1) for f in files):
            continue
        head = re.search(r'fa-file"></i>&nbsp;(.*?)(?:<span>|</div>|<p>)', blk, re.S)
        nums = re.findall(r'class="num-downloads">(.*?)</span>', blk, re.S)
        size = re.search(r'class="file-size">,\s*([^<]+)<', blk)
        vt = re.search(r"virustotal\.com/gui/file/([0-9a-f]{64})", blk)
        files.append(ModFile(
            label=_txt(head.group(1)) if head else "?",
            current="(current)" in blk[:400],
            downloads=_txt(nums[0]).split(" downloads")[0] if nums else "",
            size=size.group(1).strip() if size else "",
            date=_txt(nums[-1]) if len(nums) > 1 else "",
            page=dl.group(1),
            sha256=vt.group(1) if vt else "",
        ))
    downloads = ""
    if (d := re.search(r'file-downloads[^>]*>\s*<span class="num-downloads">([\d,]+)', page)):
        downloads = d.group(1)
    updated = ""
    if (u := re.search(r"Last Updated:</strong>\s*([^<]+)<", page)):
        updated = u.group(1).strip()
    return ModDetails(url, title, version, author, p.text(), images[:12], files, downloads, updated)


def resolve_file(download_page):
    """Direct files.gta5-mods.com URL behind a /download/<id> page."""
    # Without a Referer from the mod page, the site redirects back to the mod page.
    mod_page = _abs(download_page.rsplit("/download/", 1)[0])
    page = util.http.text(_abs(download_page), referer=mod_page)
    m = re.search(r"https://files\.gta5-mods\.com/uploads/[^\"'\s<]+", page)
    if not m:
        raise util.HttpError("No file link on " + download_page)
    return html.unescape(m.group(0))


def file_name(file_url):
    """Archive name without the site's random prefix ('58b535-Foo.zip' -> 'Foo.zip')."""
    name = urllib.parse.unquote(file_url.rsplit("/", 1)[-1])
    return re.sub(r"^[0-9a-f]{6}-", "", name)


def latest_file(url):
    """(ModDetails, current ModFile) for a mod page."""
    d = details(url)
    cur = next((f for f in d.files if f.current), d.files[0] if d.files else None)
    return d, cur
