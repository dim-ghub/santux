"""Minimal reader/writer for Steam's text KeyValues (.vdf) files, preserving key order."""
import re

_TOKEN = re.compile(r'"((?:\\.|[^"\\])*)"|(\{)|(\})|(//[^\n]*)|(\S+)')


def _unescape(s):
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), s)


def _escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")


def loads(text):
    stack = [{}]
    key = None
    for m in _TOKEN.finditer(text):
        q, ob, cb, comment, bare = m.groups()
        if comment is not None:
            continue
        if ob:
            child = {}
            stack[-1][key] = child
            stack.append(child)
            key = None
        elif cb:
            stack.pop()
            if not stack:
                raise ValueError("unbalanced braces")
        else:
            tok = _unescape(q) if q is not None else bare
            if key is None:
                key = tok
            else:
                stack[-1][key] = tok
                key = None
    return stack[0]


def dumps(obj, indent=0):
    out = []
    pad = "\t" * indent
    for k, v in obj.items():
        if isinstance(v, dict):
            out.append(f'{pad}"{_escape(k)}"\n{pad}{{\n{dumps(v, indent + 1)}{pad}}}\n')
        else:
            out.append(f'{pad}"{_escape(k)}"\t\t"{_escape(v)}"\n')
    return "".join(out)


def get_ci(d, *keys):
    """Case-insensitive nested lookup; None when missing."""
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = next((v for kk, v in d.items() if kk.lower() == k.lower()), None)
    return d


def ensure_ci(d, *keys):
    for k in keys:
        found = next((kk for kk in d if kk.lower() == k.lower()), None)
        if found is None:
            d[k] = {}
            found = k
        d = d[found]
    return d
