import os
import tempfile
import shutil
import pytest
from pathlib import Path
from process_repo_files import *


def test_read_atlas_json(tmp_path):
    atlas = tmp_path / "atlas.json"
    chapter = tmp_path / "chapter1.html"
    chapter.write_text("<html></html>")
    atlas.write_text('{"files": ["chapter1.html"]}')
    result = read_atlas_json(atlas)
    assert isinstance(result, list)
    assert chapter in result

def test_check_tilt_gem_installed(monkeypatch):
    # Simulate tilt gem missing
    def fake_run(*a, **k):
        class Result:
            stdout = "false"
        return Result()
    monkeypatch.setattr("subprocess.run", fake_run)
    with pytest.raises(TiltGemMissingError):
        check_tilt_gem_installed()

def test_check_asciidoctor_installed(monkeypatch):
    # Simulate asciidoctor present
    monkeypatch.setattr("subprocess.run", lambda *a, **k: type("R", (), {"stdout": "asciidoctor 2.0.0"})())
    assert check_asciidoctor_installed() is True
    # Simulate asciidoctor missing
    def raise_fnf(*a, **k): raise FileNotFoundError
    monkeypatch.setattr("subprocess.run", raise_fnf)
    with pytest.raises(AsciidoctorMissingError):
        check_asciidoctor_installed()

def test_convert_asciidoc_string_to_html(monkeypatch):
    # Simulate successful conversion
    monkeypatch.setattr("subprocess.run", lambda *a, **k: type("R", (), {"stdout": "<html>converted</html>"})())
    html = convert_asciidoc_string_to_html("= Title", "./")
    assert "converted" in html
    # Simulate failure
    class FakeError(Exception): pass
    def raise_cpe(*a, **k): raise subprocess.CalledProcessError(1, 'cmd', output='', stderr='fail')
    monkeypatch.setattr("subprocess.run", raise_cpe)
    with pytest.raises(AsciidoctorConversionError):
        convert_asciidoc_string_to_html("= Title", "./")

def test_is_local_relative_path():
    assert is_local_relative_path("images/foo.png")
    assert not is_local_relative_path("http://example.com/foo.png")
    assert not is_local_relative_path("/foo.png")
    assert not is_local_relative_path("data:image/png;base64,abc")

def test_resolve_image_path(tmp_path):
    img = tmp_path / "foo.png"
    img.write_bytes(b"x")
    assert resolve_image_path(tmp_path, "foo.png") == img.resolve()
    assert resolve_image_path(tmp_path, "notfound.png") is None

def test_encode_image_to_base64(tmp_path):
    img = tmp_path / "foo.png"
    img.write_bytes(b"abc")
    b64 = encode_image_to_base64(img)
    import base64 as b64mod
    assert b64 == b64mod.b64encode(b"abc").decode()

def test_get_mimetype(tmp_path):
    img = tmp_path / "foo.png"
    img.write_bytes(b"abc")
    assert get_mimetype(img) == "image/png"
    unknown = tmp_path / "foo.unknown"
    unknown.write_bytes(b"abc")
    with pytest.raises(ValueError):
        get_mimetype(unknown)

def test_detect_format(tmp_path):
    html = tmp_path / "foo.html"
    adoc = tmp_path / "foo.adoc"
    html.write_text("")
    adoc.write_text("")
    assert detect_format(html) == "html"
    assert detect_format(adoc) == "asciidoc"

def test_get_next_non_whitespace_sibling():
    from bs4 import BeautifulSoup
    html = '<div class="content"></div>\n<div class="title">caption</div>'
    soup = BeautifulSoup(html, "html.parser")
    content_div = soup.find("div", class_="content")
    sibling = get_next_non_whitespace_sibling(content_div)
    assert sibling and sibling["class"] == ["title"]

def test_collect_image_data_from_chapter_file_html(tmp_path):
    from process_repo_files import collect_image_data_from_chapter_file
    html = '<html><body><img src="foo.jpg" alt=""><p>caption</p></body></html>'
    img = tmp_path / "foo.jpg"
    img.write_bytes(b"x")
    images = collect_image_data_from_chapter_file(
        chapter_text_content=html,
        chapter_filepath=tmp_path / "chapter1.html",
        project_dir=tmp_path,
        conversion_templates_dir=".",
        skip_existing_alt_text=False,
        img_filename_filter_list=None,
        chapter_format="html"
    )
    assert len(images) == 1
    assert images[0].image_src == "foo.jpg"

def test_replace_alt_text_in_chapter_content():
    from chapters_and_images import Image
    images = [Image(
        chapter_filepath=Path("chapter1.html"),
        original_img_elem_str='<img src="images/dog.jpg" alt="">',
        image_src="images/dog.jpg",
        image_filepath=Path("images/dog.jpg"),
        preceding_para_text="A dog is running.",
        succeeding_para_text="The dog stops.",
        caption_text="A brown dog.",
        original_alt_text="",
        generated_alt_text="A dog running",
        alt_text_replaced=False
    )]
    html = '<html><body><img src="images/dog.jpg" alt=""></body></html>'
    out = replace_alt_text_in_chapter_content(html, "html", images)
    assert 'alt="A dog running"' in out

