"""GTA V archive keys, derived from the user's own game files.

The AES key is found in GTA5.exe by its SHA-1 (the approach and hashes come from CodeWalker /
Neodymium's GTA crypto work, MIT licensed). It decrypts CodeWalker's magic.dat, which holds the
NG keys, NG decryption tables and hash lookup table. magic.dat is useless without the AES key,
and is downloaded from CodeWalker's repository at a pinned commit. The derived keys are cached in
the app's data folder so the exe only has to be searched once per game build.
"""
import hashlib
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from .. import util

AES_KEY_SHA1 = bytes.fromhex("A0796128A775720AC204D9819F68C172E3952C6D")
MAGIC_URL = ("https://raw.githubusercontent.com/dexyfex/CodeWalker/"
             "709bf125cef921c5f35f1dab81d314c65684d71e/CodeWalker.Core/Resources/magic.dat")


@dataclass
class Keys:
    aes: bytes
    ng_keys: list          # 101 × 272 bytes, as tuples of 68 uint32
    ng_tables: list        # [17][16][256] uint32
    lut: bytes             # 256


def _find_aes_key(exe: Path, log):
    data = exe.read_bytes()
    log(f"Searching {exe.name} for the archive key (one-time, ~10 s)…")
    sha1 = hashlib.sha1
    mv = memoryview(data)
    for pos in range(0, len(data) - 32, 8):
        if sha1(mv[pos:pos + 32]).digest() == AES_KEY_SHA1:
            return bytes(mv[pos:pos + 32])
    raise RuntimeError(f"Couldn't find the archive key in {exe.name}. Is this an unmodified GTA V exe?")


def jenk(data: bytes) -> int:
    h = 0
    for b in data:
        h = (h + b) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


class NetRandom:
    """System.Random with a seed (the legacy subtractive generator .NET still uses for seeded instances)."""
    MBIG, MSEED = 2147483647, 161803398

    def __init__(self, seed):
        def i32(v):  # C# int arithmetic wraps; a negative seed makes it overflow here
            return (v + 0x80000000) % 0x100000000 - 0x80000000
        sub = self.MBIG if seed == -2147483648 else abs(seed)
        mj = i32(self.MSEED - sub)
        a = [0] * 56
        a[55] = mj
        mk = 1
        for i in range(1, 55):
            ii = (21 * i) % 55
            a[ii] = mk
            mk = i32(mj - mk)
            if mk < 0:
                mk = i32(mk + self.MBIG)
            mj = a[ii]
        for _ in range(4):
            for i in range(1, 56):
                a[i] = i32(a[i] - a[1 + (i + 30) % 55])
                if a[i] < 0:
                    a[i] = i32(a[i] + self.MBIG)
        self.a, self.inext, self.inextp = a, 0, 21

    def next_bytes(self, n):
        a, inext, inextp, MBIG = self.a, self.inext, self.inextp, self.MBIG
        out = bytearray(n)
        for i in range(n):
            inext = inext + 1 if inext < 55 else 1
            inextp = inextp + 1 if inextp < 55 else 1
            v = a[inext] - a[inextp]
            if v == MBIG:
                v -= 1
            if v < 0:
                v += MBIG
            a[inext] = v
            out[i] = v & 0xFF
        self.inext, self.inextp = inext, inextp
        return bytes(out)


def aes_ecb_decrypt(data: bytes, key: bytes) -> bytes:
    """AES-256-ECB over whole 16-byte blocks; a trailing partial block is left as is."""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    except ImportError:
        raise RuntimeError("The Python 'cryptography' package is needed (python-cryptography / python3-cryptography).")
    n = len(data) - len(data) % 16
    if n == 0:
        return data
    d = Cipher(algorithms.AES(key), modes.ECB()).decryptor()
    return d.update(data[:n]) + d.finalize() + data[n:]


def _decode_magic(magic: bytes, aes: bytes):
    seed = jenk(aes)
    seed = seed - (1 << 32) if seed >= 1 << 31 else seed
    rnd = NetRandom(seed)
    n = len(magic)
    r = [rnd.next_bytes(n) for _ in range(4)]
    db = bytes((magic[i] - r[0][i] - r[1][i] - r[2][i] - r[3][i]) & 0xFF for i in range(n))
    raw = zlib.decompress(aes_ecb_decrypt(db, aes), -15)
    b1, b2, b3 = raw[:27472], raw[27472:27472 + 278528], raw[306000:306256]
    ng_keys = [struct.unpack_from("<68I", b1, i * 272) for i in range(101)]
    flat = struct.unpack("<69632I", b2)
    tables = [[flat[(r_ * 16 + t) * 256:(r_ * 16 + t + 1) * 256] for t in range(16)] for r_ in range(17)]
    return ng_keys, tables, b3


_cache = {}


def load(game, log=print) -> Keys:
    exe = game.folder / game.exe
    st = exe.stat()
    tag = f"{game.edition}-{st.st_size}-{int(st.st_mtime)}"
    if tag in _cache:
        return _cache[tag]
    kdir = util.data_dir() / "keys"
    kdir.mkdir(exist_ok=True)
    key_file = kdir / f"{tag}.aes"
    if key_file.is_file():
        aes = key_file.read_bytes()
    else:
        aes = _find_aes_key(exe, log)
        key_file.write_bytes(aes)
    magic = kdir / "magic.dat"
    if not magic.is_file():
        log("Downloading CodeWalker's magic.dat (NG tables)…")
        util.http.download(MAGIC_URL, magic)
    ng_keys, tables, lut = _decode_magic(magic.read_bytes(), aes)
    k = Keys(aes, ng_keys, tables, lut)
    _cache[tag] = k
    return k


# ---------------------------------------------------------------- NG decryption

def name_hash(keys: Keys, name: str) -> int:
    lut = keys.lut
    r = 0
    for ch in name:
        t = (1025 * (lut[ord(ch) & 0xFF] + r)) & 0xFFFFFFFF
        r = (t >> 6) ^ t
    n9 = (9 * r) & 0xFFFFFFFF
    return (32769 * ((n9 >> 11) ^ n9)) & 0xFFFFFFFF


def ng_key(keys: Keys, name: str, length: int):
    # uint32 arithmetic, as in the game: archives over 4 GB minus the hash wrap around.
    return keys.ng_keys[((name_hash(keys, name) + length + 61) & 0xFFFFFFFF) % 101]


_ROUND_B = (0, 7, 10, 13, 1, 4, 11, 14, 2, 5, 8, 15, 3, 6, 9, 12)


def _ng_decrypt_np(keys, data, key, np):
    """All blocks at once with numpy: the same table lookups, vectorised across blocks."""
    tabs = getattr(keys, "_np_tables", None)
    if tabs is None:
        tabs = keys._np_tables = np.array(keys.ng_tables, dtype=np.uint32)  # (17, 16, 256)
    n = len(data) // 16
    b = np.frombuffer(data, dtype=np.uint8, count=n * 16).reshape(n, 16)
    k = np.array(key, dtype=np.uint32).reshape(17, 4)
    for rnd in range(17):
        t = tabs[rnd]
        order = range(16) if rnd in (0, 1, 16) else _ROUND_B
        o = list(order)
        x = np.empty((n, 4), dtype=np.uint32)
        for w in range(4):
            i0, i1, i2, i3 = o[4 * w:4 * w + 4]
            x[:, w] = t[i0][b[:, i0]] ^ t[i1][b[:, i1]] ^ t[i2][b[:, i2]] ^ t[i3][b[:, i3]] ^ k[rnd, w]
        b = x.astype("<u4").view(np.uint8).reshape(n, 16)
    return b.tobytes() + data[n * 16:]


def ng_decrypt(keys: Keys, data: bytes, name: str, length: int) -> bytes:
    key = ng_key(keys, name, length)
    if len(data) >= 4096:
        try:
            import numpy as np
            return _ng_decrypt_np(keys, data, key, np)
        except ImportError:
            pass
    T = keys.ng_tables
    sub = [key[4 * i:4 * i + 4] for i in range(17)]
    out = bytearray(data)
    nblocks = len(data) // 16
    for bi in range(nblocks):
        b = data[bi * 16:bi * 16 + 16]
        for rnd in range(17):
            t, k = T[rnd], sub[rnd]
            if rnd in (0, 1, 16):
                x1 = t[0][b[0]] ^ t[1][b[1]] ^ t[2][b[2]] ^ t[3][b[3]] ^ k[0]
                x2 = t[4][b[4]] ^ t[5][b[5]] ^ t[6][b[6]] ^ t[7][b[7]] ^ k[1]
                x3 = t[8][b[8]] ^ t[9][b[9]] ^ t[10][b[10]] ^ t[11][b[11]] ^ k[2]
                x4 = t[12][b[12]] ^ t[13][b[13]] ^ t[14][b[14]] ^ t[15][b[15]] ^ k[3]
            else:
                x1 = t[0][b[0]] ^ t[7][b[7]] ^ t[10][b[10]] ^ t[13][b[13]] ^ k[0]
                x2 = t[1][b[1]] ^ t[4][b[4]] ^ t[11][b[11]] ^ t[14][b[14]] ^ k[1]
                x3 = t[2][b[2]] ^ t[5][b[5]] ^ t[8][b[8]] ^ t[15][b[15]] ^ k[2]
                x4 = t[3][b[3]] ^ t[6][b[6]] ^ t[9][b[9]] ^ t[12][b[12]] ^ k[3]
            b = struct.pack("<4I", x1, x2, x3, x4)
        out[bi * 16:bi * 16 + 16] = b
    return bytes(out)
