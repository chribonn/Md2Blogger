"""Shared fixtures for the Md2Blogger test suite."""

from pathlib import Path

import pytest
from bs4 import BeautifulSoup

import md2blogger

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"

# Any bytes will do: the converter copies image files, it never decodes them.
PNG = b"\x89PNG\r\n\x1a\n fake image data"


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Never read or write the real per-user settings file."""
    path = tmp_path / "user-settings" / "settings.json"
    monkeypatch.setenv(md2blogger.SETTINGS_ENV, str(path))
    return path


@pytest.fixture
def config():
    return md2blogger.prepare_config({})


@pytest.fixture
def convert(config):
    """convert(text, **kwargs) with the default configuration."""
    def _convert(text, **kwargs):
        return md2blogger.convert(text, config, **kwargs)
    return _convert


@pytest.fixture
def vault(tmp_path):
    """A small Obsidian vault:

    vault/.obsidian/
    vault/Attachments/2026/photo one.png
    vault/Attachments/diagram.svg
    vault/Notes/Post.md
    vault/Notes/Other note.md
    vault/Notes/local.png
    """
    root = tmp_path / "vault"
    (root / ".obsidian").mkdir(parents=True)
    (root / "Attachments" / "2026").mkdir(parents=True)
    (root / "Attachments" / "2026" / "photo one.png").write_bytes(PNG)
    (root / "Attachments" / "diagram.svg").write_bytes(b"<svg/>")
    notes = root / "Notes"
    notes.mkdir()
    (notes / "local.png").write_bytes(PNG)
    (notes / "Post.md").write_text("# Post\n\n![[photo one.png]]\n", encoding="utf-8")
    (notes / "Other note.md").write_text(
        "---\ntags: [x]\n---\n"
        "Intro paragraph.\n\n"
        "## Details\n\nDetail text.\n\n### Sub detail\n\nDeeper.\n\n"
        "## Next\n\nNext text.\n\n"
        "A quoted block ^quote-me\n\n"
        "- first\n- second item ^item-two\n",
        encoding="utf-8",
    )
    return root


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def all_attribute_names(html: str) -> set[str]:
    return {name for tag in soup(html).find_all(True) for name in tag.attrs}
