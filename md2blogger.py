"""
md2blogger.py — Obsidian-flavored Markdown to Blogger-compatible HTML converter.

Reads config.json for inline styles and forbidden tags, parses an Obsidian
note and outputs a clean HTML snippet ready for Blogger's HTML View.

Usage:
    python md2blogger.py input.md [-o output.html] [-c config.json]
                         [--imgfolder [FOLDER]] [--vault PATH]
"""

from __future__ import annotations

__version__ = "1.0"

import argparse
import copy
import dataclasses
import html
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from urllib.parse import quote, unquote, urlsplit

import nh3
from bs4 import BeautifulSoup, NavigableString, Tag
from bs4.element import PreformattedString
from markdown_it import MarkdownIt
from markdown_it.common.utils import escapeHtml
from markdown_it.rules_block import StateBlock
from markdown_it.rules_core import StateCore
from markdown_it.rules_inline import StateInline
from markdown_it.token import Token
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin


# ---------------------------------------------------------------------------
# Defaults (config.json holds the same values; user files are merged over these)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: dict = {
    "forbidden_tags": [
        "html", "head", "body", "meta", "link", "title",
        "style", "script",
        "header", "footer", "nav", "main", "section", "article", "aside",
        "col", "colgroup",
        "form", "input", "textarea", "select", "button",
        "iframe", "embed", "object",
        "svg", "canvas", "video", "audio",
        "base", "template", "slot",
    ],
    "allow_raw_html": True,
    "styles": {
        "h1": "font-family: verdana, sans-serif; color: #333; font-size: 2em; margin-top: 1em; margin-bottom: 0.5em;",
        "h2": "font-family: verdana, sans-serif; color: #444; font-size: 1.5em; margin-top: 1em; margin-bottom: 0.5em;",
        "h3": "font-family: verdana, sans-serif; color: #555; font-size: 1.17em; margin-top: 1em; margin-bottom: 0.5em;",
        "h4": "font-family: verdana, sans-serif; color: #555; font-size: 1em; margin-top: 1em; margin-bottom: 0.5em;",
        "h5": "font-family: verdana, sans-serif; color: #555; font-size: 0.83em; margin-top: 1em; margin-bottom: 0.5em;",
        "h6": "font-family: verdana, sans-serif; color: #555; font-size: 0.75em; margin-top: 1em; margin-bottom: 0.5em;",
        "p": "font-family: verdana, sans-serif; line-height: 1.6; color: #333; margin-bottom: 1em;",
        "strong": "font-weight: bold;",
        "em": "font-style: italic;",
        "a": "color: #1a73e8; text-decoration: underline;",
        "code": "font-family: 'Courier New', monospace; background-color: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-size: 0.9em;",
        "pre": "margin: 0; white-space: pre-wrap; word-wrap: break-word;",
        "blockquote": "border-left: 4px solid #ccc; padding: 10px 15px; color: #666; margin: 1em 0; font-family: verdana, sans-serif;",
        "table": "border-collapse: collapse; width: 100%; margin: 1em 0; font-family: verdana, sans-serif;",
        "thead": "",
        "tbody": "",
        "tr": "",
        "th": "border: 1px solid #ddd; padding: 8px 12px; background-color: #f2f2f2; text-align: left; font-weight: bold; color: #333;",
        "td": "border: 1px solid #ddd; padding: 8px 12px; color: #333;",
        "img": "max-width: 100%; height: auto; display: block; margin: 1em 0;",
        "ul": "padding-left: 20px; margin-bottom: 1em; font-family: verdana, sans-serif; color: #333;",
        "ol": "padding-left: 20px; margin-bottom: 1em; font-family: verdana, sans-serif; color: #333;",
        "li": "margin-bottom: 5px; line-height: 1.6;",
        "hr": "border: none; border-top: 1px solid #ccc; margin: 20px 0;",
        "del": "text-decoration: line-through; color: #999;",
        "s": "text-decoration: line-through; color: #999;",
        "sup": "font-size: 0.75em; vertical-align: super;",
        "sub": "font-size: 0.75em; vertical-align: sub;",
        "mark": "background-color: #fff3cd; padding: 2px 4px;",
        "br": "",
        "div": "",
        "span": "",
        "details": "",
        "summary": "cursor: pointer;",
        ".callout": "background-color: rgba({color}, 0.1); border-radius: 4px; padding: 12px 12px 12px 24px; margin: 1em 0; font-family: verdana, sans-serif;",
        ".callout-title": "font-weight: 600; color: rgb({color});",
        ".callout-content": "margin-top: 0.5em;",
        ".highlight-red": "background-color: rgba(233, 49, 71, 0.25);",
        ".highlight-orange": "background-color: rgba(236, 117, 0, 0.25);",
        ".highlight-yellow": "background-color: rgba(224, 172, 0, 0.25);",
        ".highlight-green": "background-color: rgba(8, 185, 78, 0.25);",
        ".highlight-blue": "background-color: rgba(8, 109, 221, 0.25);",
        ".highlight-purple": "background-color: rgba(120, 82, 238, 0.25);",
        ".tag": "background-color: rgba(138, 92, 245, 0.1); color: #8a5cf5; border-radius: 2em; padding: 1px 8px; font-size: 0.875em; white-space: nowrap;",
        ".internal-link": "",
        ".task": "list-style-type: none;",
        ".task-checkbox": "margin-right: 6px;",
        ".task-done": "text-decoration: line-through; color: #999;",
        ".embed": "border-left: 2px solid #8a5cf5; padding-left: 1em; margin: 1em 0;",
        ".math": "",
        ".math-block": "overflow-x: auto; margin: 1em 0; text-align: center;",
        ".footnote-ref": "",
        ".footnotes-list": "font-size: 0.9em; color: #555;",
        ".footnote-backref": "text-decoration: none;",
    },
    "code_block_wrapper": "<div style=\"background-color: #f4f4f4; padding: 15px; border: 1px solid #ddd; border-radius: 4px; overflow-x: auto; margin: 1em 0;\">{content}</div>",
    "callouts": {
        "default_type": "note",
        "types": {
            "note": {"color": "8, 109, 221", "icon": "✏️"},
            "abstract": {"color": "0, 191, 188", "icon": "📋"},
            "info": {"color": "8, 109, 221", "icon": "ℹ️"},
            "todo": {"color": "8, 109, 221", "icon": "☑️"},
            "tip": {"color": "0, 191, 188", "icon": "🔥"},
            "success": {"color": "8, 185, 78", "icon": "✅"},
            "question": {"color": "236, 117, 0", "icon": "❓"},
            "warning": {"color": "236, 117, 0", "icon": "⚠️"},
            "failure": {"color": "233, 49, 71", "icon": "❌"},
            "danger": {"color": "233, 49, 71", "icon": "⚡"},
            "bug": {"color": "233, 49, 71", "icon": "🐞"},
            "example": {"color": "120, 82, 238", "icon": "📑"},
            "quote": {"color": "158, 158, 158", "icon": "💬"},
        },
        "aliases": {
            "summary": "abstract", "tldr": "abstract",
            "hint": "tip", "important": "tip",
            "check": "success", "done": "success",
            "help": "question", "faq": "question",
            "caution": "warning", "attention": "warning",
            "fail": "failure", "missing": "failure",
            "error": "danger",
            "cite": "quote",
        },
    },
    "tasks": {
        "unchecked": "☐",
        "checked": "☑",
    },
    "obsidian": {
        "image_base_url": "",
        "image_extension_default": ".png",
        "strict_line_breaks": True,
        "wikilink_url_template": "",
        "tags": "label",
        "math": "mathjax",
    },
}

TAG_MODES = ("label", "text", "remove")
MATH_MODES = ("mathjax", "text")

# Obsidian's accepted image formats, and attachments that are linked instead
IMAGE_EXTS = frozenset({".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"})
ATTACHMENT_EXTS = frozenset({
    ".pdf",
    ".mp3", ".wav", ".m4a", ".ogg", ".3gp", ".flac", ".webm",
    ".mp4", ".ogv", ".mov", ".mkv",
})
UNRENDERABLE_EXTS = frozenset({".canvas", ".base"})

HIGHLIGHT_EMOJI = {
    "🔴": "red", "🟠": "orange", "🟡": "yellow",
    "🟢": "green", "🔵": "blue", "🟣": "purple",
}

DEFAULT_IMGFOLDER = "md2blg"
MAX_EMBED_DEPTH = 3
SETTINGS_ENV = "MD2BLOGGER_SETTINGS"

# ---------------------------------------------------------------------------
# Sanitizer allowlist. forbidden_tags in the config can only remove tags from
# this set; anything outside it never reaches the output.
# ---------------------------------------------------------------------------

SAFE_TAGS = frozenset({
    "a", "abbr", "article", "aside", "b", "bdi", "bdo", "blockquote", "br",
    "caption", "cite", "code", "col", "colgroup", "dd", "del", "details", "dfn",
    "div", "dl", "dt", "em", "figcaption", "figure", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "i", "img", "ins",
    "kbd", "li", "main", "mark", "nav", "ol", "p", "pre", "q", "rp", "rt",
    "ruby", "s", "samp", "section", "small", "span", "strike", "strong", "sub",
    "summary", "sup", "table", "tbody", "td", "tfoot", "th", "thead", "time",
    "tr", "u", "ul", "var", "wbr",
})

# Removed together with everything inside them
REMOVE_WITH_CONTENT = frozenset({
    "script", "style", "template", "noscript", "textarea", "select",
    "svg", "math", "iframe", "object", "title",
})

GENERIC_ATTRS = frozenset({"style", "title", "id", "lang", "dir"})
TAG_ATTRS = {
    "a": {"href", "name"},
    "img": {"src", "alt", "width", "height"},
    "td": {"colspan", "rowspan", "align"},
    "th": {"colspan", "rowspan", "align", "scope"},
    "ol": {"start", "reversed", "type"},
    "li": {"value"},
    "details": {"open"},
    "blockquote": {"cite"},
    "q": {"cite"},
    "del": {"cite", "datetime"},
    "ins": {"cite", "datetime"},
    "col": {"span"},
    "colgroup": {"span"},
    "time": {"datetime"},
}
URL_SCHEMES = frozenset({"http", "https", "mailto"})

# Attributes used between rendering and style injection; removed afterwards
STYLE_HOOK_ATTRS = ("class", "data-color")


class UserError(Exception):
    """A problem the user can fix (bad path, bad config). Printed without a traceback."""


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base. Nested dicts merge; everything else is replaced."""
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _deep_merge(dict(base[key]), value)
        else:
            base[key] = value
    return base


def _normalize_color(value: object, where: str) -> str:
    """Accept '#rrggbb', '#rgb' or 'r, g, b' and return 'r, g, b'."""
    if isinstance(value, str):
        text = value.strip()
        hex_match = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", text)
        if hex_match:
            digits = hex_match.group(1)
            if len(digits) == 3:
                digits = "".join(ch * 2 for ch in digits)
            return ", ".join(str(int(digits[i:i + 2], 16)) for i in (0, 2, 4))
        rgb_match = re.fullmatch(r"(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})", text)
        if rgb_match and all(int(n) <= 255 for n in rgb_match.groups()):
            return ", ".join(rgb_match.groups())
    raise UserError(f"config: {where} must be a colour like \"#086ddd\" or \"8, 109, 221\".")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise UserError(f"config: {message}")


def prepare_config(user_config: dict | None) -> dict:
    """Merge a (possibly partial or 0.9-style) config over the defaults and validate it."""
    _require(user_config is None or isinstance(user_config, dict), "the top level must be a JSON object.")
    config = _deep_merge(copy.deepcopy(DEFAULT_CONFIG), user_config or {})

    forbidden = config["forbidden_tags"]
    _require(isinstance(forbidden, list) and all(isinstance(t, str) for t in forbidden),
             "forbidden_tags must be a list of tag names.")
    config["forbidden_tags"] = [t.strip().lower() for t in forbidden]

    styles = config["styles"]
    _require(isinstance(styles, dict) and all(isinstance(v, str) for v in styles.values()),
             "styles must map tag names (or .class names) to CSS strings.")

    wrapper = config["code_block_wrapper"]
    _require(isinstance(wrapper, str) and "{content}" in wrapper,
             "code_block_wrapper must be a string containing {content}.")
    _require(isinstance(config["allow_raw_html"], bool), "allow_raw_html must be true or false.")

    callouts = config["callouts"]
    _require(isinstance(callouts, dict), "callouts must be an object.")
    _require(isinstance(callouts.get("types"), dict), "callouts.types must be an object.")
    _require(isinstance(callouts.get("aliases"), dict)
             and all(isinstance(k, str) and isinstance(v, str) for k, v in callouts["aliases"].items()),
             "callouts.aliases must map alias names to callout types.")
    _require(isinstance(callouts.get("default_type"), str), "callouts.default_type must be a string.")
    types = {}
    for name, spec in callouts["types"].items():
        _require(isinstance(spec, dict), f"callouts.types.{name} must be an object with color and icon.")
        icon = spec.get("icon", "")
        _require(isinstance(icon, str), f"callouts.types.{name}.icon must be a string.")
        types[name.lower()] = {
            "color": _normalize_color(spec.get("color"), f"callouts.types.{name}.color"),
            "icon": icon,
        }
    callouts["types"] = types
    callouts["aliases"] = {k.lower(): v.lower() for k, v in callouts["aliases"].items()}
    callouts["default_type"] = callouts["default_type"].lower()

    tasks = config["tasks"]
    _require(isinstance(tasks, dict) and isinstance(tasks.get("unchecked"), str)
             and isinstance(tasks.get("checked"), str),
             "tasks must contain the strings unchecked and checked.")

    obs = config["obsidian"]
    _require(isinstance(obs, dict), "obsidian must be an object.")
    for key in ("image_base_url", "image_extension_default", "wikilink_url_template"):
        _require(isinstance(obs.get(key), str), f"obsidian.{key} must be a string.")
    _require(isinstance(obs.get("strict_line_breaks"), bool), "obsidian.strict_line_breaks must be true or false.")
    _require(obs.get("tags") in TAG_MODES, f"obsidian.tags must be one of {', '.join(TAG_MODES)}.")
    _require(obs.get("math") in MATH_MODES, f"obsidian.math must be one of {', '.join(MATH_MODES)}.")
    return config


def load_config(config_path: str = "config.json") -> dict:
    """Load config.json, merge it over the defaults and validate it."""
    path = Path(config_path)
    if not path.is_file():
        raise UserError(f"config file '{config_path}' not found.")
    try:
        user_config = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise UserError(
            f"config file '{config_path}' is not valid JSON "
            f"(line {exc.lineno}, column {exc.colno}): {exc.msg}."
        ) from None
    except OSError as exc:
        raise UserError(f"could not read config file '{config_path}': {exc.strerror}.") from None
    return prepare_config(user_config)


# ---------------------------------------------------------------------------
# Remembered settings (the Obsidian vault location)
# ---------------------------------------------------------------------------

def settings_file() -> Path:
    """Per-user settings file, outside the project so local paths never reach git."""
    override = os.environ.get(SETTINGS_ENV)
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "Md2Blogger" / "settings.json"


def load_settings() -> dict:
    try:
        data = json.loads(settings_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_settings(settings: dict) -> None:
    path = settings_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError as exc:
        raise UserError(f"could not save settings to '{path}': {exc.strerror}.") from None


# ---------------------------------------------------------------------------
# Vault, file lookup and image export
# ---------------------------------------------------------------------------

class Vault:
    """An Obsidian vault folder with a lazily built, case-insensitive file index."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self._by_name: dict[str, list[Path]] | None = None

    def _index(self) -> dict[str, list[Path]]:
        if self._by_name is None:
            by_name: dict[str, list[Path]] = {}
            for dirpath, dirnames, filenames in os.walk(self.root):
                # Skip .obsidian, .trash, .git and other hidden folders
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                for name in filenames:
                    by_name.setdefault(name.lower(), []).append(Path(dirpath) / name)
            self._by_name = by_name
        return self._by_name

    def find_by_name(self, link: str, near: Path | None) -> Path | None:
        """Resolve a link the way Obsidian does: by file name, or by the end of its path."""
        wanted = link.replace("\\", "/").strip("/").lower()
        name = wanted.rsplit("/", 1)[-1]
        candidates = [
            p for p in self._index().get(name, [])
            if p.as_posix().lower().endswith("/" + wanted)
        ]
        if not candidates:
            return None

        def rank(path: Path) -> tuple:
            same_folder = near is not None and path.parent == near
            return (0 if same_folder else 1, len(path.relative_to(self.root).parts), path.as_posix().lower())

        return min(candidates, key=rank)


def find_vault_root(start: Path) -> Path | None:
    """Return the nearest folder at or above start that contains .obsidian."""
    start = start.resolve()
    for folder in (start, *start.parents):
        if (folder / ".obsidian").is_dir():
            return folder
    return None


def path_to_url(path: str) -> str:
    """Percent-encode a relative file path for use in src/href."""
    return quote(path.replace("\\", "/"), safe="/")


class ImageExporter:
    """Copies images into one folder, mirroring the vault's folder structure."""

    def __init__(self, folder: Path, output_dir: Path):
        self.folder = Path(folder).resolve()
        self.output_dir = Path(output_dir).resolve()
        self._copied: dict[Path, Path] = {}   # source -> destination
        self._owner: dict[Path, Path] = {}    # destination -> source

    @property
    def count(self) -> int:
        return len(self._copied)

    def export(self, source: Path, ctx: Context) -> str:
        """Copy source (once) and return the URL to use in the HTML."""
        source = source.resolve()
        dest = self._copied.get(source)
        if dest is None:
            dest = self._free_destination(self.folder / ctx.relative_location(source), source)
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
            except OSError as exc:
                raise UserError(f"could not copy image '{source}' to '{dest}': {exc.strerror}.") from None
            self._copied[source] = dest
            self._owner[dest] = source
        try:
            relative = os.path.relpath(dest, self.output_dir)
        except ValueError:
            raise UserError("--imgfolder must be on the same drive as the output file.") from None
        return path_to_url(relative)

    def _free_destination(self, dest: Path, source: Path) -> Path:
        """Keep the original name unless a different image already took it."""
        candidate, n = dest, 2
        while self._owner.get(candidate, source) != source:
            candidate = dest.with_name(f"{dest.stem}_{n}{dest.suffix}")
            n += 1
        return candidate


def unique_folder(parent: Path, name: str) -> Path:
    """Return parent/name, or parent/name_2, name_3 ... if that already exists."""
    candidate, n = parent / name, 2
    while candidate.exists():
        candidate = parent / f"{name}_{n}"
        n += 1
    return candidate


# ---------------------------------------------------------------------------
# Conversion context
# ---------------------------------------------------------------------------

@dataclass
class Context:
    """Everything the Markdown plugins need for one conversion."""

    config: dict
    note_path: Path | None = None
    vault: Vault | None = None
    exporter: ImageExporter | None = None
    warnings: list[str] = field(default_factory=list)
    depth: int = 0
    stack: tuple[Path, ...] = ()
    allowed_roots: tuple[Path, ...] = ()
    home_dir: Path | None = None

    @property
    def obsidian(self) -> dict:
        return self.config["obsidian"]

    @property
    def note_dir(self) -> Path | None:
        return self.note_path.parent if self.note_path else None

    @property
    def note_name(self) -> str | None:
        return self.note_path.stem if self.note_path else None

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def child(self, note_path: Path) -> Context:
        return dataclasses.replace(
            self, note_path=note_path, depth=self.depth + 1, stack=self.stack + (note_path,)
        )

    def is_allowed(self, path: Path) -> bool:
        """Only files inside the vault or the converted note's folder may be used."""
        resolved = path.resolve()
        return any(resolved.is_relative_to(root) for root in self.allowed_roots)

    def relative_location(self, source: Path) -> Path:
        if self.vault and source.is_relative_to(self.vault.root):
            return source.relative_to(self.vault.root)
        if self.home_dir and source.is_relative_to(self.home_dir):
            return source.relative_to(self.home_dir)
        return Path(source.name)

    def locate(self, link: str) -> Path | None:
        """Find the file a link points to: next to the note, from the vault root, then by name."""
        link = link.replace("\\", "/").strip()
        if not link or link.startswith("/") or re.match(r"^[A-Za-z]:", link):
            return None
        for root in (self.note_dir, self.vault.root if self.vault else None):
            if root is None:
                continue
            candidate = root / link
            if candidate.is_file() and self.is_allowed(candidate):
                return candidate.resolve()
        if self.vault:
            found = self.vault.find_by_name(link, self.note_dir)
            if found and self.is_allowed(found):
                return found.resolve()
        return None


def _ctx(env: dict) -> Context:
    ctx = env.get("md2b") if isinstance(env, dict) else None
    if ctx is None:
        ctx = Context(config=prepare_config({}))
        if isinstance(env, dict):
            env["md2b"] = ctx
    return ctx


# ---------------------------------------------------------------------------
# Helpers shared by the Markdown plugins
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Heading text -> id. Used for heading ids and for links to headings."""
    text = re.sub(r"[^\w\s-]", "", text.strip().lower())
    return re.sub(r"[\s]+", "-", text).strip("-")


def fragment_id(fragment: str) -> str:
    """Turn an Obsidian link fragment (Heading, ^block-id) into an element id."""
    fragment = unquote(fragment).split("#")[-1].strip()
    if fragment.startswith("^"):
        return fragment[1:]
    return slugify(fragment)


SIZE_RE = re.compile(r"(\d+)(?:x(\d+))?")


def _size_attrs(size: str | None) -> str:
    if not size:
        return ""
    match = SIZE_RE.fullmatch(size)
    if not match:
        return ""
    out = f' width="{match.group(1)}"'
    if match.group(2):
        out += f' height="{match.group(2)}"'
    return out


def _parse_wikilink(inner: str, embed: bool) -> dict:
    inner = inner.replace("\\|", "|")
    target_part, _, alias = inner.partition("|")
    target, _, subpath = target_part.partition("#")
    meta = {
        "embed": embed,
        "target": target.strip(),
        "subpath": subpath.strip(),
        "alias": alias.strip(),
        "size": None,
        "alt": "",
    }
    if embed and alias:
        alt_parts = []
        for part in (p.strip() for p in alias.split("|")):
            if meta["size"] is None and SIZE_RE.fullmatch(part):
                meta["size"] = part
            else:
                alt_parts.append(part)
        meta["alt"] = "|".join(alt_parts)
    return meta


def _strip_md(name: str) -> str:
    return name[:-3] if name.lower().endswith(".md") else name


def classify_embed(target: str, ctx: Context) -> str:
    """image, file (linked attachment), note (transcluded) or other (shown as text)."""
    ext = PurePosixPath(target).suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in ATTACHMENT_EXTS:
        return "file"
    if ext in UNRENDERABLE_EXTS:
        return "other"
    if ext == ".md":
        return "note"
    if ctx.locate(target + ".md"):
        return "note"
    default_ext = ctx.obsidian["image_extension_default"]
    if ext == "" and default_ext:
        # With a vault we can check what exists; without one keep the 0.9 behaviour,
        # where ![[name]] is an image with the default extension.
        if ctx.vault is None or ctx.locate(target + default_ext):
            return "image"
    return "note"


def _internal_link_html(meta: dict, ctx: Context) -> str:
    note = _strip_md(meta["target"])
    subpath = meta["subpath"]
    same_note = not note or (ctx.note_name is not None and note.lower() == ctx.note_name.lower())
    if meta["alias"] and not meta["embed"]:
        display = meta["alias"]
    elif same_note and subpath:
        display = subpath.split("#")[-1]
    elif subpath:
        display = f"{note} > {subpath.split('#')[-1]}"
    else:
        display = note

    href = None
    if same_note and subpath:
        href = "#" + fragment_id(subpath)
    elif not same_note and ctx.obsidian["wikilink_url_template"]:
        href = ctx.obsidian["wikilink_url_template"].replace("{name}", quote(note, safe=""))
    if href:
        return f'<a href="{escapeHtml(href)}" class="internal-link">{escapeHtml(display)}</a>'
    return f'<span class="internal-link">{escapeHtml(display)}</span>'


def _wiki_image_html(meta: dict, ctx: Context) -> str:
    target = meta["target"]
    if not PurePosixPath(target).suffix:
        target += ctx.obsidian["image_extension_default"]
    alt = meta["alt"] or PurePosixPath(target.replace("\\", "/")).name
    src = None
    if ctx.exporter:
        found = ctx.locate(target)
        if found and found.suffix.lower() in IMAGE_EXTS:
            src = ctx.exporter.export(found, ctx)
        else:
            ctx.warn(f"Image '{target}' was not found, so it was not copied.")
    if src is None:
        src = ctx.obsidian["image_base_url"] + path_to_url(target)
    return f'<img src="{escapeHtml(src)}" alt="{escapeHtml(alt)}"{_size_attrs(meta["size"])}>'


def _attachment_html(meta: dict, ctx: Context) -> str:
    target = meta["target"]
    display = meta["alt"] or PurePosixPath(target.replace("\\", "/")).name
    href = ctx.obsidian["image_base_url"] + path_to_url(target)
    return f'<a href="{escapeHtml(href)}">{escapeHtml(display)}</a>'


def _export_markdown_image(src: str, ctx: Context) -> str | None:
    """Copy a local image used with ![alt](path) syntax. External URLs are left alone."""
    parts = urlsplit(src)
    if parts.scheme or parts.netloc or src.startswith(("/", "#")):
        return None
    path_text = unquote(parts.path)
    if not path_text:
        return None
    found = ctx.locate(path_text)
    if found is None:
        if PurePosixPath(path_text).suffix.lower() in IMAGE_EXTS:
            ctx.warn(f"Image '{path_text}' was not found, so it was not copied.")
        return None
    if found.suffix.lower() not in IMAGE_EXTS:
        return None
    return ctx.exporter.export(found, ctx)


# ---------------------------------------------------------------------------
# Markdown-it rules for Obsidian syntax
# ---------------------------------------------------------------------------

def _comment_block(state: StateBlock, start_line: int, end_line: int, silent: bool) -> bool:
    """%% block comments %% that start at the beginning of a line."""
    if state.is_code_block(start_line):
        return False
    pos = state.bMarks[start_line] + state.tShift[start_line]
    if not state.src.startswith("%%", pos):
        return False
    limit = state.eMarks[end_line - 1]
    close = state.src.find("%%", pos + 2, limit)
    if close == -1:
        # Obsidian hides the rest of the note when a comment is never closed
        if not silent:
            state.line = end_line
        return True
    line = start_line
    while line < end_line - 1 and state.eMarks[line] < close:
        line += 1
    remainder = state.src[close + 2:state.eMarks[line]].strip()
    if line == start_line and remainder:
        return False  # an inline comment at the start of a paragraph
    if silent:
        return True
    state.line = line + 1
    if remainder:
        token = state.push("paragraph_open", "p", 1)
        token.map = [line, line + 1]
        token = state.push("inline", "", 0)
        token.content = remainder
        token.map = [line, line + 1]
        token.children = []
        state.push("paragraph_close", "p", -1)
    return True


def _comment_inline(state: StateInline, silent: bool) -> bool:
    """%%inline comments%% on one line."""
    src, pos = state.src, state.pos
    if not src.startswith("%%", pos):
        return False
    end = src.find("%%", pos + 2, state.posMax)
    if end == -1 or "\n" in src[pos + 2:end]:
        return False
    state.pos = end + 2
    return True


def _highlight_inline(state: StateInline, silent: bool) -> bool:
    """==highlight==, with optional colour emoji: ==🔴red==."""
    src, start, maximum = state.src, state.pos, state.posMax
    if not src.startswith("==", start) or start + 2 >= maximum:
        return False
    if (start > 0 and src[start - 1] == "=") or src[start + 2] in " \t\n=":
        return False

    content_start = start + 2
    found = -1
    state.pos = content_start
    while state.pos < maximum:
        pos = state.pos
        if src.startswith("==", pos) and src[pos - 1] not in " \t\n" and not src.startswith("===", pos):
            found = pos
            break
        state.md.inline.skipToken(state)
    state.pos = start
    if found == -1:
        return False

    if not silent:
        color = HIGHLIGHT_EMOJI.get(src[content_start])
        if color:
            content_start += 1
            if content_start < found and src[content_start] == "\ufe0f":
                content_start += 1
        token = state.push("mark_open", "mark", 1)
        token.markup = "=="
        if color:
            token.attrSet("class", f"highlight-{color}")
        state.pos = content_start
        state.posMax = found
        state.md.inline.tokenize(state)
        state.posMax = maximum
        token = state.push("mark_close", "mark", -1)
        token.markup = "=="
    state.pos = found + 2
    return True


def _wikilink_inline(state: StateInline, silent: bool) -> bool:
    """[[links]] and ![[embeds]]."""
    src, pos = state.src, state.pos
    embed = src.startswith("![[", pos)
    if not embed and not src.startswith("[[", pos):
        return False
    start = pos + (3 if embed else 2)
    end = src.find("]]", start, state.posMax)
    if end == -1:
        return False
    inner = src[start:end]
    if not inner.strip() or "\n" in inner or "[[" in inner:
        return False
    if not silent:
        token = state.push("obsidian_wikilink", "", 0)
        token.content = inner
        token.meta = _parse_wikilink(inner, embed)
    state.pos = end + 2
    return True


TAG_RE = re.compile(r"#([\w/-]+)")


def _tag_inline(state: StateInline, silent: bool) -> bool:
    """#tags (must follow whitespace and contain something other than digits)."""
    src, pos = state.src, state.pos
    if src[pos] != "#" or (pos > 0 and not src[pos - 1].isspace()):
        return False
    match = TAG_RE.match(src, pos, state.posMax)
    if not match or not re.search(r"[^\d/]", match.group(1)):
        return False
    if not silent:
        token = state.push("obsidian_tag", "", 0)
        token.content = match.group(1)
    state.pos = match.end()
    return True


CALLOUT_RE = re.compile(r"\[!([^\]\s|]+)(?:\|[^\]]*)?\]([+-]?)[ \t]*(.*)")


def _find_close(tokens: list[Token], start: int, close_type: str) -> int | None:
    level = tokens[start].level
    for j in range(start + 1, len(tokens)):
        if tokens[j].type == close_type and tokens[j].level == level:
            return j
    return None


def _callouts_core(state: StateCore) -> None:
    """> [!type]+/- Title  ->  styled box (<details> when foldable)."""
    ctx = _ctx(state.env)
    callouts = ctx.config["callouts"]
    forbidden = set(ctx.config["forbidden_tags"])
    tokens = state.tokens
    i = 0
    while i < len(tokens):
        if (tokens[i].type == "blockquote_open" and i + 2 < len(tokens)
                and tokens[i + 1].type == "paragraph_open" and tokens[i + 2].type == "inline"):
            first, _, rest = tokens[i + 2].content.partition("\n")
            match = CALLOUT_RE.fullmatch(first.strip())
            close = _find_close(tokens, i, "blockquote_close") if match else None
            if match and close is not None:
                raw_type, fold, title = match.groups()
                kind = callouts["aliases"].get(raw_type.lower(), raw_type.lower())
                if kind not in callouts["types"]:
                    kind = callouts["default_type"]
                spec = callouts["types"].get(kind) or {"color": "8, 109, 221", "icon": ""}
                title = title.strip() or raw_type[:1].upper() + raw_type[1:].lower()
                foldable = fold in ("+", "-") and not {"details", "summary"} & forbidden

                level = tokens[i].level
                box_tag = "details" if foldable else "div"
                title_tag = "summary" if foldable else "div"
                hooks = {"data-color": spec["color"]}
                box_open = Token("callout_open", box_tag, 1, attrs={"class": "callout", **hooks},
                                 level=level, block=True, map=tokens[i].map)
                if foldable and fold == "+":
                    box_open.attrs["open"] = ""
                title_text = f"{spec['icon']} {title}" if spec["icon"] else title
                new_tokens = [
                    box_open,
                    Token("callout_title_open", title_tag, 1,
                          attrs={"class": "callout-title", **hooks}, level=level + 1, block=True),
                    Token("inline", "", 0, content=title_text, children=[], level=level + 2,
                          map=tokens[i].map),
                    Token("callout_title_close", title_tag, -1, level=level + 1, block=True),
                ]
                body = tokens[i + 1:close]
                if rest.strip():
                    body[1].content = rest
                else:
                    body = body[3:]
                if body:
                    new_tokens.append(Token("callout_content_open", "div", 1,
                                            attrs={"class": "callout-content", **hooks},
                                            level=level + 1, block=True))
                    new_tokens.extend(body)
                    new_tokens.append(Token("callout_content_close", "div", -1, level=level + 1, block=True))
                new_tokens.append(Token("callout_close", box_tag, -1, level=level, block=True))
                tokens[i:close + 1] = new_tokens
        i += 1


def _fix_link_targets(tokens: list[Token]) -> None:
    """[text](#^block-id) and [text](#Heading%20name) -> the ids we generate."""
    for token in tokens:
        if token.type != "inline" or not token.children:
            continue
        for child in token.children:
            if child.type == "link_open":
                href = str(child.attrGet("href") or "")
                if href.startswith("#") and len(href) > 1:
                    child.attrSet("href", "#" + fragment_id(href[1:]))


TASK_RE = re.compile(r"\[(.)\](?=\s|$)")


def _apply_tasks(tokens: list[Token], ctx: Context) -> None:
    """- [ ] todo / - [x] done; any character other than a space marks a task done."""
    glyphs = ctx.config["tasks"]
    for i, token in enumerate(tokens):
        if (token.type != "inline" or i < 2 or not token.children
                or tokens[i - 1].type != "paragraph_open" or tokens[i - 2].type != "list_item_open"):
            continue
        first = token.children[0]
        match = TASK_RE.match(first.content) if first.type == "text" else None
        if not match:
            continue
        done = match.group(1) != " "
        first.content = first.content[match.end():].lstrip(" ")
        item = tokens[i - 2]
        item.attrJoin("class", "task")
        if done:
            item.attrJoin("class", "task-done")
        token.children[0:0] = [
            Token("span_open", "span", 1, attrs={"class": "task-checkbox"}),
            Token("text", "", 0, content=glyphs["checked" if done else "unchecked"]),
            Token("span_close", "span", -1),
        ]


BLOCK_ID_RE = re.compile(r"(?:^|[ \t]+)\^([A-Za-z0-9_-]+)[ \t]*$")


def _anchor(block_id: str) -> Token:
    return Token("obsidian_anchor", "span", 0, meta={"id": block_id})


def _apply_block_ids(tokens: list[Token]) -> None:
    """Hide ^block-id markers and give the block that id, so links can reach it."""
    for i, token in enumerate(tokens):
        if token.type != "inline" or not token.children or i == 0:
            continue
        last = token.children[-1]
        match = BLOCK_ID_RE.search(last.content) if last.type == "text" else None
        if not match:
            continue
        block_id = match.group(1)
        last.content = last.content[:match.start()]
        opener = tokens[i - 1]
        only_id = all(
            child.type in ("softbreak", "hardbreak") or (child.type == "text" and not child.content.strip())
            for child in token.children
        )

        if only_id and opener.type == "paragraph_open" and i + 1 < len(tokens):
            # ^id on its own line names the block above it
            opener.hidden = True
            tokens[i + 1].hidden = True
            token.children = [_anchor(block_id)]
            if i >= 2 and tokens[i - 2].nesting == -1:
                close = tokens[i - 2]
                open_type = close.type[:-len("_close")] + "_open" if close.type.endswith("_close") else ""
                for j in range(i - 3, -1, -1):
                    if tokens[j].type == open_type and tokens[j].level == close.level:
                        if open_type == "heading_open":
                            tokens[j + 1].children = (tokens[j + 1].children or []) + [_anchor(block_id)]
                            token.children = []
                        elif not tokens[j].attrGet("id"):
                            tokens[j].attrSet("id", block_id)
                            token.children = []
                        break
            continue

        if opener.type == "paragraph_open":
            target = opener
            if opener.hidden:  # paragraph inside a tight list item
                for j in range(i - 2, -1, -1):
                    if tokens[j].type == "list_item_open" and tokens[j].level == opener.level - 1:
                        target = tokens[j]
                        break
            if not target.hidden and not target.attrGet("id"):
                target.attrSet("id", block_id)
                continue
        token.children.append(_anchor(block_id))


def _extract_section(text: str, subpath: str) -> str | None:
    """The part of a note that ![[Note#Heading]] or ![[Note#^block-id]] refers to."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for n in range(1, len(lines)):
            if lines[n].strip() in ("---", "..."):
                lines = lines[n + 1:]
                break
    target = subpath.split("#")[-1].strip()

    if target.startswith("^"):
        block_id = re.escape(target[1:])
        for n, line in enumerate(lines):
            if line.strip() == "^" + target[1:]:
                end = n - 1
                while end >= 0 and not lines[end].strip():
                    end -= 1
                start = end
                while start > 0 and lines[start - 1].strip():
                    start -= 1
                return "\n".join(lines[start:end + 1]) if end >= 0 else None
            if re.search(rf"\s\^{block_id}\s*$", line):
                if re.match(r"\s*([-*+]|\d+[.)])\s", line):
                    return line.strip()
                start = n
                while start > 0 and lines[start - 1].strip():
                    start -= 1
                return "\n".join(lines[start:n + 1])
        return None

    wanted = " ".join(target.lower().split())
    in_fence = None
    start = level = None
    for n, line in enumerate(lines):
        fence = re.match(r"\s{0,3}(`{3,}|~{3,})", line)
        if fence:
            marker = fence.group(1)[0]
            if in_fence is None:
                in_fence = marker
            elif in_fence == marker:
                in_fence = None
            continue
        if in_fence:
            continue
        heading = re.match(r"\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if not heading:
            continue
        this_level = len(heading.group(1))
        if start is None:
            title = BLOCK_ID_RE.sub("", heading.group(2))
            if " ".join(title.lower().split()) == wanted:
                start, level = n, this_level
        elif this_level <= level:
            return "\n".join(lines[start:n])
    return "\n".join(lines[start:]) if start is not None else None


def _transclude(state: StateCore, meta: dict, ctx: Context) -> str | None:
    target = meta["target"]
    name = target if target.lower().endswith(".md") else target + ".md"
    path = ctx.locate(name)
    if path is None:
        hint = "" if ctx.vault else " No Obsidian vault is known; use --vault PATH."
        ctx.warn(f"Embedded note '{target}' was not found.{hint}")
        return None
    if path in ctx.stack or ctx.depth >= MAX_EMBED_DEPTH:
        ctx.warn(f"Skipped embedding '{target}' inside itself.")
        return None
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        ctx.warn(f"Embedded note '{target}' could not be read.")
        return None
    if meta["subpath"]:
        section = _extract_section(text, meta["subpath"])
        if section is None:
            ctx.warn(f"'#{meta['subpath']}' was not found in embedded note '{target}'.")
            return None
        text = section
    child_env = {"md2b": ctx.child(path), "docId": slugify(path.stem)}
    inner = state.md.render(text, child_env)
    return f'<div class="embed">\n{inner}</div>\n'


def _apply_embeds(state: StateCore, ctx: Context) -> None:
    """Classify ![[embeds]] and transclude notes that stand alone in a paragraph."""
    tokens = state.tokens
    result: list[Token] = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.type == "inline" and token.children:
            for child in token.children:
                if child.type == "obsidian_wikilink" and child.meta["embed"]:
                    child.meta["kind"] = classify_embed(child.meta["target"], ctx)
            significant = [
                c for c in token.children
                if not (c.type in ("softbreak", "hardbreak") or (c.type == "text" and not c.content.strip()))
            ]
            if (result and result[-1].type == "paragraph_open" and len(significant) == 1
                    and significant[0].type == "obsidian_wikilink"
                    and significant[0].meta.get("kind") == "note"):
                block_html = _transclude(state, significant[0].meta, ctx)
                if block_html is not None:
                    result.pop()  # paragraph_open
                    result.append(Token("obsidian_embed_block", "", 0, content=block_html, block=True))
                    i += 2  # skip the inline token and paragraph_close
                    continue
        result.append(token)
        i += 1
    state.tokens[:] = result


def _obsidian_core(state: StateCore) -> None:
    ctx = _ctx(state.env)
    _fix_link_targets(state.tokens)
    _apply_tasks(state.tokens, ctx)
    _apply_block_ids(state.tokens)
    _apply_embeds(state, ctx)


# --- Render rules ---------------------------------------------------------

def _render_nothing(self, tokens, idx, options, env) -> str:
    return ""


def _render_wikilink(self, tokens, idx, options, env) -> str:
    meta = tokens[idx].meta
    ctx = _ctx(env)
    if meta["embed"]:
        kind = meta.get("kind") or classify_embed(meta["target"], ctx)
        if kind == "image":
            return _wiki_image_html(meta, ctx)
        if kind == "file":
            return _attachment_html(meta, ctx)
    return _internal_link_html(meta, ctx)


def _render_tag(self, tokens, idx, options, env) -> str:
    mode = _ctx(env).obsidian["tags"]
    text = escapeHtml("#" + tokens[idx].content)
    if mode == "remove":
        return ""
    if mode == "text":
        return text
    return f'<span class="tag">{text}</span>'


def _render_anchor(self, tokens, idx, options, env) -> str:
    return f'<span id="{escapeHtml(tokens[idx].meta["id"])}"></span>'


def _render_embed_block(self, tokens, idx, options, env) -> str:
    return tokens[idx].content


def _render_image(self, tokens, idx, options, env) -> str:
    """Standard ![alt](src), plus Obsidian sizing: ![alt|100](src), ![100x50](src)."""
    token = tokens[idx]
    ctx = _ctx(env)
    alt = self.renderInlineAsText(token.children or [], options, env)
    width = height = None
    match = re.fullmatch(r"(.*?)\|(\d+)(?:x(\d+))?", alt) or re.fullmatch(r"()(\d+)(?:x(\d+))?", alt)
    if match:
        alt, width, height = match.group(1).strip(), match.group(2), match.group(3)
    src = str(token.attrGet("src") or "")
    if ctx.exporter:
        src = _export_markdown_image(src, ctx) or src
    attrs: dict = {"src": src, "alt": alt}
    if token.attrGet("title"):
        attrs["title"] = token.attrGet("title")
    if width:
        attrs["width"] = width
    if height:
        attrs["height"] = height
    token.attrs = attrs
    return self.renderToken(tokens, idx, options, env)


def _math_rule(display: bool):
    """$inline$ and $$display$$ maths: MathJax delimiters, or the LaTeX source as code."""
    def render(self, tokens, idx, options, env) -> str:
        content = str(tokens[idx].content).strip()
        if _ctx(env).obsidian["math"] == "text":
            delim = "$$" if display else "$"
            inner = '<code class="math">' + escapeHtml(delim + content + delim) + "</code>"
        elif display:
            inner = escapeHtml("\\[" + content + "\\]")
        else:
            inner = '<span class="math">' + escapeHtml("\\(" + content + "\\)") + "</span>"
        return f'<div class="math-block">{inner}</div>\n' if display else inner
    return render


def build_markdown(config: dict) -> MarkdownIt:
    """markdown-it with CommonMark, GFM tables/strikethrough and the Obsidian extensions."""
    md = MarkdownIt("commonmark", {
        "html": config["allow_raw_html"],
        "breaks": not config["obsidian"]["strict_line_breaks"],
    })
    md.enable(["table", "strikethrough"])
    # Parse every link so its text is kept; the sanitizer then drops unsafe URLs
    # (javascript:, data:, file: ...) instead of the reader seeing raw Markdown.
    md.validateLink = lambda url: True
    front_matter_plugin(md)
    footnote_plugin(md)
    dollarmath_plugin(md, allow_labels=False, allow_space=False, allow_digits=False, double_inline=True)

    md.block.ruler.before("fence", "obsidian_comment", _comment_block,
                          {"alt": ["paragraph", "reference", "blockquote", "list"]})
    md.inline.ruler.before("strikethrough", "obsidian_comment", _comment_inline)
    md.inline.ruler.before("emphasis", "obsidian_highlight", _highlight_inline)
    md.inline.ruler.before("link", "obsidian_wikilink", _wikilink_inline)
    md.inline.ruler.before("link", "obsidian_tag", _tag_inline)
    md.core.ruler.after("block", "obsidian_callouts", _callouts_core)
    md.core.ruler.after("inline", "obsidian", _obsidian_core)
    anchors_plugin(md, min_level=1, max_level=6, slug_func=slugify)

    md.add_render_rule("front_matter", _render_nothing)
    md.add_render_rule("obsidian_wikilink", _render_wikilink)
    md.add_render_rule("obsidian_tag", _render_tag)
    md.add_render_rule("obsidian_anchor", _render_anchor)
    md.add_render_rule("obsidian_embed_block", _render_embed_block)
    md.add_render_rule("image", _render_image)
    md.add_render_rule("math_inline", _math_rule(display=False))
    md.add_render_rule("math_inline_double", _math_rule(display=True))
    md.add_render_rule("math_block", _math_rule(display=True))
    return md


# ---------------------------------------------------------------------------
# Sanitizing
# ---------------------------------------------------------------------------

def sanitize(html_text: str, config: dict, keep_style_hooks: bool = False) -> str:
    """Allowlist-based cleaning with nh3. Removes scripts, event handlers and unsafe URLs."""
    tags = set(SAFE_TAGS - set(config["forbidden_tags"]))
    generic = set(GENERIC_ATTRS) | (set(STYLE_HOOK_ATTRS) if keep_style_hooks else set())
    attributes = {"*": generic}
    for tag, attrs in TAG_ATTRS.items():
        if tag in tags:
            attributes[tag] = set(attrs)
    return nh3.clean(
        html_text,
        tags=tags,
        clean_content_tags=set(REMOVE_WITH_CONTENT),
        attributes=attributes,
        url_schemes=set(URL_SCHEMES),
        link_rel=None,
        strip_comments=True,
    )


# ---------------------------------------------------------------------------
# Inline style injection
# ---------------------------------------------------------------------------

def inject_styles(html_text: str, config: dict) -> str:
    """Apply config styles as style="..." attributes and wrap code blocks."""
    soup = BeautifulSoup(html_text, "html.parser")
    styles = config["styles"]
    wrapper = config["code_block_wrapper"]

    for pre_tag in soup.find_all("pre"):
        code_tag = pre_tag.find("code")
        if not code_tag:
            continue
        if styles.get("code"):
            code_tag["style"] = styles["code"]
        # Start and end the code on its own line (fixes Blogger's first-line indent quirk)
        raw_code = code_tag.get_text()
        if not raw_code.startswith("\n"):
            raw_code = "\n" + raw_code
        if not raw_code.endswith("\n"):
            raw_code += "\n"
        code_tag.clear()
        code_tag.append(NavigableString(raw_code))
        if styles.get("pre"):
            pre_tag["style"] = styles["pre"]
        for tag in (pre_tag, code_tag):
            tag["data-cb"] = "1"
            for attr in STYLE_HOOK_ATTRS:
                if tag.has_attr(attr):
                    del tag[attr]
        pre_tag.replace_with(BeautifulSoup(wrapper.replace("{content}", str(pre_tag)), "html.parser"))

    # A link whose URL was removed as unsafe is shown as plain text
    for link in soup.find_all("a"):
        if not any(link.get(attr) for attr in ("href", "id", "name")):
            link.unwrap()

    for tag in soup.find_all(True):
        if tag.has_attr("data-cb"):
            del tag["data-cb"]
            continue
        parts = []
        if styles.get(tag.name):
            parts.append(styles[tag.name])
        for cls in tag.get("class") or []:
            if styles.get("." + cls):
                parts.append(styles["." + cls])
        css = " ".join(parts)
        if "{color}" in css:
            css = css.replace("{color}", tag.get("data-color") or "8, 109, 221")
        if tag.get("style"):
            css = f"{css} {tag['style']}".strip()
        if css:
            tag["style"] = css
        for attr in STYLE_HOOK_ATTRS:
            if tag.has_attr(attr):
                del tag[attr]
        if tag.name == "span" and not tag.attrs:
            tag.unwrap()  # nothing left to style or link to
    return str(soup)


# ---------------------------------------------------------------------------
# Pretty-printing
# ---------------------------------------------------------------------------

# Tags that are rendered on their own line (block-level)
BLOCK_TAGS = frozenset({
    "address", "article", "aside", "blockquote", "caption", "dd", "details",
    "div", "dl", "dt", "figcaption", "figure", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "main", "nav",
    "ol", "p", "pre", "section", "summary", "table", "tbody", "td", "tfoot",
    "th", "thead", "tr", "ul",
})
VOID_TAGS = frozenset({"area", "br", "col", "embed", "hr", "img", "input", "source", "track", "wbr"})
_WS_RE = re.compile(r"[ \t\n\r\f]+")  # not \s: that would also collapse &nbsp;


def pretty_print(html_text: str, indent: str = "  ") -> str:
    """Indent HTML for readability. Escapes text and attributes; keeps <pre> as-is."""
    soup = BeautifulSoup(html_text, "html.parser")
    lines: list[str] = []

    def attrs_of(tag: Tag) -> str:
        out = []
        for key, val in tag.attrs.items():
            if isinstance(val, list):
                val = " ".join(val)
            out.append(f' {key}="{html.escape(str(val), quote=True)}"')
        return "".join(out)

    def inline(nodes) -> str:
        parts = []
        for node in nodes:
            if isinstance(node, PreformattedString):  # comments, doctypes, CDATA
                continue
            if isinstance(node, NavigableString):
                parts.append(_WS_RE.sub(" ", html.escape(str(node), quote=False)))
            elif isinstance(node, Tag):
                parts.append(str(node))
        return "".join(parts).strip(" \t\n\r\f")

    def is_block(node) -> bool:
        return isinstance(node, Tag) and node.name in BLOCK_TAGS

    def render_block(tag: Tag, depth: int) -> None:
        pad = indent * depth
        attrs = attrs_of(tag)
        if tag.name in VOID_TAGS:
            lines.append(f"{pad}<{tag.name}{attrs}>")
        elif tag.name == "pre":
            lines.append(pad + str(tag))
        elif not any(is_block(child) for child in tag.children):
            lines.append(f"{pad}<{tag.name}{attrs}>{inline(tag.children)}</{tag.name}>")
        else:
            lines.append(f"{pad}<{tag.name}{attrs}>")
            render_children(tag.children, depth + 1)
            lines.append(f"{pad}</{tag.name}>")

    def render_children(nodes, depth: int) -> None:
        run: list = []
        for node in nodes:
            if is_block(node):
                flush(run, depth)
                run = []
                render_block(node, depth)
            else:
                run.append(node)
        flush(run, depth)

    def flush(run: list, depth: int) -> None:
        text = inline(run)
        if text:
            lines.append(indent * depth + text)

    render_children(soup.children, 0)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def convert(
    md_text: str,
    config: dict,
    *,
    note_path: Path | str | None = None,
    vault: Vault | None = None,
    exporter: ImageExporter | None = None,
    warnings: list[str] | None = None,
) -> str:
    """Full conversion pipeline: parse -> sanitize -> style -> pretty-print -> sanitize."""
    config = prepare_config(config)
    note = Path(note_path).resolve() if note_path else None
    roots = tuple(r for r in (vault.root if vault else None, note.parent if note else None) if r)
    ctx = Context(
        config=config,
        note_path=note,
        vault=vault,
        exporter=exporter,
        warnings=warnings if warnings is not None else [],
        stack=(note,) if note else (),
        allowed_roots=roots,
        home_dir=note.parent if note else None,
    )
    env: dict = {"md2b": ctx}
    if note:
        env["docId"] = slugify(note.stem)

    # Step 1: Markdown (with Obsidian extensions) -> raw HTML
    raw_html = build_markdown(config).render(md_text, env)
    # Step 2: Drop unsafe and forbidden markup before styling
    clean_html = sanitize(raw_html, config, keep_style_hooks=True)
    # Step 3: Inline styles from config.json
    styled_html = inject_styles(clean_html, config)
    # Step 4: Pretty-print for readability
    pretty_html = pretty_print(styled_html)
    # Step 5: Final safety pass on exactly what will be output
    return sanitize(pretty_html, config).strip()


def resolve_vault(cli_vault: str | None, input_path: Path) -> Vault | None:
    """--vault (remembered), else the vault containing the note, else the remembered one."""
    if cli_vault:
        root = Path(cli_vault).expanduser()
        if not root.is_dir():
            raise UserError(f"vault folder '{cli_vault}' not found.")
        root = root.resolve()
        if not (root / ".obsidian").is_dir():
            print(f"Warning: '{root}' has no .obsidian folder, so it may not be an Obsidian vault.",
                  file=sys.stderr)
        settings = load_settings()
        settings["vault_path"] = str(root)
        save_settings(settings)
        print(f"Remembered Obsidian vault '{root}' (saved in {settings_file()}).", file=sys.stderr)
        return Vault(root)

    detected = find_vault_root(input_path.parent)
    if detected:
        return Vault(detected)

    stored = load_settings().get("vault_path")
    if isinstance(stored, str) and stored:
        if Path(stored).is_dir():
            return Vault(Path(stored))
        print(f"Warning: the remembered vault '{stored}' no longer exists. Use --vault PATH to set it again.",
              file=sys.stderr)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert Obsidian Markdown to Blogger-compatible HTML."
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("input", help="Path to the .md input file")
    parser.add_argument(
        "-o", "--output",
        help="Path to the output file (default: prints to stdout)",
        default=None,
    )
    parser.add_argument(
        "-c", "--config",
        help="Path to config.json (default: config.json in current dir)",
        default="config.json",
    )
    parser.add_argument(
        "--imgfolder", nargs="?", const="", default=None, metavar="FOLDER",
        help=(f"Copy the note's images into FOLDER next to the output (default: {DEFAULT_IMGFOLDER}, "
              f"or {DEFAULT_IMGFOLDER}_2 etc. if that exists) and reference the copies"),
    )
    parser.add_argument(
        "--vault", default=None, metavar="PATH",
        help="Location of your Obsidian vault. Remembered for later runs",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)

        input_path = Path(args.input)
        if not input_path.is_file():
            raise UserError(f"input file '{args.input}' not found.")
        try:
            md_text = input_path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise UserError(f"could not read '{args.input}' as UTF-8 text: {exc}.") from None

        vault = resolve_vault(args.vault, input_path)
        out_path = Path(args.output) if args.output else None
        output_dir = (out_path.parent if out_path else Path.cwd()).resolve()

        exporter = None
        if args.imgfolder is not None:
            if args.imgfolder:
                folder = Path(args.imgfolder)
                folder = folder if folder.is_absolute() else output_dir / folder
            else:
                folder = unique_folder(output_dir, DEFAULT_IMGFOLDER)
            exporter = ImageExporter(folder, output_dir)
            if vault is None:
                print("Warning: no Obsidian vault is known, so images are only looked up next to the note. "
                      "Use --vault PATH to set it.", file=sys.stderr)

        warnings: list[str] = []
        result = convert(md_text, config, note_path=input_path, vault=vault,
                         exporter=exporter, warnings=warnings)
        for warning in warnings:
            print(f"Warning: {warning}", file=sys.stderr)

        if out_path:
            try:
                out_path.write_text(result, encoding="utf-8")
            except OSError as exc:
                raise UserError(f"could not write '{out_path}': {exc.strerror}.") from None
            print(f"Output written to {out_path}")
        else:
            print(result)
        if exporter:
            print(f"{exporter.count} image(s) copied to {exporter.folder}", file=sys.stderr)
    except UserError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
