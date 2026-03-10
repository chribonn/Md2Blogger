# Md2Blogger

A Python tool that converts Obsidian-flavored Markdown files into Blogger-compatible HTML snippets with inline styling. The output is clean inner-content HTML ready to paste directly into Blogger's HTML View.

## Why

Blogger's editor strips `<style>` blocks, rejects many HTML5 tags, and mangles unstyled markup. This tool solves that by:

- Injecting all formatting as `style="..."` attributes directly on each tag
- Stripping tags that Blogger rejects (configurable)
- Converting Obsidian-specific syntax (`![[images]]`, `[[wikilinks]]`, `==highlights==`, callouts) into standard HTML

Everything is controlled through an editable `config.json` — no code changes needed to tweak styles or rules.

## Requirements

- Python 3.9+
- Dependencies:

```bash
pip install markdown-it-py mdit-py-plugins beautifulsoup4
```

## Usage

```bash
# Output to file
python md2blogger.py input.md -o output.html

# Print to stdout
python md2blogger.py input.md

# Use a custom config file
python md2blogger.py input.md -o output.html -c my_config.json
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `input` | Yes | Path to the `.md` input file |
| `-o`, `--output` | No | Output file path. Prints to stdout if omitted |
| `-c`, `--config` | No | Path to config file. Defaults to `config.json` in the current directory |

## Supported Markdown Features

| Feature | Syntax | Notes |
|---|---|---|
| Headers | `# H1` through `###### H6` | All levels supported |
| Bold / Italic | `**bold**`, `*italic*`, `***both***` | Nesting works correctly |
| Links | `[text](url)` | Standard Markdown links |
| Wikilinks | `[[Page]]`, `[[Page\|Display]]` | Obsidian-style, converted to `<a>` tags |
| Images | `![alt](url)` | Standard Markdown |
| Obsidian images | `![[file.png]]`, `![[file]]` | Auto-adds default extension if missing |
| Inline code | `` `code` `` | Styled with monospace font + background |
| Code blocks | ` ```lang ... ``` ` | Wrapped in a styled `<div>` container |
| Unordered lists | `- item` | Nested lists supported |
| Ordered lists | `1. item` | Nested lists supported |
| Task lists | `- [x] done`, `- [ ] todo` | Obsidian-style checkboxes |
| Blockquotes | `> text` | Multi-line supported |
| Callouts | `> [!note] Title` | Obsidian callouts rendered as styled blockquotes |
| Tables | Pipe tables | Every `<th>` and `<td>` gets inline borders/padding |
| Highlights | `==text==` | Obsidian highlight syntax → `<mark>` tag |
| Strikethrough | `~~text~~` | Rendered as `<s>` with line-through |
| Horizontal rules | `---` | Styled `<hr>` |
| Raw HTML | Inline HTML in source | Passed through, styled, and sanitized |

## config.json Reference

The config file has four sections:

### `forbidden_tags`

An array of HTML tag names that will be stripped from the output. Their child content is preserved — only the tag wrapper is removed.

```json
"forbidden_tags": [
    "html", "head", "body", "meta", "link", "title",
    "style", "script",
    "header", "footer", "nav", "main", "section", "article", "aside",
    "col", "colgroup",
    "form", "input", "textarea", "select", "button",
    "iframe", "embed", "object",
    "svg", "canvas", "video", "audio",
    "base", "template", "slot"
]
```

These defaults cover tags that Blogger typically strips, blocks, or renders incorrectly. Add or remove entries as needed.

### `styles`

A map of HTML tag name → inline CSS string. Every instance of that tag in the output gets this `style` attribute applied.

```json
"styles": {
    "h1": "font-family: verdana, sans-serif; color: #333; font-size: 2em;",
    "p": "font-family: verdana, sans-serif; line-height: 1.6; color: #333;",
    "th": "border: 1px solid #ddd; padding: 8px 12px; background-color: #f2f2f2;",
    "td": "border: 1px solid #ddd; padding: 8px 12px;"
}
```

Set a tag's value to `""` (empty string) to skip styling for that tag. Nested elements each get their own style independently — for example, a `<strong>` inside a `<li>` receives both the `li` style on the list item and the `strong` style on the bold text.

### `code_block_wrapper`

A template string for wrapping fenced code blocks. The placeholder `{content}` is replaced with the `<pre><code>...</code></pre>` block.

```json
"code_block_wrapper": "<div style=\"background-color: #f4f4f4; padding: 15px; border: 1px solid #ddd; border-radius: 4px; overflow-x: auto; margin: 1em 0;\">{content}</div>"
```

### `obsidian`

Settings for Obsidian-specific syntax conversion.

```json
"obsidian": {
    "image_base_url": "",
    "image_extension_default": ".png"
}
```

| Key | Description |
|---|---|
| `image_base_url` | Prepended to image filenames from `![[image]]` syntax. Set to your image hosting URL (e.g., `https://myblog.com/images/`) or leave empty for relative paths. |
| `image_extension_default` | Extension appended to `![[image]]` references that don't include one. Defaults to `.png`. |

## How It Works

1. **Obsidian pre-processing** — Regex pass converts `![[]]` images, `[[]]` wikilinks, `==highlights==`, and `> [!type]` callouts into standard Markdown/HTML.
2. **Markdown parsing** — `markdown-it-py` (CommonMark + tables + strikethrough + task lists) converts Markdown to raw HTML.
3. **Style injection & sanitization** — BeautifulSoup walks the HTML tree, applies inline styles from `config.json`, strips forbidden tags, and removes `class`/`id` attributes.
4. **Cleanup** — Any stray `<style>` blocks are removed as a final safety pass.

## Example

Given `sample.md` in this repo:

```bash
python md2blogger.py sample.md -o sample_output.html
```

Open `sample_output.html` in a browser to preview, or paste its contents into Blogger's HTML View.
