"""Obsidian-flavoured Markdown structures."""

import md2blogger
from conftest import soup


def text_of(html: str) -> str:
    return " ".join(soup(html).get_text().split())


# --- Comments ---------------------------------------------------------------

def test_inline_comment_is_hidden(convert):
    assert text_of(convert("This is an %%inline%% comment.")) == "This is an comment."


def test_block_comment_with_blank_lines_and_markdown_is_hidden(convert):
    out = convert("Before\n\n%%\nHidden\n\n# Hidden heading\n- hidden item\n%%\n\nAfter")
    assert text_of(out) == "Before After"


def test_text_after_a_block_comment_stays_visible(convert):
    out = convert("%%\ncomment\n%% _italic_")
    assert soup(out).find("em").get_text() == "italic"


def test_unclosed_block_comment_hides_the_rest(convert):
    assert text_of(convert("Visible\n\n%%\nHidden\n\nStill hidden")) == "Visible"


def test_comment_markers_in_code_are_kept(convert):
    out = convert("`%%a%%`\n\n```\nx = 10 %% 3\n%%\n```")
    assert "%%a%%" in out
    assert "x = 10 %% 3" in out


# --- Properties (front matter) ----------------------------------------------

def test_front_matter_is_removed(convert):
    out = convert("---\ntitle: My post\ntags: [a, b]\n---\n# Heading\n\n---\n\nEnd")
    assert "title:" not in out
    assert soup(out).find("h1").get_text() == "Heading"
    assert soup(out).find("hr") is not None


# --- Callouts -----------------------------------------------------------------

def callout_box(html: str):
    return soup(html).find(["div", "details"])


def test_callout_gets_type_colour_icon_and_title(convert):
    out = convert("> [!warning] Mind the gap\n> Body text")
    box = callout_box(out)
    assert "rgba(236, 117, 0, 0.1)" in box["style"]
    title, content = box.find_all("div", recursive=False)
    assert title.get_text() == "⚠️ Mind the gap"
    assert "rgb(236, 117, 0)" in title["style"]
    assert content.get_text(strip=True) == "Body text"


def test_callout_default_title_is_the_type_in_title_case(convert):
    title = callout_box(convert("> [!faq]\n> Body")).find("div")
    assert title.get_text() == "❓ Faq"


def test_callout_aliases_and_unknown_types(convert):
    assert "0, 191, 188" in callout_box(convert("> [!hint] Hi"))["style"]      # tip colour
    unknown = callout_box(convert("> [!my-custom] Hi"))
    assert "8, 109, 221" in unknown["style"]                                     # note colour
    assert unknown.find("div").get_text() == "✏️ Hi"


def test_callout_title_supports_markdown_and_metadata_is_ignored(convert):
    title = callout_box(convert("> [!note|wide] A **bold** title")).find("div")
    assert title.find("strong").get_text() == "bold"
    assert "wide" not in title.get_text()


def test_title_only_callout_has_no_content_box(convert):
    box = callout_box(convert("> [!tip] Title-only callout"))
    assert len(box.find_all("div", recursive=False)) == 1


def test_foldable_callouts_use_details_and_summary(convert):
    collapsed = soup(convert("> [!faq]- Are callouts foldable?\n> Yes")).find("details")
    assert collapsed is not None and not collapsed.has_attr("open")
    assert collapsed.find("summary").get_text() == "❓ Are callouts foldable?"
    expanded = soup(convert("> [!faq]+ Open\n> Yes")).find("details")
    assert expanded.has_attr("open")


def test_foldable_callout_falls_back_to_div_when_details_is_forbidden():
    config = md2blogger.prepare_config({"forbidden_tags": ["details", "summary"]})
    out = md2blogger.convert("> [!faq]- Q\n> A", config)
    assert soup(out).find("details") is None
    assert "Q" in out and "A" in out


def test_nested_callouts(convert):
    out = convert("> [!question] Can callouts be nested?\n> > [!todo] Yes!\n> > > [!example] Deeper")
    titles = [d.get_text(" ", strip=True) for d in soup(out).find_all("div") if "font-weight: 600" in d.get("style", "")]
    assert titles == ["❓ Can callouts be nested?", "☑️ Yes!", "📑 Deeper"]


def test_callout_body_keeps_lists_and_paragraphs(convert):
    out = convert("> [!hint] Callout Title\n> This is some text\n>\n> - with bullet points")
    box = callout_box(out)
    assert box.find("p").get_text() == "This is some text"
    assert box.find("li").get_text() == "with bullet points"


def test_plain_blockquote_is_unchanged(convert):
    assert soup(convert("> Just a quote")).find("blockquote") is not None


def test_callout_colours_can_be_customised_with_hex():
    config = md2blogger.prepare_config({"callouts": {"types": {"note": {"color": "#ff0000", "icon": "!"}}}})
    box = callout_box(md2blogger.convert("> [!note] Hi", config))
    assert "rgba(255, 0, 0, 0.1)" in box["style"]
    assert box.find("div").get_text() == "! Hi"


# --- Highlights ---------------------------------------------------------------

def test_highlight_and_colour_highlights(convert):
    marks = soup(convert("==plain== ==🔴red== ==🟢green==")).find_all("mark")
    assert [m.get_text() for m in marks] == ["plain", "red", "green"]
    assert "rgba(233, 49, 71, 0.25)" in marks[1]["style"]
    assert "rgba(8, 185, 78, 0.25)" in marks[2]["style"]


def test_highlight_can_contain_formatting(convert):
    mark = soup(convert("==some **bold** text==")).find("mark")
    assert mark.find("strong").get_text() == "bold"


def test_highlight_markers_in_code_and_comparisons_are_left_alone(convert):
    out = convert("`a == b` and x == y\n\n```python\nassert a == 1 and b == 2\n```")
    assert soup(out).find("mark") is None
    assert "assert a == 1 and b == 2" in out


# --- Footnotes ----------------------------------------------------------------

def test_footnotes_and_inline_footnotes(convert):
    out = convert("Simple[^1] and inline.^[Inline note.]\n\n[^1]: The referenced text.")
    refs = soup(out).find_all("sup")
    assert [r.get_text() for r in refs] == ["[1]", "[2]"]
    items = soup(out).find("ol").find_all("li")
    assert "The referenced text." in items[0].get_text()
    assert "Inline note." in items[1].get_text()
    assert refs[0].find("a")["href"] == "#" + items[0]["id"]


def test_footnote_ids_include_the_note_name(convert, tmp_path):
    out = convert("A[^1]\n\n[^1]: B", note_path=tmp_path / "My Post.md")
    assert soup(out).find("sup").find("a")["href"] == "#fn-my-post-1"


# --- Links, headings and block references ----------------------------------

def test_headings_get_ids_that_wikilinks_point_to(convert):
    out = convert("## My Heading\n\nSee [[#My Heading]] and [[#My Heading|that part]].")
    parsed = soup(out)
    assert parsed.find("h2")["id"] == "my-heading"
    links = parsed.find_all("a")
    assert [(a["href"], a.get_text()) for a in links] == [("#my-heading", "My Heading"), ("#my-heading", "that part")]


def test_links_to_the_current_note_become_page_anchors(convert, tmp_path):
    out = convert("# Intro\n\n[[Post#Intro]]", note_path=tmp_path / "Post.md")
    assert soup(out).find("a")["href"] == "#intro"


def test_markdown_links_to_headings_and_blocks(convert):
    out = convert("## Big Idea\n\nText ^b1\n\n[h](#Big%20Idea) [b](#^b1)")
    assert [a["href"] for a in soup(out).find_all("a")] == ["#big-idea", "#b1"]


def test_links_to_other_notes_are_plain_text_by_default(convert):
    out = convert("[[Other Note]], [[Other Note|custom text]] and [[Other Note#Part]]")
    parsed = soup(out)
    assert parsed.find("a") is None
    assert text_of(out) == "Other Note, custom text and Other Note > Part"


def test_links_to_other_notes_can_use_a_url_template():
    config = md2blogger.prepare_config(
        {"obsidian": {"wikilink_url_template": "https://myblog.blogspot.com/search?q={name}"}}
    )
    out = md2blogger.convert("[[Other Note|read this]]", config)
    link = soup(out).find("a")
    assert link["href"] == "https://myblog.blogspot.com/search?q=Other%20Note"
    assert link.get_text() == "read this"


def test_block_id_at_end_of_paragraph(convert):
    out = convert("A quotable sentence. ^quote-1\n\n[[#^quote-1]]")
    parsed = soup(out)
    assert parsed.find("p")["id"] == "quote-1"
    assert "^quote-1" not in parsed.find("p").get_text()
    assert parsed.find("a")["href"] == "#quote-1"


def test_block_id_on_its_own_line_names_the_block_above(convert):
    out = convert("- one\n- two\n\n^my-list\n\n## Heading\n^head-id")
    parsed = soup(out)
    assert parsed.find("ul")["id"] == "my-list"
    heading = parsed.find("h2")
    assert heading["id"] == "heading"
    assert heading.find("span")["id"] == "head-id"
    assert "^" not in parsed.get_text()


def test_block_id_on_a_list_item(convert):
    assert soup(convert("- item ^li-1\n- other")).find("li")["id"] == "li-1"


def test_block_ids_in_code_are_left_alone(convert):
    out = convert("```\nmask = x ^bits\n```")
    assert "mask = x ^bits" in out
    assert 'id="bits"' not in out


# --- Tasks --------------------------------------------------------------------

def test_tasks_show_checkboxes_and_any_character_completes_them(convert):
    items = soup(convert("- [x] Milk\n- [ ] Eggs\n- [?] Bread\n- [-] Jam")).find_all("li")
    assert [li.get_text() for li in items] == ["☑Milk", "☐Eggs", "☑Bread", "☑Jam"]
    assert "line-through" in items[0]["style"]
    assert "line-through" not in items[1]["style"]
    assert all("list-style-type: none" in li["style"] for li in items)


def test_ordered_and_nested_task_lists(convert):
    out = convert("1. [ ] Task\n   - [x] Subtask")
    assert [li.find("span").get_text() for li in soup(out).find_all("li")] == ["☐", "☑"]


def test_task_glyphs_are_configurable():
    config = md2blogger.prepare_config({"tasks": {"unchecked": "[ ]", "checked": "[x]"}})
    assert soup(md2blogger.convert("- [x] a", config)).find("span").get_text() == "[x]"


# --- Tags ---------------------------------------------------------------------

def test_tags_are_labels_by_default(convert):
    out = convert("Filed under #blogging and #project/active, issue #123, C#sharp")
    spans = soup(out).find_all("span")
    assert [s.get_text() for s in spans] == ["#blogging", "#project/active"]
    assert "border-radius" in spans[0]["style"]
    assert "#123" in out and "C#sharp" in out


def test_tag_modes():
    for mode, expected in (("text", "See #idea now"), ("remove", "See now")):
        config = md2blogger.prepare_config({"obsidian": {"tags": mode}})
        out = md2blogger.convert("See #idea now", config)
        assert soup(out).find("span") is None
        assert text_of(out) == expected


def test_tags_in_code_and_headings_markers_are_not_tags(convert):
    out = convert("# Heading\n\n`#notatag`")
    assert soup(out).find("span") is None


# --- Maths --------------------------------------------------------------------

def test_math_uses_mathjax_delimiters(convert):
    out = convert("Euler: $e^{i\\pi} = -1$, prices $5 and $10\n\n$$\na < b\n$$")
    parsed = soup(out)
    assert "\\(e^{i\\pi} = -1\\)" in parsed.find("p").get_text()
    assert "$5 and $10" in parsed.find("p").get_text()
    assert parsed.find_all("div")[-1].get_text() == "\\[a < b\\]"


def test_math_can_be_shown_as_source():
    config = md2blogger.prepare_config({"obsidian": {"math": "text"}})
    out = md2blogger.convert("Inline $x^2$", config)
    assert soup(out).find("code").get_text() == "$x^2$"


# --- Other blocks -------------------------------------------------------------

def test_mermaid_stays_a_code_block(convert):
    out = convert("```mermaid\ngraph TD\nA --> B\n```")
    assert "A --&gt; B" in out
    assert soup(out).find("pre") is not None


def test_line_breaks_follow_the_strict_setting(convert):
    assert soup(convert("one\ntwo")).find("br") is None
    config = md2blogger.prepare_config({"obsidian": {"strict_line_breaks": False}})
    assert soup(md2blogger.convert("one\ntwo", config)).find("br") is not None


def test_escaped_pipes_in_tables(convert):
    out = convert("| a | b |\n|---|---|\n| [[Page\\|Alias]] | ![[pic.png\\|80]] |")
    cells = soup(out).find_all("td")
    assert cells[0].get_text() == "Alias"
    assert cells[1].find("img")["width"] == "80"


# --- Images and attachments (default mode) -----------------------------------

def test_wiki_images_with_sizes_and_alt_text(convert):
    imgs = soup(convert("![[a.png|300]] ![[b.jpg|100x145]] ![[c.png|A cat|50]] ![[d]]")).find_all("img")
    assert [(i["src"], i["alt"], i.get("width"), i.get("height")) for i in imgs] == [
        ("a.png", "a.png", "300", None),
        ("b.jpg", "b.jpg", "100", "145"),
        ("c.png", "A cat", "50", None),
        ("d.png", "d.png", None, None),
    ]


def test_markdown_images_with_obsidian_sizes(convert):
    imgs = soup(convert("![Engelbart|100x145](https://x.org/e.jpg) ![250](https://x.org/f.jpg)")).find_all("img")
    assert [(i["alt"], i["width"], i.get("height")) for i in imgs] == [("Engelbart", "100", "145"), ("", "250", None)]


def test_image_base_url_and_url_encoding():
    config = md2blogger.prepare_config({"obsidian": {"image_base_url": "https://cdn.example.com/img/"}})
    img = soup(md2blogger.convert("![[Folder/My photo (1) é.png]]", config)).find("img")
    assert img["src"] == "https://cdn.example.com/img/Folder/My%20photo%20%281%29%20%C3%A9.png"


def test_audio_video_and_pdf_embeds_become_links(convert):
    links = soup(convert("![[talk.mp3]] ![[clip.mp4]] ![[Document.pdf#page=3]]")).find_all("a")
    assert [(a["href"], a.get_text()) for a in links] == [
        ("talk.mp3", "talk.mp3"), ("clip.mp4", "clip.mp4"), ("Document.pdf", "Document.pdf"),
    ]


# --- Embedded notes -----------------------------------------------------------

def embed_box(html: str):
    return next(d for d in soup(html).find_all("div") if "border-left: 2px solid" in d.get("style", ""))


def test_embedding_a_whole_note(convert, vault):
    note = vault / "Notes" / "Post.md"
    out = convert("Before\n\n![[Other note]]\n\nAfter", note_path=note, vault=md2blogger.Vault(vault))
    box = embed_box(out)
    assert "Intro paragraph." in box.get_text()
    assert "tags:" not in box.get_text()


def test_embedding_a_heading_section(convert, vault):
    out = convert("![[Other note#Details]]", note_path=vault / "Notes" / "Post.md", vault=md2blogger.Vault(vault))
    box_text = embed_box(out).get_text()
    assert "Detail text." in box_text and "Deeper." in box_text
    assert "Next text." not in box_text and "Intro" not in box_text


def test_embedding_blocks(convert, vault):
    kwargs = {"note_path": vault / "Notes" / "Post.md", "vault": md2blogger.Vault(vault)}
    assert text_of(str(embed_box(convert("![[Other note#^quote-me]]", **kwargs)))) == "A quoted block"
    assert text_of(str(embed_box(convert("![[Other note#^item-two]]", **kwargs)))) == "second item"


def test_missing_embedded_note_is_reported(convert, vault):
    warnings = []
    out = convert("![[Nowhere]]", note_path=vault / "Notes" / "Post.md",
                  vault=md2blogger.Vault(vault), warnings=warnings)
    assert "Nowhere" in out
    assert any("Nowhere" in w for w in warnings)


def test_a_note_embedding_itself_does_not_loop(convert, vault):
    loop = vault / "Notes" / "Loop.md"
    loop.write_text("Loop text\n\n![[Loop]]\n", encoding="utf-8")
    warnings = []
    out = convert(loop.read_text(encoding="utf-8"), note_path=loop, vault=md2blogger.Vault(vault), warnings=warnings)
    assert out.count("Loop text") == 1
    assert any("inside itself" in w for w in warnings)
