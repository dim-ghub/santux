"""Read and write GTA V RPF7 archives.

Reading handles every encryption the game ships (NG, AES, OPEN/none). Writing always produces an
OPEN archive (unencrypted table of contents), which is what OpenIV.asi / RageOpenV load from the
mods folder. Untouched file data is copied byte for byte, encrypted or not; entries are written in
the per-directory ordinal name order the game expects.
"""
import io
import os
import struct
import zlib

from . import keys as K

MAGIC = 0x52504637          # 'RPF7'
ENC_NONE, ENC_OPEN, ENC_AES, ENC_NG = 0, 0x4E45504F, 0x0FFFFFF9, 0x0FEFFFFF
RSC7 = 0x37435352
BLOCK = 512


class RpfError(Exception):
    pass


class Entry:
    def __init__(self, name, parent=None):
        self.name = name
        self.parent = parent

    @property
    def lname(self):
        return self.name.lower()

    def path(self):
        parts = []
        e = self
        while e.parent is not None:
            parts.append(e.name)
            e = e.parent
        return "\\".join(reversed(parts))


class Dir(Entry):
    def __init__(self, name, parent=None):
        super().__init__(name, parent)
        self.children = {}          # lower name -> Entry

    def add(self, e):
        e.parent = self
        self.children[e.lname] = e
        return e


class File(Entry):
    """A file entry. Data is either a range of a source archive (copied as stored) or new bytes."""

    def __init__(self, name, parent=None):
        super().__init__(name, parent)
        self.resource = False
        self.size_field = 0       # FileSize as in the entry (0 = stored uncompressed, for binaries)
        self.usize = 0            # binary: uncompressed size
        self.encrypted = False    # binary: data is NG/AES encrypted
        self.sys_flags = 0
        self.gfx_flags = 0
        self.src = None           # (archive, absolute offset, stored length)
        self.data = None          # stored bytes, when new or modified
        self.nested = None        # Archive, when this .rpf entry was opened and may be modified

    @property
    def stored_len(self):
        if self.data is not None:
            return len(self.data)
        return self.src[2]


def _pad(n, a):
    return (n + a - 1) // a * a


class Archive:
    """An RPF7 archive. Open with Archive.open(path) or Archive.from_bytes(data, name); new() for empty."""

    def __init__(self, name):
        self.name = name
        self.root = Dir("")
        self.encryption = ENC_OPEN
        self._fh = None
        self._buf = None
        self._base = 0
        self.modified = False

    # ------------------------------------------------------------ reading
    @classmethod
    def new(cls, name):
        a = cls(name)
        a.modified = True
        return a

    @classmethod
    def open(cls, path, keys=None):
        a = cls(os.path.basename(path))
        a._fh = open(path, "rb")
        a._parse(os.path.getsize(path), keys)
        return a

    @classmethod
    def from_bytes(cls, data, name, keys=None):
        a = cls(name)
        a._buf = data
        a._parse(len(data), keys)
        return a

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None

    def _read(self, off, n):
        if self._buf is not None:
            return bytes(self._buf[off:off + n])
        self._fh.seek(off)
        return self._fh.read(n)

    def _parse(self, size, keys):
        ver, count, names_len, enc = struct.unpack("<4I", self._read(0, 16))
        if ver != MAGIC:
            raise RpfError(f"{self.name} is not an RPF7 archive")
        self.encryption = enc
        ents = self._read(16, count * 16)
        names = self._read(16 + count * 16, names_len)
        if enc in (ENC_NONE, ENC_OPEN):
            pass
        elif enc == ENC_AES:
            ents, names = K.aes_ecb_decrypt(ents, keys.aes), K.aes_ecb_decrypt(names, keys.aes)
        else:
            if keys is None:
                raise RpfError(f"{self.name} is encrypted; keys are needed")
            ents = K.ng_decrypt(keys, ents, self.name, size)
            names = K.ng_decrypt(keys, names, self.name, size)

        def name_at(off):
            end = names.index(b"\0", off)
            return names[off:end].decode("utf-8", "replace")

        raw = []
        for i in range(count):
            a, b, c, d = struct.unpack_from("<4I", ents, i * 16)
            raw.append((a, b, c, d, ents[i * 16:i * 16 + 16]))
        objs = [None] * count

        def make(i, parent):
            a, b, c, d, rawb = raw[i]
            if b == 0x7FFFFF00:
                e = Dir(name_at(a), parent)
                e._range = (c, d)
                return e
            no = rawb[0] | (rawb[1] << 8)
            fsize = rawb[2] | (rawb[3] << 8) | (rawb[4] << 16)
            foff = rawb[5] | (rawb[6] << 8) | (rawb[7] << 16)
            e = File(name_at(no), parent)
            if b & 0x80000000:
                e.resource = True
                foff &= 0x7FFFFF
                e.sys_flags, e.gfx_flags = c, d
                stored = fsize
                if fsize == 0xFFFFFF:
                    h = self._read(foff * BLOCK, 16)
                    stored = h[7] | (h[14] << 8) | (h[5] << 16) | (h[2] << 24)
                elif fsize == 0:
                    stored = _res_size(c) + _res_size(d)
            else:
                e.usize, e.encrypted = c, d == 1
                stored = fsize if fsize else c
            e.size_field = fsize
            e.src = (self, foff * BLOCK, stored)
            return e

        self.root = make(0, None)
        objs[0] = self.root
        stack = [self.root]
        while stack:
            d = stack.pop()
            start, n = d._range
            for i in range(start, start + n):
                e = make(i, d)
                d.children[e.lname] = e
                if isinstance(e, Dir):
                    stack.append(e)

    # ------------------------------------------------------------ lookup / edit
    @staticmethod
    def _split(path):
        return [p for p in path.replace("/", "\\").split("\\") if p]

    def find(self, path):
        e = self.root
        for p in self._split(path):
            if not isinstance(e, Dir):
                return None
            e = e.children.get(p.lower())
            if e is None:
                return None
        return e

    def ensure_dir(self, path):
        d = self.root
        for p in self._split(path):
            e = d.children.get(p.lower())
            if e is None:
                e = d.add(Dir(p))
                self.modified = True
            elif not isinstance(e, Dir):
                raise RpfError(f"{p} is a file, not a folder, in {self.name}")
            d = e
        return d

    def read_file(self, path_or_entry, keys=None):
        """Plain (decrypted, decompressed) contents of a binary file entry."""
        e = self.find(path_or_entry) if isinstance(path_or_entry, str) else path_or_entry
        if e is None or not isinstance(e, File):
            raise RpfError(f"No file {path_or_entry} in {self.name}")
        if e.nested is not None:
            return e.nested.to_bytes()
        if e.data is not None and getattr(e, "plain", None) is not None:
            return e.plain
        if e.resource:
            raise RpfError(f"{e.name} is a resource, not a plain file")
        arch, off, n = e.src if e.data is None else (None, 0, 0)
        raw = e.data if e.data is not None else arch._read(off, n)
        if e.encrypted:
            if (arch or self).encryption == ENC_AES:
                raw = K.aes_ecb_decrypt(raw, keys.aes)
            else:
                raw = K.ng_decrypt(keys, raw, e.name, e.usize)
        if e.size_field:
            raw = zlib.decompress(raw, -15)
        return raw

    def put_file(self, path, data: bytes):
        """Add or replace a file, stored the way CodeWalker/OpenIV store new files."""
        parts = self._split(path)
        d = self.ensure_dir("\\".join(parts[:-1]))
        name = parts[-1]
        e = File(name)
        if len(data) >= 16 and struct.unpack_from("<I", data, 0)[0] == RSC7:
            e.resource = True
            e.sys_flags, e.gfx_flags = struct.unpack_from("<II", data, 8)
            data = bytearray(data)
            n = len(data)
            if n >= 0xFFFFFF:
                data[7], data[14], data[5], data[2] = n & 0xFF, (n >> 8) & 0xFF, (n >> 16) & 0xFF, (n >> 24) & 0xFF
            e.size_field = min(n, 0xFFFFFF)
            e.data = bytes(data)
        else:
            e.usize = len(data)
            raw_store = name.lower().endswith((".rpf", ".awc"))
            comp = None if raw_store else zlib.compress(data, 9)[2:-4]
            if comp is None or len(comp) > 0xFFFFFF:
                e.size_field, e.data = 0, bytes(data)
            else:
                e.size_field, e.data = len(comp), comp
            e.plain = bytes(data)
        d.add(e)
        self.modified = True
        return e

    def delete(self, path):
        e = self.find(path)
        if e is None or e.parent is None:
            return False
        del e.parent.children[e.lname]
        self.modified = True
        return True

    def open_nested(self, path, keys, create=False):
        e = self.find(path)
        if e is None:
            if not create:
                return None
            parts = self._split(path)
            e = File(parts[-1])
            self.ensure_dir("\\".join(parts[:-1])).add(e)
            e.nested = Archive.new(parts[-1])
            self.modified = True
            return e.nested
        if not isinstance(e, File) or e.resource:
            raise RpfError(f"{path} isn't an archive")
        if e.nested is None:
            arch, off, n = e.src
            data = arch._read(off, n) if e.data is None else e.data
            if e.size_field:  # stored compressed (unusual for archives)
                data = zlib.decompress(data, -15)
            e.nested = Archive.from_bytes(data, e.name, keys)
        return e.nested

    def is_modified(self):
        if self.modified:
            return True
        stack = [self.root]
        while stack:
            d = stack.pop()
            for e in d.children.values():
                if isinstance(e, Dir):
                    stack.append(e)
                elif e.nested is not None and e.nested.is_modified():
                    return True
        return False

    # ------------------------------------------------------------ writing
    def _ordered(self):
        entries = [self.root]
        ranges = {}
        stack = [self.root]
        while stack:
            d = stack.pop()
            kids = sorted(d.children.values(), key=lambda e: e.name)
            ranges[id(d)] = (len(entries), len(kids))
            for e in kids:
                entries.append(e)
                if isinstance(e, Dir):
                    stack.append(e)
        return entries, ranges

    def _finalise_nested(self):
        stack = [self.root]
        while stack:
            d = stack.pop()
            for e in d.children.values():
                if isinstance(e, Dir):
                    stack.append(e)
                elif e.nested is not None and e.nested.is_modified():
                    data = e.nested.to_bytes()
                    e.data, e.size_field, e.usize, e.encrypted, e.resource = data, 0, len(data), False, False
                    e.nested = None

    def write(self, out):
        """Write the archive (OPEN encryption) to a binary file object at its current position 0."""
        self._finalise_nested()
        entries, ranges = self._ordered()
        names = bytearray()
        name_off = {}
        for e in entries:
            if e.name not in name_off:
                name_off[e.name] = len(names)
                names += e.name.encode("utf-8") + b"\0"
        names += b"\0" * (_pad(len(names), 16) - len(names))
        header_len = _pad(16 + 16 * len(entries) + len(names), BLOCK)

        pos = header_len // BLOCK
        place = {}
        for e in entries:
            if isinstance(e, File):
                place[id(e)] = pos
                pos += _pad(e.stored_len, BLOCK) // BLOCK
        if pos >= 1 << 23:
            raise RpfError(f"{self.name} would be larger than an RPF7 archive can be")

        toc = bytearray()
        for e in entries:
            no = name_off[e.name]
            if isinstance(e, Dir):
                start, n = ranges[id(e)]
                toc += struct.pack("<4I", no, 0x7FFFFF00, start, n)
                continue
            if no > 0xFFFF:
                raise RpfError(f"Too many file names in {self.name}")
            off = place[id(e)]
            if e.resource:
                fs = min(e.stored_len, 0xFFFFFF) if e.data is not None else e.size_field
                toc += struct.pack("<H", no) + fs.to_bytes(3, "little") + (off | 0x800000).to_bytes(3, "little")
                toc += struct.pack("<II", e.sys_flags, e.gfx_flags)
            else:
                fs = e.size_field
                toc += struct.pack("<H", no) + fs.to_bytes(3, "little") + off.to_bytes(3, "little")
                toc += struct.pack("<II", e.usize, 1 if e.encrypted else 0)

        out.write(struct.pack("<4I", MAGIC, len(entries), len(names), ENC_OPEN))
        out.write(toc)
        out.write(names)
        out.write(b"\0" * (header_len - 16 - len(toc) - len(names)))
        for e in entries:
            if not isinstance(e, File):
                continue
            n = e.stored_len
            if e.data is not None:
                out.write(e.data)
            else:
                arch, off, _ = e.src
                _copy(arch, off, n, out)
            out.write(b"\0" * (_pad(n, BLOCK) - n))

    def to_bytes(self):
        b = io.BytesIO()
        self.write(b)
        return b.getvalue()

    def save(self, path):
        """Write to path atomically (via a temporary file next to it)."""
        tmp = str(path) + ".santux-tmp"
        try:
            with open(tmp, "wb") as f:
                self.write(f)
            self.close()
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)


def _copy(arch, off, n, out):
    if arch._buf is not None:
        out.write(arch._buf[off:off + n])
        return
    fh = arch._fh
    if hasattr(os, "copy_file_range") and hasattr(out, "fileno"):
        try:
            out.flush()
            src, dst = fh.fileno(), out.fileno()
            dpos = out.tell()
            done = 0
            while done < n:
                c = os.copy_file_range(src, dst, n - done, off + done, dpos + done)
                if c == 0:
                    break
                done += c
            if done == n:
                out.seek(dpos + n)
                return
        except OSError:
            pass
    fh.seek(off)
    left = n
    while left:
        chunk = fh.read(min(left, 1 << 20))
        if not chunk:
            raise RpfError("Unexpected end of archive while copying")
        out.write(chunk)
        left -= len(chunk)


def _res_size(flags):
    s0 = ((flags >> 27) & 1) << 0
    s1 = ((flags >> 26) & 1) << 1
    s2 = ((flags >> 25) & 1) << 2
    s3 = ((flags >> 24) & 1) << 3
    s4 = ((flags >> 17) & 0x7F) << 4
    s5 = ((flags >> 11) & 0x3F) << 5
    s6 = ((flags >> 7) & 0xF) << 6
    s7 = ((flags >> 5) & 0x3) << 7
    s8 = ((flags >> 4) & 1) << 8
    return (0x200 << (flags & 0xF)) * (s0 + s1 + s2 + s3 + s4 + s5 + s6 + s7 + s8)
