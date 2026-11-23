"""Gemini AI integration: turn non-.oiv mods + written instructions into installable .oiv packages.

Reads a mod's gta5-mods.com description, file listing, and any readme/text/xml files inside the
extracted archive, asks Gemini (free tier via Google AI Studio) for a structured installation plan,
validates every path and XML fragment, and compiles archive / mods-folder edits into a real .oiv
package via installer.make_oiv() plus any loose game-folder copies.

Because the output is a standard Santux Plan (a generated .oiv + loose copies), installing,
disabling, enabling, rebuilding, and uninstalling work identically to any native .oiv mod.
"""
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from . import installer, oiv as oivmod, util

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.5-flash"
FALLBACK_MODELS = ("gemini-2.5-flash", "gemini-3.8-flash", "gemini-2.0-flash")

BUILTIN_MODELS = [
    {"key": "", "label": "Auto (recommended)"},
    {"key": "gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
    {"key": "gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash-Lite"},
    {"key": "gemini-2.5-pro", "label": "Gemini 2.5 Pro"},
    {"key": "gemini-3.8-flash", "label": "Gemini 3.8 Flash"},
    {"key": "gemini-2.0-flash", "label": "Gemini 2.0 Flash"},
]

_SKIP_MODEL_SUBSTRS = ("embedding", "aqa", "tts", "audio", "image-generation", "imagen", "veo", "live", "robotics")

INSTRUCTION_NAMES = ("readme", "read me", "read_me", "install", "how to", "howto",
                     "instruction", "guide", "manual", "note", "info", "changelog", "credits")
TEXT_EXTS = {".txt", ".md", ".nfo", ".ini", ".cfg", ".xml", ".meta", ".json", ".dat", ".log", ".yml", ".yaml", ".toml"}
PREVIEW_ONLY_EXTS = {".xml", ".meta", ".json", ".dat", ".ini", ".cfg", ".yml", ".yaml", ".toml"}

MAX_FILES_LISTED = 400
MAX_DESCRIPTION_CHARS = 16000
MAX_TOTAL_TEXT_CHARS = 42000
MAX_README_CHARS = 12000
MAX_OTHER_TEXT_CHARS = 3500


class AiError(Exception):
    pass


@dataclass
class AiResult:
    summary: str = ""
    warnings: list = field(default_factory=list)
    steps: list = field(default_factory=list)       # human-readable descriptions of each op
    oiv_path: Path | None = None
    copies: list = field(default_factory=list)      # (src Path, dest rel to game folder)
    used_sources: set = field(default_factory=set)  # source Paths consumed by the AI plan


# ---------------------------------------------------------------- settings

def api_key() -> str:
    return (util.settings().get("gemini_api_key") or os.environ.get("GEMINI_API_KEY") or "").strip()


def model_name() -> str:
    return (util.settings().get("gemini_model") or "").strip() or DEFAULT_MODEL


def auto_convert_enabled() -> bool:
    s = util.settings()
    if "gemini_auto" in s:
        return bool(s["gemini_auto"])
    return bool(api_key())


def is_configured() -> bool:
    return bool(api_key())


# ---------------------------------------------------------------- Gemini REST client

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary": {
            "type": "STRING",
            "description": "1-2 sentence plain-English summary of what this mod installs and how.",
        },
        "warnings": {
            "type": "ARRAY",
            "items": {"type": "STRING"},
            "description": "Important caveats, skipped optional variants, or manual steps that cannot be automated.",
        },
        "operations": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "type": {
                        "type": "STRING",
                        "enum": [
                            "add_to_archive",
                            "delete_from_archive",
                            "xml_edit",
                            "text_edit",
                            "copy_file",
                        ],
                    },
                    "archive": {
                        "type": "STRING",
                        "description": "Top-level GTA V .rpf path without leading mods/ (e.g. 'update/update.rpf', 'x64e.rpf', 'update/x64/dlcpacks/patchday28ng/dlc.rpf').",
                    },
                    "nested_archives": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "description": "Optional nested .rpf paths inside archive (e.g. ['levels/gta5/vehicles.rpf']).",
                    },
                    "source": {
                        "type": "STRING",
                        "description": "Exact relative path of a file inside the mod archive.",
                    },
                    "dest": {
                        "type": "STRING",
                        "description": "Destination path inside the archive (for archive ops) or relative to the GTA V game folder (for copy_file).",
                    },
                    "xml_action": {
                        "type": "STRING",
                        "enum": ["add", "replace", "remove"],
                    },
                    "xpath": {
                        "type": "STRING",
                        "description": "XPath expression for xml_edit (e.g. '/SMandatoryPacksData/Paths').",
                    },
                    "append": {
                        "type": "STRING",
                        "enum": ["Last", "First", "Before", "After"],
                    },
                    "xml_content": {
                        "type": "STRING",
                        "description": "Well-formed XML element(s) to add or replace with for xml_edit.",
                    },
                    "text_action": {
                        "type": "STRING",
                        "enum": ["insert", "replace", "add", "delete"],
                    },
                    "where": {
                        "type": "STRING",
                        "enum": ["Before", "After"],
                    },
                    "line": {
                        "type": "STRING",
                        "description": "Line pattern to match for text_edit.",
                    },
                    "condition": {
                        "type": "STRING",
                        "enum": ["Mask", "Equal", "StartWith", "EndWith", "Contains"],
                    },
                    "text_content": {
                        "type": "STRING",
                        "description": "Text to insert, replace, add, or delete for text_edit.",
                    },
                },
                "required": ["type"],
            },
        },
    },
    "required": ["summary", "warnings", "operations"],
}

SYSTEM_INSTRUCTION = """You are an expert GTA V mod packaging assistant for Santux (an OpenIV/.oiv-compatible mod manager for Linux).

Your job: read a mod's description, file list, and included readme/text/xml files, and produce a precise JSON installation plan that Santux will compile into an OpenIV .oiv package (and/or loose game-folder copies).

CRITICAL RULES:
1. Only reference files in "source" that ACTUALLY EXIST in the provided file list, using their EXACT relative paths.
2. Never include paths for FiveM, RageMP, alt:V, or RagePluginHook — this is always single-player GTA V.
3. Match the user's GTA V edition (Legacy vs Enhanced) if the mod provides edition-specific folders or instructions.
4. If the mod includes multiple optional variants/presets (e.g. "Regular" vs "Low-End", or "Optional" extras), pick the standard/recommended main version and note the skipped variants in "warnings".
5. Never overwrite core game or loader files (gta5.exe, dinput8.dll, scripthookv.dll, xinput1_4.dll, etc.).
6. Archive paths MUST NOT start with "mods/" — Santux automatically writes all archive edits into the game's mods/ folder.
   - Example: "mods/update/update.rpf/common/data/handling.meta" ->
     type: "add_to_archive", archive: "update/update.rpf", dest: "common/data/handling.meta"
   - Example: "mods/x64e.rpf/levels/gta5/vehicles.rpf/adder.yft" ->
     type: "add_to_archive", archive: "x64e.rpf", nested_archives: ["levels/gta5/vehicles.rpf"], dest: "adder.yft"
   - Example: "mods/update/x64/dlcpacks/mycar/dlc.rpf" ->
     type: "copy_file", source: "...", dest: "update/x64/dlcpacks/mycar/dlc.rpf"
     AND add an "xml_edit" on archive "update/update.rpf", dest "common/data/dlclist.xml",
     xml_action: "add", xpath: "/SMandatoryPacksData/Paths", append: "Last",
     xml_content: "<Item>dlcpacks:/mycar/</Item>"
7. For loose files that belong in the GTA V game folder (e.g. Menyoo vehicles/maps in menyooStuff/Vehicles/ or menyooStuff/Spooner/, scripts in scripts/, .asi plugins and their .ini/.xml configs in the game root):
   - Use type: "copy_file" with dest relative to the GTA V root folder (e.g. "menyooStuff/Vehicles/mycar.xml", "scripts/MyMod.xml").
8. For XML edits inside an .rpf archive (like dlclist.xml, extratitleupdatedata.meta, handling.meta, vehicles.meta, carvariations.meta, weaponcomponents.meta):
   - Use type: "xml_edit" with valid XPath and well-formed XML in "xml_content".
   - If the mod ships a complete replacement file (e.g. a full handling.meta or visualsettings.dat), use "add_to_archive" instead of "xml_edit".
   - If the mod ships a small XML snippet meant to be pasted into an existing file inside an .rpf, use "xml_edit".
9. Binary metadata files (.ymt, .ymf, .ymap, .ytyp) CANNOT be edited with xml_edit or text_edit — they can only be replaced wholesale via "add_to_archive".
10. If the instructions are truly ambiguous or require something unsupported (like editing binary PSO/RBF metadata or running an external .exe installer), explain clearly in "warnings" and only emit operations you are confident are correct. If nothing can be safely determined, return an empty "operations" array with an explanation in "summary" and "warnings".
"""


def _post_gemini(model: str, key: str, payload: dict, timeout: int = 90) -> dict:
    url = f"{API_BASE}/{model}:generateContent"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=util.ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raw = ""
        try:
            raw = e.read().decode("utf-8", "replace")
            msg = json.loads(raw).get("error", {}).get("message", "")
        except Exception:
            msg = raw[:300]
        if e.code in (401, 403):
            raise AiError(f"Gemini API key rejected ({e.code}): {msg or e.reason}") from None
        if e.code == 429:
            raise AiError(f"Gemini rate limit reached (429). Wait a moment and try again. {msg}") from None
        err = AiError(f"Gemini API error ({e.code}): {msg or e.reason}")
        err.http_code = e.code
        raise err from None
    except urllib.error.URLError as e:
        raise AiError(f"Could not reach Gemini API: {e.reason}") from None


def _call_gemini(payload: dict, key: str | None = None, model: str | None = None, timeout: int = 90) -> tuple[dict, str]:
    k = (key if key is not None else api_key()).strip()
    if not k:
        raise AiError("No Gemini API key configured. Add your free key in Settings → AI installer (Gemini).")
    pinned = (model if model is not None else util.settings().get("gemini_model") or "").strip()
    candidates = [pinned] if pinned else list(FALLBACK_MODELS)
    tried = set()
    last_err = None
    for m in candidates:
        tried.add(m)
        try:
            return _post_gemini(m, k, payload, timeout=timeout), m
        except AiError as e:
            last_err = e
            if getattr(e, "http_code", None) == 404 and not pinned:
                continue
            raise
    if not pinned:
        for entry in list_models(key=k):
            m = entry.get("key") or ""
            if not m or m in tried:
                continue
            try:
                return _post_gemini(m, k, payload, timeout=timeout), m
            except AiError as e:
                last_err = e
                if getattr(e, "http_code", None) == 404:
                    continue
                raise
    raise last_err or AiError("No working Gemini model found.")


def _extract_text(resp: dict) -> str:
    cands = resp.get("candidates") or []
    if not cands:
        fb = resp.get("promptFeedback") or {}
        reason = fb.get("blockReason") or "no candidates returned"
        raise AiError(f"Gemini returned no response ({reason}).")
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
    if not text.strip():
        reason = cands[0].get("finishReason") or "empty response"
        raise AiError(f"Gemini returned an empty response ({reason}).")
    return text


def test_connection(key: str | None = None, model: str | None = None) -> str:
    """Verify the Gemini API key and model work. Returns the model name that succeeded."""
    payload = {
        "contents": [{"parts": [{"text": "Reply with the single word OK."}]}],
        "generationConfig": {"maxOutputTokens": 16, "temperature": 0},
    }
    _, used_model = _call_gemini(payload, key=key, model=model, timeout=25)
    return used_model


def list_models(key: str | None = None, timeout: int = 20) -> list[dict]:
    """Fetch all generateContent-capable Gemini models available to this API key."""
    k = (key if key is not None else api_key()).strip()
    if not k:
        return list(BUILTIN_MODELS)
    raw_models = []
    page_token = ""
    for _ in range(5):
        url = f"{API_BASE}?pageSize=100" + (f"&pageToken={page_token}" if page_token else "")
        req = urllib.request.Request(url, headers={"x-goog-api-key": k}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=util.ssl_context()) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            raw = ""
            try:
                raw = e.read().decode("utf-8", "replace")
                msg = json.loads(raw).get("error", {}).get("message", "")
            except Exception:
                msg = raw[:300]
            raise AiError(f"Could not list Gemini models ({e.code}): {msg or e.reason}") from None
        except urllib.error.URLError as e:
            raise AiError(f"Could not reach Gemini API: {e.reason}") from None
        raw_models.extend(data.get("models") or [])
        page_token = data.get("nextPageToken") or ""
        if not page_token:
            break

    found = []
    for m in raw_models:
        name = (m.get("name") or "").removeprefix("models/")
        methods = m.get("supportedGenerationMethods") or []
        low = name.lower()
        if "generateContent" not in methods or not low.startswith("gemini-"):
            continue
        if any(s in low for s in _SKIP_MODEL_SUBSTRS):
            continue
        display = (m.get("displayName") or "").strip() or name
        found.append((name, display))

    # Deduplicate labels if multiple model IDs share a displayName (e.g. preview vs stable)
    from collections import Counter
    counts = Counter(d for _, d in found)
    entries = []
    for name, display in found:
        label = f"{display} ({name})" if counts[display] > 1 or ("preview" in name or "exp" in name) and name not in display.lower() else display
        entries.append({"key": name, "label": label})

    # Sort newest versions first, preferring Flash models over Pro/exp at the same version
    def _sort_key(item):
        k_ = item["key"].lower()
        nums = [int(x) for x in re.findall(r"\d+", k_)[:2]]
        major = nums[0] if len(nums) > 0 else 0
        minor = nums[1] if len(nums) > 1 else 0
        is_preview = 1 if ("preview" in k_ or "exp" in k_ or "latest" in k_) else 0
        tier = 0 if "flash" in k_ and "lite" not in k_ else (1 if "flash" in k_ else (2 if "pro" in k_ else 3))
        return (-major, -minor, is_preview, tier, k_)

    entries.sort(key=_sort_key)
    return [{"key": "", "label": "Auto (recommended)"}] + entries


# ---------------------------------------------------------------- context gathering

def _is_instruction_file(p: Path) -> bool:
    low = p.stem.lower()
    return any(tok in low for tok in INSTRUCTION_NAMES) or p.suffix.lower() in (".txt", ".md", ".nfo")


def _read_text_safe(p: Path, limit: int) -> str:
    try:
        raw = p.read_bytes()
    except OSError:
        return ""
    # Skip binary files masquerading as text
    sample = raw[:4096]
    if b"\x00" in sample:
        try:
            text = raw.decode("utf-16")
        except UnicodeDecodeError:
            return ""
    else:
        text = raw.decode("utf-8-sig", "replace")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) > limit:
        return text[:limit] + f"\n... [truncated, {len(text) - limit} more chars]"
    return text


def gather_context(root: Path, game, title: str = "", description: str = "") -> str:
    """Build the prompt describing the mod's metadata, files, and text/instruction contents."""
    files = sorted((p for p in root.rglob("*") if p.is_file()), key=installer.natural_key)
    sections = []

    sections.append(
        f"MOD TITLE: {title or root.name}\n"
        f"TARGET GAME: GTA V {game.edition} (version {game.version or 'unknown'})"
    )

    if description and description.strip():
        desc = description.strip()
        if len(desc) > MAX_DESCRIPTION_CHARS:
            desc = desc[:MAX_DESCRIPTION_CHARS] + "\n... [truncated]"
        sections.append(f"MOD PAGE DESCRIPTION:\n{desc}")

    # File listing
    listing_lines = []
    for p in files[:MAX_FILES_LISTED]:
        rel = p.relative_to(root).as_posix()
        try:
            sz = util.human_size(p.stat().st_size)
        except OSError:
            sz = "?"
        listing_lines.append(f"  {rel} ({sz})")
    if len(files) > MAX_FILES_LISTED:
        listing_lines.append(f"  ... ({len(files) - MAX_FILES_LISTED} more files)")
    sections.append("FILES IN MOD ARCHIVE:\n" + "\n".join(listing_lines))

    # Text / instruction / XML files (prioritize readmes first)
    text_files = [p for p in files if p.suffix.lower() in TEXT_EXTS]
    text_files.sort(key=lambda p: (0 if _is_instruction_file(p) else 1, len(p.relative_to(root).parts), str(p).lower()))

    budget = MAX_TOTAL_TEXT_CHARS
    file_blocks = []
    for p in text_files:
        if budget <= 200:
            break
        rel = p.relative_to(root).as_posix()
        is_doc = _is_instruction_file(p) and p.suffix.lower() not in PREVIEW_ONLY_EXTS
        limit = min(budget, MAX_README_CHARS if is_doc else MAX_OTHER_TEXT_CHARS)
        content = _read_text_safe(p, limit)
        if not content:
            continue
        file_blocks.append(f"--- FILE: {rel} ---\n{content}")
        budget -= len(content)

    if file_blocks:
        sections.append("TEXT & CONFIG FILE CONTENTS:\n\n" + "\n\n".join(file_blocks))

    return "\n\n".join(sections)


# ---------------------------------------------------------------- compilation to .oiv

def _clean_rel(path: str) -> str:
    """Normalize a relative path and reject traversal attempts."""
    p = (path or "").strip().replace("\\", "/").lstrip("/")
    parts = []
    for part in p.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            raise AiError(f"Unsafe path returned by AI: {path!r}")
        parts.append(part)
    return "/".join(parts)


def _strip_mods_prefix(path: str) -> str:
    p = _clean_rel(path)
    if p.lower().startswith("mods/"):
        return p[5:]
    return p


def _split_archive_chain(archive: str, nested: list | None = None) -> list[str]:
    """Split an archive path + optional nested_archives into a clean chain of .rpf paths.
    Handles cases where the LLM puts 'x64e.rpf/levels/gta5/vehicles.rpf' in a single string."""
    raw_items = [_strip_mods_prefix(archive)]
    for n in (nested or []):
        if n and str(n).strip():
            raw_items.append(_clean_rel(str(n)))
    chain = []
    for item in raw_items:
        if not item:
            continue
        # Split on .rpf/ boundaries (case-insensitive)
        parts = re.split(r"(?<=\.rpf)/", item, flags=re.I)
        for p in parts:
            p = p.strip("/")
            if p:
                chain.append(p)
    return chain


def _resolve_source(root: Path, rel: str) -> Path | None:
    cleaned = _clean_rel(rel)
    if not cleaned:
        return None
    cand = root / cleaned
    if not cand.is_file():
        cand = oivmod.resolve_ci(root, cleaned)
    if cand is None or not cand.is_file():
        return None
    try:
        cand.resolve().relative_to(root.resolve())
    except ValueError:
        return None
    return cand


def _x(s: str) -> str:
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _validate_xml_fragment(xml_str: str) -> str:
    """Ensure xml_str is a well-formed XML fragment (one or more elements)."""
    s = (xml_str or "").strip()
    if not s:
        raise AiError("Empty XML fragment")
    try:
        wrap = etree.fromstring(f"<_santux_frag>{s}</_santux_frag>".encode("utf-8"))
    except etree.XMLSyntaxError as e:
        raise AiError(f"Invalid XML fragment from AI: {e}") from None
    if not len(wrap):
        raise AiError("XML fragment contains no elements")
    return "".join(etree.tostring(c, encoding="unicode") for c in wrap)


class _ArchiveNode:
    """Tree node representing an <archive> element in assembly.xml."""
    def __init__(self, path: str):
        self.path = path
        self.children: dict[str, "_ArchiveNode"] = {}
        self.ops: list[str] = []

    def sub(self, path: str) -> "_ArchiveNode":
        key = path.lower()
        if key not in self.children:
            self.children[key] = _ArchiveNode(path)
        return self.children[key]

    def render(self, indent: str = "") -> str:
        win_path = self.path.replace("/", "\\")
        lines = [f'{indent}<archive path="{_x(win_path)}" createIfNotExist="True" type="RPF7">']
        for op in self.ops:
            lines.append(f"{indent}  {op}")
        for child in self.children.values():
            lines.append(child.render(indent + "  "))
        lines.append(f"{indent}</archive>")
        return "\n".join(lines)


def compile_plan(data: dict, root: Path, title: str, version: str = "", author: str = "") -> AiResult:
    """Validate Gemini's JSON response and compile it into an AiResult (.oiv + loose copies)."""
    result = AiResult(
        summary=(data.get("summary") or "").strip(),
        warnings=[str(w).strip() for w in (data.get("warnings") or []) if str(w).strip()],
    )
    ops = data.get("operations") or []
    if not ops:
        return result

    top_archives: dict[str, _ArchiveNode] = {}
    top_level_xml: list[str] = []
    oiv_files: dict[str, Path] = {}   # content/<key> -> source Path
    src_to_key: dict[Path, str] = {}

    def register_content_file(src: Path) -> str:
        if src in src_to_key:
            return src_to_key[src]
        rel = src.relative_to(root).as_posix()
        key = rel
        n = 1
        while key.lower() in {k.lower() for k in oiv_files}:
            key = f"f{n}_{src.name}"
            n += 1
        oiv_files[key] = src
        src_to_key[src] = key
        result.used_sources.add(src)
        return key

    def get_archive_node(archive: str, nested: list | None) -> _ArchiveNode | None:
        chain = _split_archive_chain(archive, nested)
        if not chain:
            return None
        first = chain[0]
        key = first.lower()
        if key not in top_archives:
            top_archives[key] = _ArchiveNode(first)
        node = top_archives[key]
        for sub in chain[1:]:
            node = node.sub(sub)
        return node

    for op in ops:
        kind = (op.get("type") or "").strip().lower()
        try:
            if kind == "add_to_archive":
                src = _resolve_source(root, op.get("source", ""))
                if not src:
                    result.warnings.append(f"Skipped missing source file: {op.get('source')}")
                    continue
                node = get_archive_node(op.get("archive", ""), op.get("nested_archives"))
                if node is None:
                    result.warnings.append(f"Skipped archive op with no archive path for {src.name}")
                    continue
                dest = _clean_rel(op.get("dest", ""))
                if not dest or dest.endswith("/"):
                    dest = (dest + "/" + src.name).lstrip("/")
                ckey = register_content_file(src)
                win_dest = dest.replace("/", "\\")
                node.ops.append(f'<add source="{_x(ckey)}">{_x(win_dest)}</add>')
                chain_str = " → ".join(_split_archive_chain(op.get("archive", ""), op.get("nested_archives")))
                result.steps.append(f"Add {src.relative_to(root).as_posix()} → {chain_str}/{dest}")

            elif kind == "delete_from_archive":
                node = get_archive_node(op.get("archive", ""), op.get("nested_archives"))
                dest = _clean_rel(op.get("dest", ""))
                if node is None or not dest:
                    continue
                node.ops.append(f"<delete>{_x(dest.replace('/', chr(92)))}</delete>")
                chain_str = " → ".join(_split_archive_chain(op.get("archive", ""), op.get("nested_archives")))
                result.steps.append(f"Delete {chain_str}/{dest}")

            elif kind == "xml_edit":
                node = get_archive_node(op.get("archive", ""), op.get("nested_archives"))
                dest = _clean_rel(op.get("dest", ""))
                action = (op.get("xml_action") or "").strip().lower()
                xpath = (op.get("xpath") or "").strip()
                if node is None or not dest or action not in ("add", "replace", "remove") or not xpath:
                    result.warnings.append(f"Skipped incomplete XML edit on {dest or '?'}")
                    continue
                win_dest = dest.replace("/", "\\")
                if action == "remove":
                    inner = f'<remove xpath="{_x(xpath)}"/>'
                elif action == "add":
                    frag = _validate_xml_fragment(op.get("xml_content", ""))
                    append = (op.get("append") or "Last").strip()
                    if append.lower() not in ("last", "first", "before", "after"):
                        append = "Last"
                    inner = f'<add xpath="{_x(xpath)}" append="{_x(append)}">{frag}</add>'
                else:  # replace
                    frag = _validate_xml_fragment(op.get("xml_content", ""))
                    inner = f'<replace xpath="{_x(xpath)}">{frag}</replace>'
                node.ops.append(f'<xml path="{_x(win_dest)}">{inner}</xml>')
                chain_str = " → ".join(_split_archive_chain(op.get("archive", ""), op.get("nested_archives")))
                result.steps.append(f"Edit XML ({action}) {chain_str}/{dest} at {xpath}")

            elif kind == "text_edit":
                node = get_archive_node(op.get("archive", ""), op.get("nested_archives"))
                dest = _clean_rel(op.get("dest", ""))
                action = (op.get("text_action") or "").strip().lower()
                if node is None or not dest or action not in ("insert", "replace", "add", "delete"):
                    result.warnings.append(f"Skipped incomplete text edit on {dest or '?'}")
                    continue
                win_dest = dest.replace("/", "\\")
                cond = (op.get("condition") or ("Mask" if action == "insert" else "Equal")).strip()
                line = op.get("line") or ""
                body = op.get("text_content") or ""
                if action == "insert":
                    where = (op.get("where") or "After").strip()
                    if where.lower() not in ("before", "after"):
                        where = "After"
                    inner = f'<insert where="{_x(where)}" line="{_x(line)}" condition="{_x(cond)}">{_x(body)}</insert>'
                elif action == "replace":
                    inner = f'<replace line="{_x(line)}" condition="{_x(cond)}">{_x(body)}</replace>'
                elif action == "add":
                    inner = f"<add>{_x(body)}</add>"
                else:  # delete
                    inner = f'<delete condition="{_x(cond)}">{_x(body or line)}</delete>'
                node.ops.append(f'<text path="{_x(win_dest)}">{inner}</text>')
                chain_str = " → ".join(_split_archive_chain(op.get("archive", ""), op.get("nested_archives")))
                result.steps.append(f"Edit text ({action}) {chain_str}/{dest}")

            elif kind == "copy_file":
                src = _resolve_source(root, op.get("source", ""))
                if not src:
                    result.warnings.append(f"Skipped missing source file: {op.get('source')}")
                    continue
                dest = _clean_rel(op.get("dest", ""))
                if not dest:
                    continue
                # Strip leading mods/ if targeting mods folder
                if dest.lower().startswith("mods/"):
                    dest_mods = dest[5:]
                    ckey = register_content_file(src)
                    top_level_xml.append(f'<add source="{_x(ckey)}">{_x(dest_mods.replace("/", chr(92)))}</add>')
                    result.steps.append(f"Add mods/{dest_mods}")
                elif oivmod._uses_mods(dest):
                    ckey = register_content_file(src)
                    top_level_xml.append(f'<add source="{_x(ckey)}">{_x(dest.replace("/", chr(92)))}</add>')
                    result.steps.append(f"Add mods/{dest}")
                else:
                    # Loose game-folder file (scripts/, menyooStuff/, root .asi/.ini/.xml)
                    if "/" not in dest and dest.lower() in installer.SKIP_ROOT:
                        result.warnings.append(f"Skipped protected game file: {dest}")
                        continue
                    result.copies.append((src, dest))
                    result.used_sources.add(src)
                    result.steps.append(f"Copy {src.relative_to(root).as_posix()} → {dest}")
        except AiError as e:
            result.warnings.append(str(e))

    # Build the .oiv package if there are any archive or mods/ operations
    content_parts = [node.render() for node in top_archives.values()] + top_level_xml
    if content_parts:
        work = util.cache_dir() / "generated"
        work.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"\W+", "-", title or root.name).strip("-").lower() or "mod"
        oiv_dest = work / f"ai-{slug}.oiv"
        content_xml = "\n".join(content_parts)
        installer.make_oiv(oiv_dest, f"{title or root.name} (AI)", version or "1", author or "Gemini AI",
                           content_xml, oiv_files)
        # Verify Santux's OIV loader can parse what we built
        oivmod.Package.load(oiv_dest)
        result.oiv_path = oiv_dest

    return result


# ---------------------------------------------------------------- public entry point

def convert_mod(plan: installer.Plan, game, title: str = "", version: str = "",
                author: str = "", description: str = "", log=print) -> AiResult:
    """Ask Gemini to analyse plan.root + description and produce an installable .oiv / copies."""
    log("Reading mod files and instructions…")
    prompt = gather_context(plan.root, game, title=title, description=description)

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }

    log("Asking Gemini to build an install plan…")
    resp, used_model = _call_gemini(payload)
    log(f"Received plan from {used_model}")

    raw_text = _extract_text(resp)
    try:
        data = json.loads(raw_text)
    except ValueError as e:
        raise AiError(f"Gemini returned invalid JSON: {e}") from None

    result = compile_plan(data, plan.root, title=title, version=version, author=author)
    if result.oiv_path:
        log(f"Generated .oiv package: {result.oiv_path.name}")
    if result.copies:
        log(f"Planned {len(result.copies)} loose file copy/copies")
    for w in result.warnings:
        log(f"Warning: {w}")
    return result


def apply_ai_result(plan: installer.Plan, result: AiResult) -> installer.Plan:
    """Merge an AiResult into an existing Plan in-place and return it."""
    if result.oiv_path:
        if result.oiv_path not in plan.oivs:
            plan.oivs.append(result.oiv_path)
        if result.oiv_path not in plan.chosen_oivs:
            plan.chosen_oivs.append(result.oiv_path)
    existing_dests = {d.lower() for _, d in plan.copies}
    for src, dest in result.copies:
        if dest.lower() not in existing_dests:
            plan.copies.append((src, dest))
            existing_dests.add(dest.lower())
    if result.used_sources:
        used_rels = {p.relative_to(plan.root).as_posix().lower() for p in result.used_sources if p.is_relative_to(plan.root)}
        plan.skipped = [(rel, why) for rel, why in plan.skipped if rel.lower() not in used_rels]
    return plan
