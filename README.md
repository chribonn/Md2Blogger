# Md2Blogger

Version 1.0 · [Changelog](CHANGELOG.md)

A Python tool that converts Obsidian-flavored Markdown files into Blogger-compatible HTML snippets with inline styling. The output is clean inner-content HTML ready to paste directly into Blogger's HTML View.

## Why

Blogger's editor strips `<style>` blocks, rejects many HTML5 tags, and mangles unstyled markup. This tool solves that by:

- Injecting all formatting as `style="..."` attributes directly on each tag
- Stripping tags that Blogger rejects (configurable)
- Converting Obsidian-specific syntax (callouts, `![[images]]`, `[[wikilinks]]`, `==highlights==`, footnotes, comments and more) into HTML that looks as close as possible to Obsidian's reading view
- Removing anything unsafe (scripts, event handlers, `javascript:` links) before the HTML reaches your blog

Everything is controlled through an editable `config.json`, so no code changes are needed to tweak styles or rules.

## Requirements

- Python 3.12 or newer (tested on 3.12 and 3.15)
- Dependencies:

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Output to file
python md2blogger.py input.md -o output.html

# Print to stdout
python md2blogger.py input.md

# Use a custom config file
python md2blogger.py input.md -o output.html -c my_config.json

# Copy the note's images next to the HTML (into md2blg/)
python md2blogger.py input.md -o post/output.html --imgfolder

# Same, into a folder you name
python md2blogger.py input.md -o post/output.html --imgfolder images

# Tell Md2Blogger where your vault is (remembered for later runs)
python md2blogger.py input.md -o output.html --imgfolder --vault "D:\Obsidian\My Vault"
```

### Arguments

| Argument | Required | Description |
|---|---|---|
| `input` | Yes | Path to the `.md` input file |
| `-o`, `--output` | No | Output file path. Prints to stdout if omitted |
| `-c`, `--config` | No | Path to config file. Defaults to `config.json` in the current directory |
| `--imgfolder [FOLDER]` | No | Copy the note's images into `FOLDER` next to the output and point the HTML at the copies. Without a name, uses `md2blg` (or `md2blg_2`, `md2blg_3` … if that folder already exists) |
| `--vault PATH` | No | Location of your Obsidian vault. Saved, so you only need to give it once |
| `-v`, `--version` | No | Show the version |

Put `--imgfolder` after the input file name, or write `--imgfolder=FOLDER`. Otherwise the input file name is read as the folder name.

### Images: references or copies

By default, image references stay as they are in Obsidian. `![[photo.png]]` becomes `<img src="photo.png">`, with `image_base_url` (see below) in front if you set one. Use this when you upload the images to Blogger or another host yourself.

With `--imgfolder`, every local image the note uses is copied into one folder, and the HTML refers to the copies with relative paths. The folder, the HTML file and the images can then be moved or zipped together.

- The folder is created next to the output file (or in the current directory when printing to stdout).
- It mirrors your vault's folders. `Attachments/2026/photo one.png` in the vault is copied to `md2blg/Attachments/2026/photo one.png`.
- File names are kept. A name only changes (`photo_2.png`) if two different images would land on the same path.
- Without a folder name, a new unique folder is created on each run. With a name, the folder is reused and its copies are updated.
- Only image files (`avif`, `bmp`, `gif`, `jpeg`, `jpg`, `png`, `svg`, `webp`) are copied, and only from inside your vault or the note's own folder.
- External images (`https://…`) are left as they are.

### The Obsidian vault location

Md2Blogger needs your vault to find images by name (as Obsidian does) and to include embedded notes. It looks for the vault in this order:

1. `--vault PATH`, which is also saved for next time.
2. The vault that contains the input file. Any parent folder with an `.obsidian` folder counts.
3. The vault saved by an earlier `--vault`.

The saved location lives in a small settings file outside the project, so your local paths never end up in git:

| System | Settings file |
|---|---|
| Windows | `%APPDATA%\Md2Blogger\settings.json` |
| macOS | `~/Library/Application Support/Md2Blogger/settings.json` |
| Linux | `~/.config/Md2Blogger/settings.json` |

Set the `MD2BLOGGER_SETTINGS` environment variable to use a different file. Delete the file to forget the vault.

## Supported Markdown Features

| Feature | Syntax | Output |
|---|---|---|
| Headers | `# H1` through `###### H6` | Each heading gets an `id`, so links can jump to it |
| Bold / Italic | `**bold**`, `*italic*`, `***both***` | Nesting works correctly |
| Links | `[text](url)` | `http`, `https`, `mailto` and relative links. Other kinds (`javascript:`, `file:`) become plain text |
| Wikilinks | `[[Note]]`, `[[Note\|Text]]`, `[[Note#Heading]]` | Plain text by default, since other notes aren't on your blog. See `wikilink_url_template` |
| Links within the note | `[[#Heading]]`, `[[#^block-id]]`, `[text](#Heading%20name)`, `[text](#^block-id)` | Links that jump to that part of the post |
| Block IDs | `text ^block-id`, or `^block-id` on its own line | Hidden; the block (or the block above) gets that `id` |
| Images | `![alt](url)`, `![alt\|300](url)`, `![300x200](url)` | Sizes become `width`/`height` |
| Obsidian images | `![[file.png]]`, `![[file.png\|300]]`, `![[file.png\|640x480]]`, `![[file]]` | Adds the default extension if missing. `![[file.png\|Alt text]]` sets the alt text |
| Embedded notes | `![[Note]]`, `![[Note#Heading]]`, `![[Note#^block-id]]` | The note, section or block appears in a framed box. Needs the vault |
| Audio, video, PDF | `![[talk.mp3]]`, `![[Document.pdf]]` | A link to the file (Blogger can't embed them) |
| Inline code | `` `code` `` | Styled with monospace font + background |
| Code blocks | ` ```lang ... ``` ` | Wrapped in a styled `<div>` container |
| Diagrams | ` ```mermaid ... ``` ` | Shown as a code block (Blogger can't run Mermaid) |
| Unordered lists | `- item` | Nested lists supported |
| Ordered lists | `1. item` | Nested lists supported |
| Task lists | `- [ ] todo`, `- [x] done`, `- [?]`, `- [-]` | ☐ / ☑. Any character other than a space marks a task as done, as in Obsidian. Done tasks are struck through |
| Blockquotes | `> text` | Multi-line supported |
| Callouts | `> [!tip] Title`, `> [!faq]- Folded`, `> [!faq]+ Open` | Coloured box with the type's icon and title. All 13 Obsidian types and their aliases. Foldable callouts open and close (`<details>`). Nesting works |
| Tables | Pipe tables | Every `<th>` and `<td>` gets inline borders/padding. `\|` works inside cells |
| Highlights | `==text==`, `==🔴text==` | `<mark>`. Red, orange, yellow, green, blue and purple via 🔴🟠🟡🟢🔵🟣 |
| Footnotes | `text[^1]`, `[^1]: note`, `text^[inline note]` | Numbered references, with the notes listed at the end |
| Comments | `%%hidden%%`, or `%%` on lines around a block | Removed, so private notes stay private |
| Properties | `---` front matter at the top | Removed |
| Tags | `#tag`, `#nested/tag` | A small label, as in Obsidian. Configurable |
| Maths | `$e^{i\pi}$`, `$$ ... $$` | Ready for MathJax. See [Maths on Blogger](#maths-on-blogger) |
| Strikethrough | `~~text~~` | Rendered as `<s>` with line-through |
| Horizontal rules | `---` | Styled `<hr>` |
| Raw HTML | Inline HTML in source | Allowed tags pass through and are styled. Scripts, frames, forms and event handlers are removed |

## config.json Reference

`config.json` is merged over built-in defaults, so a custom config only needs the settings you want to change. A 0.9 config file still works: any new setting it doesn't have takes its default value. If a value is wrong, Md2Blogger stops and tells you which setting to fix.

### `forbidden_tags`

An array of HTML tag names that will be stripped from the output. Their child content is preserved; only the tag wrapper is removed.

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

Md2Blogger only ever outputs tags from a fixed list of safe ones, and `forbidden_tags` removes tags from that list. Removing `script` or `iframe` from `forbidden_tags` does not allow them. `script`, `style`, `template`, `iframe`, `svg` and similar tags are always removed together with their content.

### `allow_raw_html`

`true` (default): HTML written in the note is kept (after cleaning). `false`: it is shown as text.

### `styles`

A map of HTML tag name → inline CSS string. Every instance of that tag in the output gets this `style` attribute applied.

```json
"styles": {
    "h1": "font-family: verdana, sans-serif; color: #333; font-size: 2em;",
    "p": "font-family: verdana, sans-serif; line-height: 1.6; color: #333;",
    "th": "border: 1px solid #ddd; padding: 8px 12px; background-color: #f2f2f2;",
    "td": "border: 1px solid #ddd; padding: 8px 12px;",
    ".tag": "background-color: rgba(138, 92, 245, 0.1); color: #8a5cf5; border-radius: 2em;"
}
```

Set a value to `""` (empty string) to skip styling. Nested elements each get their own style independently. For example, a `<strong>` inside a `<li>` receives both the `li` style on the list item and the `strong` style on the bold text.

Keys that start with a dot style the elements Md2Blogger creates for Obsidian features:

| Key | Styles |
|---|---|
| `.callout` | The callout box. `{color}` is replaced with the callout type's colour, e.g. `rgba({color}, 0.1)` |
| `.callout-title` | The callout's title line (also takes `{color}`) |
| `.callout-content` | The callout's body |
| `.highlight-red` … `.highlight-purple` | Coloured highlights. Applied after the `mark` style |
| `.tag` | `#tags` (when `obsidian.tags` is `label`) |
| `.internal-link` | Links to other notes |
| `.task`, `.task-done`, `.task-checkbox` | Every task item, completed tasks, and the ☐ / ☑ symbol |
| `.embed` | The frame around an embedded note |
| `.math`, `.math-block` | Inline and display maths |
| `.footnote-ref`, `.footnotes-list`, `.footnote-backref` | Footnote numbers, the list of notes, and the ↩ links |

Styles are applied in this order: the tag style, then any `.` styles, then styles that come from the note itself (table column alignment, `style` in raw HTML). When a property appears twice, the later one wins.

### `code_block_wrapper`

A template string for wrapping fenced code blocks. The placeholder `{content}` is replaced with the `<pre><code>...</code></pre>` block.

```json
"code_block_wrapper": "<div style=\"background-color: #f4f4f4; padding: 15px; border: 1px solid #ddd; border-radius: 4px; overflow-x: auto; margin: 1em 0;\">{content}</div>"
```

### `callouts`

```json
"callouts": {
    "default_type": "note",
    "types": {
        "note":    { "color": "8, 109, 221", "icon": "✏️" },
        "warning": { "color": "236, 117, 0", "icon": "⚠️" }
    },
    "aliases": { "caution": "warning", "attention": "warning" }
}
```

| Key | Description |
|---|---|
| `types` | Colour and icon for each callout type. Colours can be `"r, g, b"` or `"#rrggbb"`. Icons are emoji (Blogger can't use Obsidian's SVG icons); use `""` for none. Add your own types here, e.g. `"recipe": { "color": "#2e7d32", "icon": "🍲" }` |
| `aliases` | Other names for a type, as in Obsidian (`hint` → `tip`, `faq` → `question` …) |
| `default_type` | The style used for types that aren't listed, as in Obsidian |

The default colours are based on Obsidian's default light theme. If `details` or `summary` is in `forbidden_tags`, foldable callouts are shown open, as plain boxes.

### `tasks`

```json
"tasks": { "unchecked": "☐", "checked": "☑" }
```

The symbols shown in front of to-do and done tasks.

### `obsidian`

Settings for Obsidian-specific syntax conversion.

```json
"obsidian": {
    "image_base_url": "",
    "image_extension_default": ".png",
    "strict_line_breaks": true,
    "wikilink_url_template": "",
    "tags": "label",
    "math": "mathjax"
}
```

| Key | Description |
|---|---|
| `image_base_url` | Prepended to image (and attachment) paths from `![[image]]` syntax. Set to your image hosting URL (e.g., `https://myblog.com/images/`) or leave empty for relative paths. Not used for images copied with `--imgfolder` |
| `image_extension_default` | Extension appended to `![[image]]` references that don't include one. Defaults to `.png`. If the vault has a note with that name, the note is embedded instead |
| `strict_line_breaks` | `true` (default): a single line break inside a paragraph is ignored, as in standard Markdown and Obsidian's default. `false`: it becomes `<br>`, as with Obsidian's "Strict line breaks" turned off |
| `wikilink_url_template` | Empty (default): links to other notes are plain text. Otherwise a URL with `{name}` where the note name goes, e.g. `https://myblog.blogspot.com/search?q={name}` to link to a Blogger search for the post |
| `tags` | `label` (default): styled with `.tag`. `text`: plain text. `remove`: left out |
| `math` | `mathjax` (default): formulas are written for MathJax. `text`: the LaTeX source is shown as code |

## Maths on Blogger

Formulas are output as `\( … \)` (inline) and `\[ … \]` (display), which [MathJax](https://docs.mathjax.org/en/latest/web/start.html) typesets in the reader's browser. Add MathJax to your blog once: in Blogger, go to **Theme**, open the menu next to **Customise**, choose **Edit HTML**, and paste this just before `</head>`:

```html
<script defer='defer' src='https://cdn.jsdelivr.net/npm/mathjax@4/tex-mml-chtml.js'></script>
```

Without it, readers see the LaTeX source. Set `"math": "text"` if you'd rather show it as code.

## Security

The HTML goes straight onto a public web page, so Md2Blogger cleans it with [nh3](https://github.com/messense/nh3), a sanitizer built on the Rust library ammonia.

- Only a fixed list of safe tags and attributes is kept. Scripts, styles, frames, forms, SVG, event handlers (`onclick`, `onerror` …) and HTML comments are removed.
- Links and images may only use `http`, `https`, `mailto` or relative URLs. A link with any other URL (`javascript:`, `data:`, `file:`) is shown as plain text.
- The HTML is cleaned twice: once before styles are added, and again on the exact text that is written out.
- Obsidian comments and properties are never published.
- `--imgfolder` only copies image files, and only from your vault or the note's folder. A link like `../../secret.png` can't pull other files into the export.
- The vault location is saved outside the project folder.
- Dependencies are pinned in `requirements.txt`. Dependabot (`.github/dependabot.yml`) proposes updates, and `pip-audit` checks for known vulnerabilities (see [Development](#development)).

`style` attributes from raw HTML in your notes are kept, so a note can still position or hide its own content. Only convert notes whose HTML you trust.

## How It Works

1. **Parsing**: `markdown-it-py` (CommonMark + tables + strikethrough) converts the note to HTML. Plugins from `mdit-py-plugins` add properties, footnotes, maths and heading ids. Md2Blogger's own parser rules handle comments, highlights, wikilinks and embeds, tags, callouts, tasks and block IDs. Because these are parser rules rather than find-and-replace, they never change code blocks or inline code.
2. **Sanitizing**: nh3 removes unsafe and forbidden markup.
3. **Style injection**: BeautifulSoup applies the inline styles from `config.json` and wraps code blocks.
4. **Pretty-printing**: the HTML is indented for readability, with all text and attributes properly escaped.
5. **Final check**: nh3 cleans the finished HTML once more.

## Example

Given `sample.md` in this repo:

```bash
python md2blogger.py sample.md -o sample.html
```

Open `sample.html` in a browser to preview, or paste its contents into Blogger's HTML View.

## Development

```bash
pip install -r requirements-dev.txt

# Run the tests
python -m pytest

# Check the pinned dependencies for known vulnerabilities
python -m pip_audit -r requirements.txt -r requirements-dev.txt
```
