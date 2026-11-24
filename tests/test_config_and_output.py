"""Configuration handling, output formatting and the command line."""

import json

import pytest

import md2blogger
from conftest import CONFIG_PATH, ROOT, soup


# --- Configuration --------------------------------------------------------------

def test_shipped_config_matches_the_built_in_defaults():
    shipped = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert md2blogger.prepare_config(shipped) == md2blogger.prepare_config({})


def test_a_0_9_config_still_works_and_gets_the_new_defaults():
    old = {
        "forbidden_tags": ["script", "style"],
        "styles": {"p": "color: red;"},
        "code_block_wrapper": "<div>{content}</div>",
        "obsidian": {"image_base_url": "https://x/", "image_extension_default": ".jpg"},
    }
    config = md2blogger.prepare_config(old)
    assert config["styles"]["p"] == "color: red;"
    assert config["styles"][".callout"] == md2blogger.DEFAULT_CONFIG["styles"][".callout"]
    assert config["obsidian"]["tags"] == "label"
    out = md2blogger.convert("Hi ![[pic]]\n\n> [!tip] T", config)
    assert soup(out).find("p")["style"] == "color: red;"
    assert soup(out).find("img")["src"] == "https://x/pic.jpg"


@pytest.mark.parametrize("bad, message", [
    ({"obsidian": {"tags": "loud"}}, "obsidian.tags"),
    ({"obsidian": {"math": "katex"}}, "obsidian.math"),
    ({"code_block_wrapper": "<div></div>"}, "{content}"),
    ({"callouts": {"types": {"note": {"color": "blue", "icon": ""}}}}, "colour"),
    ({"styles": {"p": 3}}, "styles"),
    ({"forbidden_tags": "script"}, "forbidden_tags"),
    ({"allow_raw_html": "yes"}, "allow_raw_html"),
])
def test_invalid_config_values_are_explained(bad, message):
    with pytest.raises(md2blogger.UserError, match=message.replace("{", r"\{").replace("}", r"\}")):
        md2blogger.prepare_config(bad)


def test_invalid_json_is_reported_with_its_position(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text('{"styles": {,}}', encoding="utf-8")
    note = tmp_path / "n.md"
    note.write_text("x", encoding="utf-8")
    assert md2blogger.main([str(note), "-c", str(bad)]) == 1
    assert "not valid JSON (line 1" in capsys.readouterr().err


def test_missing_input_and_config_are_errors(tmp_path, capsys):
    assert md2blogger.main([str(tmp_path / "none.md"), "-c", str(CONFIG_PATH)]) == 1
    assert "input file" in capsys.readouterr().err
    assert md2blogger.main([str(tmp_path / "none.md"), "-c", str(tmp_path / "none.json")]) == 1
    assert "config file" in capsys.readouterr().err


# --- Output formatting --------------------------------------------------------

def test_no_spaces_are_added_between_inline_elements(convert):
    out = convert("**un**believable, *it*'s (`x`) fine")
    assert soup(out).get_text() == "unbelievable, it's (x) fine"


def test_non_breaking_spaces_survive(convert):
    assert "\u00a0" in soup(convert("non&nbsp;breaking")).get_text()


def test_code_blocks_keep_whitespace_and_special_characters(convert):
    out = convert("```python\ndef f(a, b):\n    if a < b and b & 1:\n        return '<x>'\n```")
    code = soup(out).find("code")
    assert code.get_text() == "\ndef f(a, b):\n    if a < b and b & 1:\n        return '<x>'\n"
    assert "&amp;lt;" not in out


def test_code_blocks_are_wrapped_and_styled(convert, config):
    out = convert("```\nx\n```")
    wrapper = soup(out).find("div")
    assert wrapper["style"].startswith("background-color: #f4f4f4")
    assert wrapper.find("pre")["style"] == config["styles"]["pre"]


def test_every_table_cell_is_styled(convert, config):
    out = convert("| a | b |\n|:-:|---|\n| 1 | 2 |")
    cells = soup(out).find_all(["th", "td"])
    assert len(cells) == 4
    assert all("border: 1px solid #ddd" in c["style"] for c in cells)
    assert "text-align:center" in cells[0]["style"].replace(" ", "")


def test_classes_and_hooks_do_not_reach_the_output(convert):
    out = convert("> [!tip] T\n> B\n\n==🔴x== #tag\n\n- [x] t\n\n```py\nx\n```")
    names = {name for tag in soup(out).find_all(True) for name in tag.attrs}
    assert names <= {"style", "id", "open", "href", "src", "alt", "width", "height", "title"}


def test_output_is_indented(convert):
    out = convert("- one\n  - two")
    assert "\n  <li" in out and "\n      <li" in out


# --- Command line -------------------------------------------------------------

def test_version_flag(capsys):
    with pytest.raises(SystemExit):
        md2blogger.main(["--version"])
    assert "1.0" in capsys.readouterr().out
    assert md2blogger.__version__ == "1.0"


def test_writes_the_output_file(tmp_path, capsys):
    note = tmp_path / "n.md"
    note.write_text("\ufeff# Title\n", encoding="utf-8")  # a BOM is ignored
    out = tmp_path / "n.html"
    assert md2blogger.main([str(note), "-o", str(out), "-c", str(CONFIG_PATH)]) == 0
    assert soup(out.read_text(encoding="utf-8")).find("h1").get_text() == "Title"
    assert "Output written to" in capsys.readouterr().out


def test_sample_converts_without_warnings(tmp_path, capsys):
    out = tmp_path / "sample.html"
    assert md2blogger.main([str(ROOT / "sample.md"), "-o", str(out), "-c", str(CONFIG_PATH)]) == 0
    assert "Warning" not in capsys.readouterr().err
    parsed = soup(out.read_text(encoding="utf-8"))
    assert parsed.find("table") is not None
    assert parsed.find(["div", "details"]) is not None
