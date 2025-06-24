from pathlib import Path
import pydantic
import pytest

from chapters_and_images import Chapter, Image, ChapterFormat


def test_chapter_valid():
    """Test Chapter validation"""
    chapter = Chapter(
        filepath=Path("chapter1.html"),
        content="<html>test</html>",
        chapter_format="html",
        images=[],
    )
    assert chapter.filepath.name == "chapter1.html"
    assert chapter.chapter_format == "html"


def test_chapter_invalid_format():
    """Test Chapter validation"""
    with pytest.raises(ValueError):
        Chapter(
            filepath=Path("chapter1.html"),
            content="<html>test</html>",
            chapter_format="pdf",  # invalid
            images=[],
        )


def test_image_valid():
    """Test Image validation"""
    image = Image(
        chapter_filepath=Path("chapter1.html"),
        original_img_elem_str='<img src="images/dog.jpg" alt="">',
        image_src="images/dog.jpg",
        image_filepath=Path("images/dog.jpg"),
        preceding_para_text="A dog is running.",
        succeeding_para_text="The dog stops.",
        caption_text="A brown dog.",
        original_alt_text="",
        generated_alt_text=None,
        alt_text_replaced=False,
    )
    assert image.image_src.endswith("dog.jpg")


def test_image_missing_required():
    """Test Image validation"""
    with pytest.raises(pydantic.ValidationError):
        Image(
            chapter_filepath=Path("chapter1.html"),
            # missing required fields
        )