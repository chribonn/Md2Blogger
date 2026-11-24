"""--imgfolder: copying images next to the HTML, and remembering the vault."""

import json

import md2blogger
from conftest import CONFIG_PATH, PNG, soup


def run(args, capsys):
    code = md2blogger.main([*args, "-c", str(CONFIG_PATH)])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def image_sources(html_file):
    return [img["src"] for img in soup(html_file.read_text(encoding="utf-8")).find_all("img")]


# --- Default mode -------------------------------------------------------------

def test_without_imgfolder_references_are_left_as_written(vault, tmp_path, capsys):
    out_file = tmp_path / "out" / "post.html"
    out_file.parent.mkdir()
    code, _, _ = run([str(vault / "Notes" / "Post.md"), "-o", str(out_file)], capsys)
    assert code == 0
    assert image_sources(out_file) == ["photo%20one.png"]
    assert not (tmp_path / "out" / "md2blg").exists()


# --- Copying ------------------------------------------------------------------

def test_images_are_copied_mirroring_the_vault(vault, tmp_path, capsys):
    note = vault / "Notes" / "Post.md"
    note.write_text(
        "![[photo one.png|200]]\n\n![[diagram.svg]]\n\n![[local.png]]\n\n"
        "![again](../Attachments/2026/photo%20one.png)\n\n![web](https://example.com/x.png)\n",
        encoding="utf-8",
    )
    out_file = tmp_path / "export" / "post.html"
    out_file.parent.mkdir()
    code, _, err = run([str(note), "-o", str(out_file), "--imgfolder"], capsys)
    assert code == 0, err

    folder = tmp_path / "export" / "md2blg"
    assert (folder / "Attachments" / "2026" / "photo one.png").read_bytes() == PNG
    assert (folder / "Attachments" / "diagram.svg").exists()
    assert (folder / "Notes" / "local.png").exists()
    assert image_sources(out_file) == [
        "md2blg/Attachments/2026/photo%20one.png",
        "md2blg/Attachments/diagram.svg",
        "md2blg/Notes/local.png",
        "md2blg/Attachments/2026/photo%20one.png",
        "https://example.com/x.png",
    ]
    assert "3 image(s) copied" in err


def test_default_folder_name_is_made_unique(vault, tmp_path, capsys):
    out_file = tmp_path / "post.html"
    (tmp_path / "md2blg").mkdir()
    run([str(vault / "Notes" / "Post.md"), "-o", str(out_file), "--imgfolder"], capsys)
    run([str(vault / "Notes" / "Post.md"), "-o", str(out_file), "--imgfolder"], capsys)
    assert (tmp_path / "md2blg_2" / "Attachments" / "2026" / "photo one.png").exists()
    assert (tmp_path / "md2blg_3" / "Attachments" / "2026" / "photo one.png").exists()
    assert image_sources(out_file) == ["md2blg_3/Attachments/2026/photo%20one.png"]


def test_named_folder_is_reused(vault, tmp_path, capsys):
    out_file = tmp_path / "post.html"
    for _ in range(2):
        code, _, _ = run([str(vault / "Notes" / "Post.md"), "-o", str(out_file), "--imgfolder", "pictures"], capsys)
        assert code == 0
    assert (tmp_path / "pictures" / "Attachments" / "2026" / "photo one.png").exists()
    assert not (tmp_path / "pictures_2").exists()
    assert image_sources(out_file) == ["pictures/Attachments/2026/photo%20one.png"]


def test_stdout_output_puts_the_folder_in_the_current_directory(vault, tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, out, _ = run([str(vault / "Notes" / "Post.md"), "--imgfolder"], capsys)
    assert code == 0
    assert 'src="md2blg/Attachments/2026/photo%20one.png"' in out
    assert (tmp_path / "md2blg" / "Attachments" / "2026" / "photo one.png").exists()


def test_files_outside_the_vault_and_note_folder_are_not_copied(vault, tmp_path, capsys):
    secret = tmp_path / "secret.png"
    secret.write_bytes(PNG)
    note = vault / "Notes" / "Post.md"
    note.write_text("![x](../../secret.png)\n\n![[missing.png]]\n", encoding="utf-8")
    out_file = tmp_path / "out.html"
    code, _, err = run([str(note), "-o", str(out_file), "--imgfolder"], capsys)
    assert code == 0
    copied = list((tmp_path / "md2blg").rglob("*.png")) if (tmp_path / "md2blg").exists() else []
    assert copied == []
    assert "missing.png" in err and "secret.png" in err


def test_non_image_files_are_never_copied(vault, tmp_path, capsys):
    (vault / "Notes" / "notes.txt").write_text("private", encoding="utf-8")
    note = vault / "Notes" / "Post.md"
    note.write_text("![x](notes.txt)\n", encoding="utf-8")
    run([str(note), "-o", str(tmp_path / "out.html"), "--imgfolder"], capsys)
    assert not (tmp_path / "md2blg" / "Notes" / "notes.txt").exists()


def test_same_relative_path_from_two_places_keeps_both(vault, tmp_path, capsys):
    drafts = tmp_path / "drafts"
    (drafts / "Attachments" / "2026").mkdir(parents=True)
    (drafts / "Attachments" / "2026" / "photo one.png").write_bytes(b"different")
    note = drafts / "Draft.md"
    # The first link resolves next to the note, the second only exists in the vault
    note.write_text("![[Attachments/2026/photo one.png]]\n\n![[2026/photo one.png]]\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    code, _, err = run([str(note), "-o", str(out_dir / "d.html"), "--imgfolder", "--vault", str(vault)], capsys)
    assert code == 0, err
    assert image_sources(out_dir / "d.html") == [
        "md2blg/Attachments/2026/photo%20one.png",
        "md2blg/Attachments/2026/photo%20one_2.png",
    ]
    copies = out_dir / "md2blg" / "Attachments" / "2026"
    assert (copies / "photo one.png").read_bytes() == b"different"
    assert (copies / "photo one_2.png").read_bytes() == PNG


def test_collisions_add_a_suffix_instead_of_overwriting(vault, tmp_path):
    other = tmp_path / "elsewhere"
    (other / "Notes").mkdir(parents=True)
    (other / "Notes" / "local.png").write_bytes(b"other image")
    note = other / "note.md"
    note.write_text("", encoding="utf-8")
    exporter = md2blogger.ImageExporter(tmp_path / "out" / "img", tmp_path / "out")
    ctx = md2blogger.Context(
        config=md2blogger.prepare_config({}), note_path=note.resolve(), vault=md2blogger.Vault(vault),
        allowed_roots=(vault.resolve(), other.resolve()), home_dir=other.resolve(),
    )
    first = exporter.export(vault / "Notes" / "local.png", ctx)
    second = exporter.export(other / "Notes" / "local.png", ctx)
    assert first == "img/Notes/local.png"
    assert second == "img/Notes/local_2.png"
    assert exporter.export(vault / "Notes" / "local.png", ctx) == first
    assert exporter.count == 2


# --- Finding the vault ----------------------------------------------------------

def test_vault_is_detected_from_the_obsidian_folder(vault, tmp_path, capsys):
    note = vault / "Notes" / "Post.md"
    code, _, err = run([str(note), "-o", str(tmp_path / "o.html"), "--imgfolder"], capsys)
    assert code == 0
    assert "no Obsidian vault" not in err
    assert (tmp_path / "md2blg" / "Attachments" / "2026" / "photo one.png").exists()


def test_vault_option_is_remembered(vault, tmp_path, capsys, isolated_settings):
    draft = tmp_path / "draft.md"
    draft.write_text("![[photo one.png]]\n", encoding="utf-8")

    code, _, err = run([str(draft), "-o", str(tmp_path / "a.html"), "--imgfolder", "--vault", str(vault)], capsys)
    assert code == 0
    assert "Remembered Obsidian vault" in err
    assert json.loads(isolated_settings.read_text(encoding="utf-8"))["vault_path"] == str(vault.resolve())

    code, _, err = run([str(draft), "-o", str(tmp_path / "b.html"), "--imgfolder", "img2"], capsys)
    assert code == 0, err
    assert image_sources(tmp_path / "b.html") == ["img2/Attachments/2026/photo%20one.png"]


def test_missing_remembered_vault_is_reported(tmp_path, capsys, isolated_settings):
    isolated_settings.parent.mkdir(parents=True)
    isolated_settings.write_text(json.dumps({"vault_path": str(tmp_path / "gone")}), encoding="utf-8")
    draft = tmp_path / "draft.md"
    draft.write_text("Hi\n", encoding="utf-8")
    code, _, err = run([str(draft), "-o", str(tmp_path / "a.html")], capsys)
    assert code == 0
    assert "no longer exists" in err


def test_without_a_vault_images_next_to_the_note_are_still_copied(tmp_path, capsys):
    notes = tmp_path / "notes"
    (notes / "img").mkdir(parents=True)
    (notes / "img" / "pic.png").write_bytes(PNG)
    note = notes / "n.md"
    note.write_text("![[img/pic.png]]\n\n![p](img/pic.png)\n", encoding="utf-8")
    code, _, err = run([str(note), "-o", str(tmp_path / "n.html"), "--imgfolder"], capsys)
    assert code == 0
    assert "no Obsidian vault is known" in err
    assert image_sources(tmp_path / "n.html") == ["md2blg/img/pic.png", "md2blg/img/pic.png"]


def test_bad_vault_path_is_an_error(tmp_path, capsys):
    note = tmp_path / "n.md"
    note.write_text("x", encoding="utf-8")
    code, _, err = run([str(note), "--vault", str(tmp_path / "nope")], capsys)
    assert code == 1
    assert "not found" in err
