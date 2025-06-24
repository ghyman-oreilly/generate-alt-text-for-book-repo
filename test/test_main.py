import json
from pathlib import Path
import os

from main import main


def test_write_backup_to_json_file():
	pass

def test_read_backup_from_json_file():
	pass

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
            ["script_name", str(atlas_path), "--image-file-filter", str(filter_path)]
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

    # ✅ Check: Final HTML file includes generated alt text
    updated_content = chapter_path.read_text()
    assert 'alt="A realistic alt text"' in updated_content

    # ✅ Optional: Check backup file was created
    backup_files = list(tmp_path.glob("backup_*.json"))
    assert len(backup_files) >= 1
    