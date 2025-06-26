import csv
import json
import os
from pathlib import Path
import pytest
import re

from main import main


def count_images_in_chapters(chapter_files, chapter_format):
    """
    Helper function to count images in chapter, to 
    test expected vs. actual
    """
    count = 0
    for chapter_file in chapter_files:
        text = chapter_file.read_text()
        if chapter_format == "html":
            count += len(re.findall(r"<img\s", text))
        elif chapter_format == "adoc":
            count += len(re.findall(r"image::", text))
    return count

def run_integration(tmp_path, testdata_dir, chapter_format, monkeypatch):
    """
    Basic end-to-end test of script's business logic
    """
    
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

    class FakeGenerator:
        """
        Dummy AltTextGenerator class
        """
        def generate_alt_text(self, image_obj, data_uri):
            return f"ALT for {image_obj.image_src}"
        
    # Patch AltTextGenerator to avoid real API calls
    monkeypatch.setattr("main.AltTextGenerator", lambda: FakeGenerator())

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
    """
    Run basic E2E for Asciidoc and HTML use cases 
    """
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

    # Patch AltTextGenerator to avoid real API calls
    class FakeGenerator:
        def generate_alt_text(self, image_obj, data_uri):
            return f"ALT for {image_obj.image_src}"
    monkeypatch.setattr("main.AltTextGenerator", lambda: FakeGenerator())

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

def test_do_not_replace_existing_alt_text(tmp_path, monkeypatch):
    """Test do_not_replace_existing_alt_text use case."""
    # Create a simple HTML file with two images
    test_html = """
    <html>
    <body>
        <img src="images/existing.png" alt="Existing alt text">
        <img src="images/missing.png" alt="">
    </body>
    </html>
    """
    chapter_file = tmp_path / "chapter.html"
    chapter_file.write_text(test_html)

    # Create images directory and dummy image files
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    (images_dir / "existing.png").touch()
    (images_dir / "missing.png").touch()

    # Create minimal atlas.json
    atlas_json = {
        "files": ["chapter.html"]
    }
    atlas_path = tmp_path / "atlas.json"
    atlas_path.write_text(json.dumps(atlas_json))

    class FakeGenerator:
        def generate_alt_text(self, image_obj, data_uri):
            return f"ALT for {image_obj.image_src}"

    # Patch AltTextGenerator to return predictable alt text
    monkeypatch.setattr("main.AltTextGenerator", lambda: FakeGenerator())

    # Patch input to auto-confirm
    monkeypatch.setattr("builtins.input", lambda _: "y")

    # Run main with --do-not-replace-existing-alt-text flag
    monkeypatch.setattr(
        "sys.argv",
        ["script_name", str(atlas_path), "--do-not-replace-existing-alt-text"],
    )

    # Change working directory to tmp_path
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main()
    finally:
        os.chdir(old_cwd)

    # Read the modified HTML
    modified_content = chapter_file.read_text()

    # Check that the existing alt text wasn't changed
    assert 'src="images/existing.png" alt="Existing alt text"' in modified_content, \
        "Existing alt text should not have been replaced"

    # Check that missing alt text was added
    assert 'src="images/missing.png" alt="ALT for images/missing.png"' in modified_content, \
        "Missing alt text should have been added"

    # Assert: Backup file was created
    backup_files = list(tmp_path.glob("backup_*.json"))
    assert backup_files, "Backup file was not created"

def test_load_from_json(tmp_path, monkeypatch):
    """Test loading and processing data from a JSON backup file."""
    # Create test chapter files
    chapter1 = tmp_path / "chapter1.html"
    chapter1.write_text("""
    <html><body>
        <img src="images/img1.png" alt="">
        <img src="images/img2.png" alt="">
    </body></html>
    """)

    # Create images directory and dummy image files
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    (images_dir / "img1.png").touch()
    (images_dir / "img2.png").touch()

    # Create a mock backup JSON with some images already processed
    mock_backup = [
        {
            "filepath": str(chapter1),
            "content": chapter1.read_text(),
            "chapter_format": "html",
            "images": [
                {
                    "chapter_filepath": str(chapter1),
                    "original_img_elem_str": '<img src="images/img1.png" alt="">',
                    "image_src": "images/img1.png",
                    "image_filepath": str(images_dir / "img1.png"),
                    "preceding_para_text": "",
                    "succeeding_para_text": "",
                    "caption_text": "",
                    "original_alt_text": "",
                    "generated_alt_text": "Already generated alt text",  # This one is done
                    "alt_text_replaced": False
                },
                {
                    "chapter_filepath": str(chapter1),
                    "original_img_elem_str": '<img src="images/img2.png" alt="">',
                    "image_src": "images/img2.png",
                    "image_filepath": str(images_dir / "img2.png"),
                    "preceding_para_text": "",
                    "succeeding_para_text": "",
                    "caption_text": "",
                    "original_alt_text": "",
                    "generated_alt_text": None,  # This one needs processing
                    "alt_text_replaced": False
                }
            ]
        }
    ]

    # Write mock backup to JSON file
    backup_file = tmp_path / "mock_backup.json"
    backup_file.write_text(json.dumps(mock_backup))

    # Create atlas.json
    atlas_json = {
        "files": ["chapter1.html"]
    }
    atlas_path = tmp_path / "atlas.json"
    atlas_path.write_text(json.dumps(atlas_json))

    class FakeGenerator:
        def generate_alt_text(self, image_obj, data_uri):
            return f"ALT for {image_obj.image_src}"
    
    # Patch AltTextGenerator to return predictable alt text
    monkeypatch.setattr("main.AltTextGenerator", lambda: FakeGenerator())

    # Patch input to auto-confirm
    monkeypatch.setattr("builtins.input", lambda _: "y")

    # Run main with --load-data-from-json flag
    monkeypatch.setattr(
        "sys.argv",
        ["script_name", str(atlas_path), "--load-data-from-json", str(backup_file)],
    )

    # Change working directory to tmp_path
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main()
    finally:
        os.chdir(old_cwd)

    # Read the modified HTML
    modified_content = chapter1.read_text()

    # Check that the already-processed image kept its alt text
    assert 'src="images/img1.png" alt="Already generated alt text"' in modified_content, \
        "Previously generated alt text should be preserved"

    # Check that the unprocessed image got new alt text
    assert 'src="images/img2.png" alt="ALT for images/img2.png"' in modified_content, \
        "New alt text should be generated for unprocessed image"

    # Assert: New backup file was created
    new_backup_files = list(tmp_path.glob("backup_*.json"))
    assert new_backup_files, "New backup file was not created"

def test_csv_based_integration_update(tmp_path, monkeypatch):
    """
    End-to-end test for update_alt_text_from_csv use case
    """
    # Setup test HTML file
    chapter_html = tmp_path / "chapter.html"
    chapter_html.write_text("""
    <html>
    <body>
    <img src="images/dog.png" alt="">
    <img src="images/cat.png" alt="">
    <img src="images/ignored.png" alt="">
    </body>
    </html>
    """, encoding="utf-8")

    # Setup images
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    (images_dir / "dog.png").touch()
    (images_dir / "cat.png").touch()
    (images_dir / "ignored.png").touch()

    # Atlas.json pointing to our chapter
    atlas_path = tmp_path / "atlas.json"
    atlas_path.write_text(json.dumps({"files": [chapter_html.name]}))

    # CSV with updated alt text for two images
    csv_path = tmp_path / "alt_text_updates.csv"
    with csv_path.open("w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["images/dog.png", "A happy dog."])
        writer.writerow(["images/cat.png", "A lazy cat."])

    # Patch sys.argv to pass update-alt-text-from-csv
    monkeypatch.setattr("sys.argv", [
        "script_name",
        str(atlas_path),
        "--update-alt-text-from-csv",
        str(csv_path),
    ])

    # Patch input to auto-confirm prompts
    monkeypatch.setattr("builtins.input", lambda _: "y")

    # Change working directory to tmp_path
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        main()
    finally:
        os.chdir(old_cwd)

    # Validate HTML was updated correctly
    updated_content = chapter_html.read_text()
    assert 'src="images/dog.png" alt="A happy dog."' in updated_content
    assert 'src="images/cat.png" alt="A lazy cat."' in updated_content
    assert 'src="images/ignored.png" alt=""' in updated_content or 'src="images/ignored.png" alt=""' in updated_content

    # Check review CSV was written
    review_csvs = list(tmp_path.glob("review_*.csv"))
    assert review_csvs, "No review CSV was generated."

    rows = [row for row in csv.reader(review_csvs[0].open())]
    assert any("dog.png" in row[0] and "A happy dog." in row[1] for row in rows)
    assert any("cat.png" in row[0] and "A lazy cat." in row[1] for row in rows)

    # Check JSON backup file was written
    backup_files = list(tmp_path.glob("backup_*.json"))
    assert backup_files, "No backup JSON was written."

    # check alt text of first image was replaced as expected
    dog_match = re.search(r'<img\s+[^>]*src="images/dog.png"[^>]*alt="([^"]+)"', updated_content)
    assert dog_match and dog_match.group(1) == "A happy dog."

    # check image to be ignored was not changed
    ignored_match = re.search(r'<img\s+[^>]*src="images/ignored.png"[^>]*alt="([^"]*?)"', updated_content)
    assert ignored_match and ignored_match.group(1) == ""
