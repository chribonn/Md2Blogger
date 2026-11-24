# Changelog

All notable changes to Md2Blogger are listed here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 1.0 - 2026-11-24

### Added

- Callouts look like Obsidian's: each of the 13 types (and their aliases) has its own colour and icon. Custom titles, title-only callouts, `[!type|metadata]` and unknown types (styled as `note`) are supported.
- Foldable callouts (`> [!faq]-` collapsed, `> [!faq]+` open) become `<details>`/`<summary>`, so readers can open and close them.
- Nested callouts.
- Highlight colours: `==🔴text==`, plus orange, yellow, green, blue and purple.
- Footnotes (`[^1]`, `[^name]`) and inline footnotes (`^[note]`).
- `%%comments%%`, inline and as blocks, are removed from the output.
- Properties (front matter) are removed from the output.
- `#tags` are shown as labels (or as plain text, or removed; see `obsidian.tags`).
- Maths (`$…$`, `$$…$$`) is output for MathJax, or as LaTeX source (`obsidian.math`).
- Image sizes: `![[image.png|300]]`, `![[image.png|640x480]]`, `![alt|300](url)` and `![300](url)`. Wikilink images can set alt text: `![[image.png|Alt text]]`.
- Embedded notes: `![[Note]]`, `![[Note#Heading]]` and `![[Note#^block-id]]` include the content in a framed box (needs the vault).
- Audio, video and PDF embeds become links to the file.
- Headings get ids. `[[#Heading]]`, `[[Note#Heading]]` (for the current note), `[[#^block-id]]` and `[text](#Heading%20name)` link to them.
- Block references: `^block-id` markers are hidden and become anchors, and `[text](#^block-id)` links to them. A `^block-id` on its own line names the block above it, as in Obsidian. (Block references were added locally after 0.9 and are first published with 1.0.)
- Any character between the task brackets (`[?]`, `[-]`, `[/]`) marks a task as done, as in Obsidian. Tasks show ☐ / ☑ and done tasks are struck through.
- `\|` inside table cells, for wikilink aliases and image sizes.
- `--imgfolder [FOLDER]` copies the note's images into a folder next to the HTML, mirroring the vault's folder structure and keeping file names, so the HTML and its images can be moved together. The default folder is `md2blg`, or `md2blg_2` etc. if it already exists.
- `--vault PATH` sets the Obsidian vault location and remembers it in a per-user settings file. The vault is also found automatically when the note is inside it.
- New settings in `config.json`: `allow_raw_html`, `callouts`, `tasks`, `obsidian.strict_line_breaks`, `obsidian.wikilink_url_template`, `obsidian.tags`, `obsidian.math`, and `.class` keys in `styles` for the new elements.
- `config.json` is merged over built-in defaults, so 0.9 configs keep working, and invalid settings are reported with the setting's name.
- A pytest suite (`tests/`), `requirements-dev.txt` and a Dependabot configuration.

### Changed

- Obsidian syntax is handled by markdown-it parser rules instead of find-and-replace over the whole file.
- HTML is cleaned with nh3 against a fixed allowlist of safe tags. `forbidden_tags` now removes tags from that list; before, any tag not listed passed through.
- Links to other notes (`[[Other Note]]`) are plain text by default, instead of relative links that are broken on Blogger. `obsidian.wikilink_url_template` can turn them into links.
- `![[name]]` without an extension embeds the note when the vault contains `name.md`. Otherwise it is still an image with the default extension.
- `id` attributes are kept (headings, block references and footnotes need them). `class` attributes are still removed.
- Image paths are fully URL-encoded (before, only spaces were).
- Links with unsafe or local URLs (`javascript:`, `data:`, `file:`) are shown as plain text.
- Errors are reported as a single line instead of a Python traceback, and warnings go to stderr. Files with a UTF-8 byte order mark are read correctly.
- Requires Python 3.12 or newer. Dependencies updated: beautifulsoup4 4.15.0, markdown-it-py 4.3.0, mdit-py-plugins 0.7.0, soupsieve 4.1.3, typing_extensions 4.16.0. New dependency: nh3 0.3.8.
- The example output `sample_output.html` is now `sample.html`.

### Fixed

- `==` and `^block-id` were also replaced inside code blocks and inline code, which changed the code.
- Code blocks containing `<`, `>` or `&` were escaped twice and showed `&lt;` on the page.
- The pretty-printer added spaces between adjacent elements (`**un**believable` became "un believable") and collapsed non-breaking spaces.
- Task list checkboxes disappeared, because `input` is a forbidden tag, so done and to-do items looked the same.
- Foldable callout titles started with "- ", and callout types containing `-` weren't recognised.
- `![[image.png|300]]` produced a broken image URL.

### Security

- Quotes in image alt text or link titles could break out of the attribute when pretty-printing and add attributes such as `onerror` (cross-site scripting).
- Escaped text (`&lt;img …&gt;`) was turned back into live HTML.
- Raw HTML kept event handlers (`onclick`, `onerror` …) and `javascript:` links. It is now sanitized.
- The contents of `<script>` and `<style>` were left on the page as visible text. They are now removed completely.
- Obsidian comments and properties, which are private, were published.

## 0.9 - 2026-03-10

First public (beta) release.

- Converts Obsidian Markdown to Blogger-ready HTML with inline styles from `config.json`.
- Strips tags listed in `forbidden_tags`.
- Supports headers, emphasis, links, wikilinks, images, `![[image]]` embeds, code, lists, task lists, blockquotes, callouts (as blockquotes), tables, highlights, strikethrough and horizontal rules.
