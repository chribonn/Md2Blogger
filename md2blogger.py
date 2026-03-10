"""
md2blogger.py — Obsidian-flavored Markdown to Blogger-compatible HTML converter.

Reads config.json for inline styles and forbidden tags, parses .md input,
and outputs a clean HTML snippet ready for Blogger's HTML View.

Usage:
    python md2blogger.py input.md [-o output.html]
"""

import argparse
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString
from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(config_path: str = "config.json") -> dict:
    """Load and validate the configuration file."""
    path = Path(config_path)
    if not path.exists():
        print(f"Error: config file '{config_path}' not found.", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Obsidian pre-processing
# ---------------------------------------------------------------------------

def preprocess_obsidian(md_text: str, config: dict) -> str:
    """Convert Obsidian-specific syntax to standard Markdown before parsing."""
    obs_cfg = config.get("obsidian", {})
    base_url = obs_cfg.get("image_base_url", "")
    default_ext = obs_cfg.get("image_extension_default", ".png")

    # Obsidian image embeds: ![[filename.png]] or ![[filename]]
    def replace_image(m: re.Match) -> str:
        name = m.group(1).strip()
        # Add default extension if none present
        if "." not in name:
            name += default_ext
        url = f"{base_url}{name}" if base_url else name
        # URL-encode spaces for compatibility
        url = url.replace(" ", "%20")
        return f"![{name}]({url})"

    md_text = re.sub(r"!\[\[([^\]]+)\]\]", replace_image, md_text)

    # Obsidian wikilinks: [[Page Name]] or [[Page Name|Display Text]]
    def replace_wikilink(m: re.Match) -> str:
        content = m.group(1).strip()
        if "|" in content:
            target, display = content.split("|", 1)
            target_url = target.strip().replace(" ", "%20")
            return f"[{display.strip()}]({target_url})"
        target_url = content.replace(" ", "%20")
        return f"[{content}]({target_url})"

    md_text = re.sub(r"(?<!!)\[\[([^\]]+)\]\]", replace_wikilink, md_text)

    # Obsidian highlights: ==highlighted text==
    md_text = re.sub(
        r"==(.*?)==",
        r'<mark style="background-color: #fff3cd; padding: 2px 4px;">\1</mark>',
        md_text,
    )

    # Obsidian callouts: > [!note] Title  ->  blockquote with bold title
    def replace_callout(m: re.Match) -> str:
        callout_type = m.group(1).strip().lower()
        title = m.group(2).strip() if m.group(2) else callout_type.capitalize()
        return f"> **{title}:**"

    md_text = re.sub(
        r"^>\s*\[!(\w+)\]\s*(.*)?$",
        replace_callout,
        md_text,
        flags=re.MULTILINE,
    )

    return md_text



# ---------------------------------------------------------------------------
# Markdown -> raw HTML
# ---------------------------------------------------------------------------

def markdown_to_raw_html(md_text: str) -> str:
    """Parse Markdown text into raw HTML using markdown-it-py."""
    md = MarkdownIt("commonmark", {"html": True, "typographer": True})
    md.enable(["table", "strikethrough"])
    tasklists_plugin(md)
    return md.render(md_text)


# ---------------------------------------------------------------------------
# Inline style injection & tag sanitization
# ---------------------------------------------------------------------------

def inject_styles_and_sanitize(html: str, config: dict) -> str:
    """Walk the HTML tree, inject inline styles, strip forbidden tags."""
    soup = BeautifulSoup(html, "html.parser")
    styles = config.get("styles", {})
    forbidden = set(config.get("forbidden_tags", []))
    code_block_wrapper = config.get("code_block_wrapper", "{content}")

    # --- Strip forbidden tags (keep their children) ---
    for tag_name in forbidden:
        for tag in soup.find_all(tag_name):
            tag.unwrap()

    # --- Handle code blocks: wrap <pre><code> in styled div ---
    for pre_tag in soup.find_all("pre"):
        code_tag = pre_tag.find("code")
        if code_tag:
            # Apply code style to the <code> tag
            if "code" in styles and styles["code"]:
                code_tag["style"] = styles["code"]
            # Mark as processed
            code_tag["data-cb"] = "1"

            # Apply pre style
            if "pre" in styles and styles["pre"]:
                pre_tag["style"] = styles["pre"]
            # Mark as processed
            pre_tag["data-cb"] = "1"

            # Wrap in the code_block_wrapper div
            wrapper_html = code_block_wrapper.replace("{content}", str(pre_tag))
            wrapper_soup = BeautifulSoup(wrapper_html, "html.parser")
            pre_tag.replace_with(wrapper_soup)

    # --- Inject inline styles on all remaining tags ---
    for tag in soup.find_all(True):
        # Skip code-block elements already styled above
        if tag.get("data-cb"):
            del tag["data-cb"]
            continue
        tag_name = tag.name
        if tag_name in styles and styles[tag_name]:
            existing = tag.get("style", "")
            if existing:
                tag["style"] = f"{styles[tag_name]} {existing}"
            else:
                tag["style"] = styles[tag_name]

        # Remove class and id attributes (Blogger doesn't need them)
        for attr in ["class", "id"]:
            if tag.has_attr(attr):
                del tag[attr]

    # --- Final pass: ensure no forbidden tags slipped through ---
    for tag_name in forbidden:
        for tag in soup.find_all(tag_name):
            tag.unwrap()

    return str(soup)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def convert(md_text: str, config: dict) -> str:
    """Full conversion pipeline: preprocess -> parse -> style -> output."""
    # Step 1: Obsidian pre-processing
    md_text = preprocess_obsidian(md_text, config)

    # Step 2: Markdown -> raw HTML
    raw_html = markdown_to_raw_html(md_text)

    # Step 3: Inject inline styles and sanitize
    styled_html = inject_styles_and_sanitize(raw_html, config)

    # Step 4: Light cleanup
    # Remove any stray <style> blocks that might have been in the source
    styled_html = re.sub(r"<style[^>]*>.*?</style>", "", styled_html, flags=re.DOTALL | re.IGNORECASE)

    return styled_html.strip()


def main():
    parser = argparse.ArgumentParser(
        description="Convert Obsidian Markdown to Blogger-compatible HTML."
    )
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
    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    # Read input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input file '{args.input}' not found.", file=sys.stderr)
        sys.exit(1)

    md_text = input_path.read_text(encoding="utf-8")

    # Convert
    result = convert(md_text, config)

    # Output
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(result, encoding="utf-8")
        print(f"Output written to {out_path}")
    else:
        print(result)


if __name__ == "__main__":
    main()
