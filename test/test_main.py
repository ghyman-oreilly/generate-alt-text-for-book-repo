import csv
import html
import json
from pathlib import Path
import os

from main import (
    main, write_backup_to_json_file, read_backup_from_json_file, 
    write_review_data_to_csv_file, read_review_data_from_csv_file,
    merge_review_data_with_repo_data
    )
from chapters_and_images import Chapter, Image


def create_fake_project(tmp_path):
    # Create chapter HTML and atlas.json
    chapter_path = tmp_path / "chapter1.html"
    chapter_content = '<html><body><img src="images/dog.jpg" alt=""></body></html>'
    chapter_path.write_text(chapter_content)

    atlas_path = tmp_path / "atlas.json"
    atlas_path.write_text(json.dumps({"files": [chapter_path.name]}))

    # Create image matching filter
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    image_path = image_dir / "dog.jpg"
    image_path.write_bytes(b"fake_image_bytes")  # Actual image data not important

    # Create filter file
    filter_path = tmp_path / "filter.txt"
    filter_path.write_text("dog.jpg\n")

    return atlas_path, filter_path, chapter_path


def test_main_basic_end_to_end(tmp_path, monkeypatch):
    """Basic end-to-end test of script flow/logic"""
    # Set up files in tmp_path
    atlas_path, filter_path, chapter_path = create_fake_project(tmp_path)

    # Change working directory to tmp_path so backup file is created there
    old_cwd = os.getcwd()
    os.chdir(tmp_path)

    try:
        # Patch input to auto-confirm
        monkeypatch.setattr("builtins.input", lambda _: "y")

        # Patch sys.argv to simulate command-line args
        monkeypatch.setattr(
            "sys.argv",
            ["script_name", str(atlas_path), "--image-file-filter", str(filter_path)],
        )

        # Patch __file__ to allow template path resolution
        monkeypatch.setattr("generate_alt_text.__file__", str(Path(__file__)))

        # Patch AllTextGenerator so we don't hit a real API
        class FakeGenerator:
            def generate_alt_text(self, image_obj, data_uri):
                return "A realistic alt text"

        monkeypatch.setattr("main.AllTextGenerator", lambda: FakeGenerator())

        # Patch image encoding (base64 doesn't matter here)
        monkeypatch.setattr("process_repo_files.encode_image_to_base64", lambda path: "BASE64")
        monkeypatch.setattr("process_repo_files.get_mimetype", lambda path: "image/jpeg")

        # Run the script
        main()
    finally:
        os.chdir(old_cwd)

    # Final HTML file includes generated alt text
    updated_content = chapter_path.read_text()
    assert 'alt="A realistic alt text"' in updated_content

    # Check backup file was created
    backup_files = list(tmp_path.glob("backup_*.json"))
    assert len(backup_files) >= 1


def test_write_backup_to_json_file_and_read(tmp_path):
    """
    Test write_backup_to_json_file and
    read_backup_from_json_file
    """
    # Create a minimal Chapter object (using dummy values)
    chapter = Chapter(
        filepath=tmp_path / "chapter1.html",
        content="<html>test</html>",
        chapter_format="html",
        images=[],
    )
    backup_path = tmp_path / "backup_test.json"
    # Write backup
    write_backup_to_json_file([chapter], backup_path)
    assert backup_path.exists()
    # Read backup
    loaded = read_backup_from_json_file(backup_path)
    assert isinstance(loaded, list)
    assert len(loaded) == 1
    loaded_chapter = loaded[0]
    assert loaded_chapter.filepath == chapter.filepath
    assert loaded_chapter.content == chapter.content
    assert loaded_chapter.chapter_format == chapter.chapter_format
    assert loaded_chapter.images == chapter.images

def make_test_image(
    image_src: str,
    generated_alt_text: str = None,
    chapter_filepath: Path = Path("chapter1.html"),
    ) -> Image:
    """Factory to create fully-populated Image object for testing."""
    return Image(
    chapter_filepath=chapter_filepath,
    original_img_elem_str='<img src="{}" alt=""/>'.format(image_src),
    image_src=image_src,
    image_filepath=Path(image_src),
    preceding_para_text="",
    succeeding_para_text="",
    caption_text="",
    original_alt_text="",
    generated_alt_text=generated_alt_text,
    alt_text_replaced=False,
    )

def test_write_review_data_to_csv_file(tmp_path):
    """
    Unit test for write_review_data_to_csv_file
    """
    # Create input data with two images
    images = [
    make_test_image("images/dog.jpg", "A happy dog."),
    make_test_image("images/cat.jpg", "A sleepy cat."),
    make_test_image("images/no_alt.jpg", None),  # Should be excluded
    ]
    output_file = tmp_path / "output.csv"
    write_review_data_to_csv_file(images, output_file)

    assert output_file.exists()

    with output_file.open("r", encoding="utf-8") as f:
        lines = list(csv.reader(f))

    assert lines == [
        ["images/dog.jpg", "A happy dog."],
        ["images/cat.jpg", "A sleepy cat."]
    ]

def test_read_review_data_from_csv_file_valid(tmp_path):
    """
    Unit test for read_review_data_from_csv_file, valid input
    """
    input_file = tmp_path / "input.csv"
    lines = [
    'images/dog.jpg,A happy dog.\n',
    'images/cat.jpg,A sleepy cat.\n',
    'images/fish.jpg,"A fish with ""shiny"" scales."\n',  # contains quotes
    ]
    input_file.write_text("".join(lines), encoding="utf-8")
    result = read_review_data_from_csv_file(input_file)

    expected = [
        ("images/dog.jpg", html.escape("A happy dog.")),
        ("images/cat.jpg", html.escape("A sleepy cat.")),
        ("images/fish.jpg", html.escape('A fish with "shiny" scales.')),
    ]
    assert result == expected

def test_read_review_data_from_csv_file_invalid(tmp_path):
    """
    Unit test for read_review_data_from_csv_file, invalid input
    """
    input_file = tmp_path / "invalid.csv"
    # Line with 3 fields, and line with malformed quote
    lines = [
    'images/dog.jpg,A happy dog.\n',
    'invalid,line,with,too,many,fields\n',
    'images/badquote.jpg,"Unescaped "quote"\n',
    ]
    input_file.write_text("".join(lines), encoding="utf-8")
    try:
        read_review_data_from_csv_file(input_file)
        assert False, "Expected ValueError due to malformed CSV"
    except ValueError as e:
        assert "Expected 2 fields" in str(e) or "unescaped internal quotes" in str(e)

def test_merge_review_data_with_repo_data_sets_correct_alt_text():
    """
    Unit test for merge_review_data_with_repo_data
    """
    # Setup initial image and chapter structure
    image1 = make_test_image("images/dog.jpg", None)
    image2 = make_test_image("images/cat.jpg", None)

    chapter = Chapter(
    filepath=Path("chapter1.html"),
    content="<html></html>",
    chapter_format="html",
    images=[image1, image2]
    )
    updated_data = [("images/dog.jpg", "A happy dog.")]
    merge_review_data_with_repo_data(updated_data, [chapter])

    assert image1.generated_alt_text == "A happy dog."
    assert image2.generated_alt_text is None
