"""The output is pasted straight into Blogger, so it must never carry script."""

import md2blogger
from conftest import all_attribute_names, soup


def has_event_handler(html: str) -> bool:
    return any(name.lower().startswith("on") for name in all_attribute_names(html))


def test_image_alt_text_cannot_break_out_of_its_attribute(convert):
    out = convert('![x" onerror="alert(1)](a.png)')
    img = soup(out).find("img")
    assert img["alt"] == 'x" onerror="alert(1)'
    assert not has_event_handler(out)


def test_link_title_cannot_break_out_of_its_attribute(convert):
    out = convert('[link](https://a.com "t&quot; onmouseover=&quot;alert(1)")')
    assert soup(out).find("a")["title"] == 't" onmouseover="alert(1)'
    assert not has_event_handler(out)


def test_escaped_html_in_text_stays_text(convert):
    out = convert("Use the &lt;img src=x onerror=alert(1)&gt; tag, and 5 < 6 & 7 > 3.")
    parsed = soup(out)
    assert parsed.find("img") is None
    assert "<img src=x onerror=alert(1)>" in parsed.get_text()
    assert "5 < 6 & 7 > 3." in parsed.get_text()


def test_event_handlers_are_removed_from_raw_html(convert):
    out = convert('<img src="x.png" onerror="alert(1)">\n\n<p onclick="alert(2)">Hi</p>')
    assert soup(out).find("img")["src"] == "x.png"
    assert not has_event_handler(out)


def test_javascript_and_data_urls_are_removed(convert):
    out = convert(
        '<a href="javascript:alert(1)">a</a> <a href=" JaVaScRiPt:alert(1)">b</a> '
        '<img src="data:text/html;base64,PHNjcmlwdD4="> [c](javascript:alert(1)) '
        '![d](javascript:alert(1))'
    )
    parsed = soup(out)
    assert parsed.find("a") is None  # links without a safe URL become plain text
    assert all(not img.get("src") for img in parsed.find_all("img"))
    assert "javascript" not in out.lower() and "data:" not in out
    assert " ".join(parsed.get_text().split()) == "a b c"


def test_safe_urls_are_kept(convert):
    out = convert("[a](https://example.com) [b](mailto:me@example.com) [c](page.html) [d](#top)")
    assert [a["href"] for a in soup(out).find_all("a")] == [
        "https://example.com", "mailto:me@example.com", "page.html", "#top",
    ]


def test_local_file_links_keep_their_text_but_lose_the_path(convert):
    out = convert(r"[Absolute Link](file://D:\chrib\secret.html) is a great file to read")
    assert soup(out).find("a") is None
    assert soup(out).get_text() == "Absolute Link is a great file to read"
    assert "chrib" not in out


def test_script_and_style_are_removed_with_their_content(convert):
    out = convert("<script>alert(1)</script>\n\n<style>body{display:none}</style>\n\nAfter")
    assert "alert" not in out
    assert "display:none" not in out
    assert "After" in out


def test_frames_forms_and_svg_are_removed(convert):
    out = convert(
        '<iframe src="https://evil.example"></iframe>\n\n'
        '<form action="https://evil.example"><input name="pw"><button>Go</button></form>\n\n'
        '<svg><script>alert(1)</script></svg>'
    )
    names = {tag.name for tag in soup(out).find_all(True)}
    assert not names & {"iframe", "form", "input", "button", "svg", "script"}
    assert "alert" not in out


def test_html_comments_are_removed(convert):
    assert "secret" not in convert("Visible <!-- secret --> text")


def test_forbidden_tags_in_config_are_stripped_but_content_kept():
    config = md2blogger.prepare_config({"forbidden_tags": ["table", "thead", "tbody", "tr", "th", "td"]})
    out = md2blogger.convert("| a | b |\n|---|---|\n| 1 | 2 |", config)
    assert soup(out).find("table") is None
    assert "a" in out and "2" in out


def test_emptying_forbidden_tags_does_not_allow_scripts():
    config = md2blogger.prepare_config({"forbidden_tags": []})
    out = md2blogger.convert('<script>alert(1)</script><iframe src="x"></iframe>ok', config)
    assert "alert" not in out
    assert soup(out).find("iframe") is None


def test_raw_html_can_be_switched_off():
    config = md2blogger.prepare_config({"allow_raw_html": False})
    out = md2blogger.convert("<b>bold</b>", config)
    assert soup(out).find("b") is None
    assert "<b>bold</b>" in soup(out).get_text()


def test_wikilink_url_template_cannot_inject_script():
    config = md2blogger.prepare_config({"obsidian": {"wikilink_url_template": "javascript:alert('{name}')"}})
    out = md2blogger.convert("[[Other]]", config)
    assert "javascript" not in out


def test_private_obsidian_content_is_not_published(convert):
    out = convert("---\nsecret_property: 42\n---\nPublic %%private remark%% text\n\n%%\nPrivate block\n%%")
    assert "secret_property" not in out
    assert "private" not in out.lower()
    assert "Public" in out
