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

def run_integration_with_filter(tmp_path, testdata_dir, chapter_format, monkeypatch, image_filter_list):
    """Run integration test with image file filter."""
    # Create image filter file
    filter_file = tmp_path / "image_filter.txt"
    filter_file.write_text("\n".join(image_filter_list))

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

    # Patch sys.argv to simulate command-line args with filter
    monkeypatch.setattr(
        "sys.argv",
        ["script_name", str(atlas_path), "--image-file-filter", str(filter_file)],
    )

    # Find all chapter files before running main
    chapter_files = list(tmp_path.glob(f"*.{chapter_format}*"))
    
    # Change working directory to tmp_path
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main()
    finally:
        os.chdir(old_cwd)

    # Check that only filtered images got alt text
    for chapter_file in chapter_files:
        content = chapter_file.read_text()
        for img_name in image_filter_list:
            if img_name in content:
                assert f"ALT for images/{img_name}" in content, f"Missing alt text for {img_name}"
        
        # Check that other images did not get alt text
        if chapter_format == "html":
            img_pattern = r'<img[^>]+src="([^"]+)"[^>]+alt="([^"]*)"'
        else:  # adoc
            img_pattern = r'image::([^\[]+)\[([^\]]*)\]'
            
        for match in re.finditer(img_pattern, content):
            img_src = match.group(1)
            alt_text = match.group(2)
            img_name = os.path.basename(img_src)
            if img_name not in image_filter_list and "ALT for" in alt_text:
                assert False, f"Image {img_name} should not have alt text but has: {alt_text}"

    # Assert: Backup file was created
    backup_files = list(tmp_path.glob("backup_*.json"))
    assert backup_files, "Backup file was not created"

def test_filtered_integration(tmp_path, monkeypatch):
    """Test integration with image file filter."""
    image_filter_list = [
        "cdb2_0101.png",
        "cdb2_0102.png",
        "cdb2_0201.png",
        "cdb2_0202.png"
    ]
    run_integration_with_filter(
        tmp_path=tmp_path,
        testdata_dir="test/testdata/asciidoc_case",
        chapter_format="adoc",
        monkeypatch=monkeypatch,
        image_filter_list=image_filter_list
    )