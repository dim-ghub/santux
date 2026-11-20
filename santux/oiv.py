"""Native .oiv package installer.

Implements the OpenIV package format (assembly.xml versions 2.0–2.2) the way OpenIV and
CodeWalker's OIV installer apply it, writing only into the game's mods folder:

- <archive path> opens a game archive. The mods folder copy is used if there is one; otherwise
  the original is read from the game folder and the edited result is written to mods\\. Nested
  <archive> elements open archives inside it.
- <add source>dest</add> adds or replaces a file. Outside an archive, .rpf files and paths under
  update\\ or x64\\ go to the mods folder; anything else (scripts, .asi) goes to the game folder.
- <delete>, <xml> (add/replace/remove by XPath), <text> (insert/replace/add/delete lines).
- <defragmentation> is a no-op: every edited archive is rewritten compactly anyway.
- <pso> (binary metadata edits) isn't supported and fails the install with a clear message.

Every top-level path a package touches is recorded, so uninstalling one package means deleting
those files from mods\\ and re-applying the remaining packages that touch them, in order.
"""
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from .rpf import archive as A, keys as K


class OivError(Exception):
    pass


@dataclass
class Package:
    path: Path
    name: str = ""
    version: str = ""
    author: str = ""
    game_version: str = ""
    content: object = None   # lxml element <content>

    @classmethod
    def load(cls, path):
        path = Path(path)
        try:
            z = zipfile.ZipFile(path)
            xml = z.read("assembly.xml")
        except (zipfile.BadZipFile, KeyError) as e:
            raise OivError(f"{path.name} isn't a valid .oiv package ({e})")
        root = etree.fromstring(xml, etree.XMLParser(recover=True, remove_comments=True))
        md = root.find("metadata")
        p = cls(path)
        p._zip = z
        p._names = {n.replace("\\", "/").lower(): n for n in z.namelist()}
        if md is not None:
            p.name = (md.findtext("name") or "").strip()
            v = md.find("version")
            if v is not None:
                p.version = ".".join(x for x in ((v.findtext("major") or "").strip(), (v.findtext("minor") or "").strip()) if x)
            a = md.find("author")
            if a is not None:
                p.author = (a.findtext("displayName") or "").strip()
            p.game_version = (md.findtext("gameversion") or "").strip().lower()
        p.name = p.name or path.stem
        p.content = root.find("content")
        if p.content is None:
            raise OivError(f"{path.name} has no <content>")
        return p

    def read(self, source):
        key = ("content/" + source.replace("\\", "/").lstrip("/")).lower()
        real = self._names.get(key)
        if real is None:
            raise OivError(f"{self.path.name} is missing content/{source}")
        return self._zip.read(real)


def _norm(path):
    """Game-relative path in canonical form: forward slashes, lower case, no leading slash."""
    return posixpath.normpath(path.replace("\\", "/").strip().lstrip("/")).lower()


def _uses_mods(dest):
    d = _norm(dest)
    return d.startswith(("update/", "x64")) or d.endswith(".rpf") or d.startswith("mods/")


def resolve_ci(base: Path, rel: str):
    """Case-insensitive lookup of rel under base. Returns the existing path, or None."""
    cur = base
    for part in [p for p in rel.replace("\\", "/").split("/") if p]:
        nxt = cur / part
        if not nxt.exists():
            try:
                low = part.lower()
                nxt = next((c for c in cur.iterdir() if c.name.lower() == low), None)
            except OSError:
                nxt = None
            if nxt is None:
                return None
        cur = nxt
    return cur


def _target_path(base: Path, rel: str):
    """Where rel lives under base: the existing case-insensitive match, or a new path that
    reuses the existing folders' spelling."""
    found = resolve_ci(base, rel)
    if found:
        return found
    parts = [p for p in rel.replace("\\", "/").split("/") if p]
    cur = base
    for i, part in enumerate(parts):
        nxt = resolve_ci(cur, part)
        if nxt is None:
            return cur.joinpath(*parts[i:])
        cur = nxt
    return cur


class Session:
    """Applies packages to one game, keeping edited archives in memory until flush()."""

    def __init__(self, game, log=print, known=(), base_dir=None):
        """known: mods\\ paths that packages recorded by Santux produced. Any other
        mods\\ file a package edits or replaces was there before (the user's own OpenIV edits);
        a copy is kept in base_dir so rebuilds start from it instead of the game's original."""
        self.game = game
        self.log = log
        self.known = set(known)
        self.base_dir = base_dir
        self.keys = None
        self.archives = {}        # norm path -> Archive
        self.touched = set()      # norm paths in mods\ this session changed
        self.loose = []           # game-folder files (relative) added by top-level adds

    def _keys(self):
        if self.keys is None:
            self.keys = K.load(self.game, self.log)
        return self.keys

    def top_archive(self, rel, create):
        key = _norm(rel)
        if key in self.archives:
            return self.archives[key]
        mods = self.game.mods_folder
        cur = resolve_ci(mods, rel)
        if cur and cur.is_file():
            self._preserve(key, cur)
        src = cur or self._base(key) or resolve_ci(self.game.folder, rel)
        if src and src.is_file():
            a = A.Archive.open(str(src), self._keys())
        elif create:
            a = A.Archive.new(Path(rel.replace("\\", "/")).name)
        else:
            self.log(f"  (skipped: {rel} doesn't exist)")
            return None
        self.archives[key] = a
        return a

    def _base(self, key):
        if self.base_dir is None:
            return None
        p = resolve_ci(self.base_dir, key)
        return p if p and p.is_file() else None

    def _preserve(self, key, path):
        """Keep a copy of a mods\\ file Santux didn't create, before changing it."""
        if self.base_dir is None or key in self.known or key in self.touched or self._base(key):
            return
        dest = self.base_dir / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.log(f"  keeping a copy of your existing mods/{key}")
        import shutil
        shutil.copyfile(path, dest)
        self.known.add(key)

    # ------------------------------------------------------------ ops
    def apply(self, pkg: Package, only=None):
        """Apply a package. only: a set of norm paths; ops for other top-level paths are skipped
        (used when rebuilding those files after an uninstall). Returns the norm paths touched."""
        before = set(self.touched)
        mine = set()
        for op in pkg.content:
            if not isinstance(op.tag, str):
                continue
            tag = op.tag.lower()
            if tag == "archive":
                rel = op.get("path", "")
                key = _norm(rel)
                if only is not None and key not in only:
                    continue
                a = self.top_archive(rel, op.get("createIfNotExist", "").lower() == "true")
                if a is not None:
                    self._archive_ops(pkg, a, op)
                    mine.add(key)
            elif tag == "add":
                dest = (op.text or "").strip()
                key = _norm(dest)
                to_mods = _uses_mods(dest)
                if only is not None and (not to_mods or key not in only):
                    continue
                data = pkg.read(op.get("source", ""))
                if to_mods:
                    rel = dest.replace("\\", "/").lstrip("/")
                    if _norm(rel).startswith("mods/"):
                        rel = rel[5:]
                    target = _target_path(self.game.mods_folder, rel)
                    if target.is_file():
                        self._preserve(_norm(rel), target)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    self.archives.pop(_norm(rel), None)
                    target.write_bytes(data)
                    self.log(f"  added mods/{rel}")
                    mine.add(_norm(rel))
                    self.touched.add(_norm(rel))
                else:
                    target = _target_path(self.game.folder, dest)
                    if target.exists():
                        self.log(f"  skipped {dest}: already in the game folder")
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    self.loose.append(target.relative_to(self.game.folder).as_posix())
                    self.log(f"  added {dest}")
            elif tag == "delete":
                rel = (op.text or "").strip()
                key = _norm(rel)
                if only is not None and key not in only:
                    continue
                target = resolve_ci(self.game.mods_folder, rel)
                if target and target.is_file():
                    target.unlink()
                    self.log(f"  deleted mods/{rel}")
                    mine.add(key)
                else:
                    self.log(f"  (not deleting {rel}: only files in the mods folder are removed)")
            elif tag == "defragmentation":
                pass
            else:
                raise OivError(f"Unsupported top-level operation <{op.tag}> in {pkg.name}")
        self.touched |= mine
        return mine | (self.touched - before)

    def _archive_ops(self, pkg, a: A.Archive, node):
        for op in node:
            if not isinstance(op.tag, str):
                continue
            tag = op.tag.lower()
            if tag == "archive":
                rel = op.get("path", "")
                inner = a.open_nested(rel, self._keys(), create=op.get("createIfNotExist", "").lower() == "true")
                if inner is None:
                    self.log(f"  (skipped: no {rel} in {a.name})")
                    continue
                self._archive_ops(pkg, inner, op)
            elif tag == "add":
                dest = (op.text or "").strip()
                a.put_file(dest, pkg.read(op.get("source", "")))
            elif tag == "delete":
                a.delete((op.text or "").strip())
            elif tag == "xml":
                self._xml(a, op)
            elif tag == "text":
                self._text(a, op)
            elif tag == "defragmentation":
                pass
            elif tag == "pso":
                raise OivError(f"{pkg.name} edits binary metadata (<pso>), which Santux can't do yet.")
            else:
                raise OivError(f"Unsupported operation <{op.tag}> in {pkg.name}")

    # ------------------------------------------------------------ xml
    def _xml(self, a, op):
        path = op.get("path", "")
        e = a.find(path)
        if e is None or not isinstance(e, A.File):
            self.log(f"  (skipped xml edit: no {path} in {a.name})")
            return
        raw = a.read_file(e, self._keys())
        text = raw.decode("utf-8-sig", "replace")
        if not text.lstrip().startswith("<"):
            raise OivError(f"{path} isn't text XML (binary metadata isn't supported yet)")
        decl = re.match(r"\s*<\?xml[^>]*\?>", text)
        doc = etree.fromstring(text.encode("utf-8"), etree.XMLParser(remove_blank_text=False, huge_tree=True))
        tree = doc.getroottree()
        changed = 0
        for sub in op:
            if not isinstance(sub.tag, str):
                continue
            kind = sub.tag.lower()
            xpath = sub.get("xpath", "")
            nodes = _xpath(tree, xpath)
            if not nodes:
                self.log(f"  (xml {kind}: nothing matches {xpath} in {path})")
                continue
            node = nodes[0]
            if kind == "add":
                mode = (sub.get("append") or "Last").lower()
                frag = _fragment(sub)
                container = node.getparent() if mode in ("before", "after") else node
                if container is None or _duplicate(container, frag):
                    continue
                _insert(node, frag, mode)
            elif kind == "replace":
                parent = node.getparent()
                if parent is None:
                    continue
                frag = _fragment(sub)
                idx = parent.index(node)
                tail = node.tail
                parent.remove(node)
                for i, f in enumerate(frag):
                    parent.insert(idx + i, f)
                if frag:
                    frag[-1].tail = tail
            elif kind == "remove":
                parent = node.getparent()
                if parent is not None:
                    _remove_keep_tail(node)
            else:
                continue
            changed += 1
        if changed:
            body = etree.tostring(doc, encoding="unicode")
            out = (decl.group(0).strip() + "\r\n" if decl else "") + body
            a.put_file(path, out.encode("utf-8"))
            self.log(f"  edited {path} in {a.name} ({changed} change{'s' if changed != 1 else ''})")

    # ------------------------------------------------------------ text
    def _text(self, a, op):
        path = op.get("path", "")
        e = a.find(path)
        if e is None:
            if op.get("createIfNotExist", "").lower() != "true":
                self.log(f"  (skipped text edit: no {path} in {a.name})")
                return
            content = ""
        else:
            content = a.read_file(e, self._keys()).decode("utf-8-sig", "replace")
        for sub in op:
            if not isinstance(sub.tag, str):
                continue
            kind = sub.tag.lower()
            body = sub.text or ""
            if kind == "insert":
                content = _text_insert(content, sub.get("where", "Before"), sub.get("line", ""),
                                       sub.get("condition", "Mask"), body)
            elif kind == "replace":
                content = _text_lines(content, sub.get("line", ""), sub.get("condition", "Equal"), body)
            elif kind == "add":
                content += "\r\n" + body
            elif kind == "delete":
                content = _text_lines(content, body, sub.get("condition", "Equal"), None)
        a.put_file(path, content.encode("utf-8"))
        self.log(f"  edited {path} in {a.name}")

    # ------------------------------------------------------------ write
    def flush(self):
        """Write every edited archive into the mods folder."""
        mods = self.game.mods_folder
        for key, a in self.archives.items():
            if not a.is_modified():
                a.close()
                continue
            target = _target_path(mods, key)
            # Keep the original spelling of the file name when it comes from the game folder.
            orig = resolve_ci(self.game.folder, key)
            if orig and not resolve_ci(mods, key):
                rel = orig.relative_to(self.game.folder)
                target = _target_path(mods, rel.as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            self.log(f"Writing mods/{target.relative_to(mods).as_posix()}…")
            a.save(str(target))
            self.touched.add(key)
        self.archives.clear()


# ---------------------------------------------------------------- xml helpers

def _xpath(tree, xpath):
    try:
        r = tree.xpath(xpath)
    except etree.XPathError:
        r = []
    if not r:
        # Case-tolerant retry: match element names ignoring case, as OpenIV does.
        ci = re.sub(r"(?<=/)([A-Za-z_][\w.\-]*)",
                    lambda m: "*[translate(local-name(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')='%s']" % m.group(1).lower(),
                    xpath)
        try:
            r = tree.xpath(ci)
        except etree.XPathError:
            r = []
    return [n for n in r if isinstance(n, etree._Element)]


def _fragment(sub):
    """The element children of an <add>/<replace> op, copied, with sensible whitespace."""
    import copy
    out = []
    for c in sub:
        if isinstance(c.tag, str):
            n = copy.deepcopy(c)
            n.tail = None
            out.append(n)
    return out


def _canon(el):
    return re.sub(r">\s+<", "><", etree.tostring(el, encoding="unicode", with_tail=False)).strip().lower()


def _duplicate(container, frag):
    if not frag:
        return False
    have = {_canon(c) for c in container if isinstance(c.tag, str)}
    return all(_canon(f) in have for f in frag)


def _insert(node, frag, mode):
    if mode == "first":
        for i, f in enumerate(frag):
            node.insert(i, f)
        _indent(node, frag)
    elif mode == "before":
        parent = node.getparent()
        idx = parent.index(node)
        for i, f in enumerate(frag):
            parent.insert(idx + i, f)
            f.tail = _sibling_ws(node)
    elif mode == "after":
        parent = node.getparent()
        idx = parent.index(node)
        ws = _sibling_ws(node)
        for i, f in enumerate(frag):
            parent.insert(idx + 1 + i, f)
            f.tail = ws
        frag[-1].tail = node.tail
        node.tail = ws
    else:  # last
        kids = [c for c in node]
        if kids:
            last = kids[-1]
            ws = _sibling_ws(last)
            end = last.tail
            last.tail = ws
            for f in frag:
                node.append(f)
                f.tail = ws
            frag[-1].tail = end
        else:
            for f in frag:
                node.append(f)
            _indent(node, frag)


def _sibling_ws(node):
    prev = node.getprevious()
    if prev is not None and prev.tail and not prev.tail.strip():
        return prev.tail
    parent = node.getparent()
    if parent is not None and parent.text and not parent.text.strip():
        return parent.text
    return "\n"


def _indent(node, frag):
    depth = 0
    p = node
    while p.getparent() is not None:
        depth += 1
        p = p.getparent()
    inner = "\n" + "  " * (depth + 1)
    if not (node.text or "").strip():
        node.text = inner
    for f in frag:
        f.tail = inner
    frag[-1].tail = "\n" + "  " * depth


def _remove_keep_tail(node):
    parent = node.getparent()
    prev = node.getprevious()
    if node.tail and node.tail.strip():
        if prev is not None:
            prev.tail = (prev.tail or "") + node.tail
        else:
            parent.text = (parent.text or "") + node.tail
    parent.remove(node)


# ---------------------------------------------------------------- text helpers

def _match(line, pattern, cond):
    cond = (cond or "Equal").lower()
    if cond == "mask":
        rx = "^" + re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".") + "$"
        return re.match(rx, line, re.I) is not None
    if cond == "startwith":
        return line.strip().lower().startswith(pattern.lower())
    if cond == "endwith":
        return line.strip().lower().endswith(pattern.lower())
    if cond == "contains":
        return pattern.lower() in line.lower()
    return line.lower() == pattern.lower()


def _text_lines(content, pattern, cond, replacement):
    lines = re.split(r"\r\n|\r|\n", content)
    out = []
    for line in lines:
        if _match(line, pattern, cond):
            if replacement is not None:
                out.append(replacement)
        else:
            out.append(line)
    return "\r\n".join(out)


def _text_insert(content, where, pattern, cond, body):
    if body.strip() and body.strip() in content:
        return content
    lines = re.split(r"\r\n|\n", content)
    for i, line in enumerate(lines):
        rx = re.escape(pattern).replace(r"\*", ".*") if (cond or "").lower() == "mask" else re.escape(pattern)
        if re.search(rx, line, re.I):
            lines.insert(i if where.lower() == "before" else i + 1, body)
            break
    return "\r\n".join(lines)
