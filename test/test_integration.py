import os
from pathlib import Path
import pytest
import re

from main import main


def count_images_in_chapters(chapter_files, chapter_format):
    count = 0
    for chapter_file in chapter_files:
        text = chapter_file.read_text()
        if chapter_format == "html":
            count += len(re.findall(r"<img\s", text))
        elif chapter_format == "adoc":
            count += len(re.findall(r"image::", text))
    return count

def run_integration(tmp_path, testdata_dir, chapter_format, monkeypatch):
    # Copy test data files to tmp_path
    for file in Path(testdata_dir).iterdir():
        target = tmp_path / file.name
        if file.is_file():
            target.write_bytes(file.read_bytes())
        elif file.is_dir():
            target.mkdir()
            for subfile in file.iterdir():
                (target / subfile.name).write_bytes(subfile.read_bytes())

    atlas_path = tmp_path / "atlas.json"

    # Patch AllTextGenerator to avoid real API calls
    class FakeGenerator:
        def generate_alt_text(self, image_obj, data_uri):
            return f"ALT for {image_obj.image_src}"
    monkeypatch.setattr("main.AllTextGenerator", lambda: FakeGenerator())

    # Patch input to auto-confirm
    monkeypatch.setattr("builtins.input", lambda _: "y")

    # Patch sys.argv to simulate command-line args
    monkeypatch.setattr(
        "sys.argv",
        ["script_name", str(atlas_path)],
    )

    # Find all chapter files before running main
    chapter_files = list(tmp_path.glob(f"*.{chapter_format}*"))
    initial_image_count = count_images_in_chapters(chapter_files, chapter_format)

    # Change working directory to tmp_path
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main()
    finally:
        os.chdir(old_cwd)

    # count "ALT for" occurrences
    alt_for_count = 0
    for chapter_file in chapter_files:
        content = chapter_file.read_text()
        alt_for_count += content.count("ALT for")

    assert alt_for_count == initial_image_count, (
        f"Expected {initial_image_count} alt texts, found {alt_for_count}"
    )

    # Assert: Backup file was created
    backup_files = list(tmp_path.glob("backup_*.json"))
    assert backup_files, "Backup file was not created"

@pytest.mark.parametrize("testdata_dir,chapter_format", [
    ("test/testdata/html_case", "html"),
    ("test/testdata/asciidoc_case", "adoc"),
])
def test_full_integration(tmp_path, testdata_dir, chapter_format, monkeypatch):
    run_integration(tmp_path, testdata_dir, chapter_format, monkeypatch)
