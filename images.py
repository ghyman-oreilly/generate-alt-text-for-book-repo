from pathlib import Path
from typing import TypedDict, List, Literal


ChapterFormat = Literal["html", "asciidoc"]

class Image(TypedDict, total=False):
    chapter_filepath: Path
    original_img_elem_str: str
    image_src: str
    image_filepath: Path
    preceding_para_text: str
    succeeding_para_text: str
    caption_text: str
    original_alt_text: str
    generated_alt_text: str
    base64_str: str
    img_data_uri: str

class Chapter(TypedDict):
    chapter_filepath: Path
    images: List[Image]
    chapter_format: ChapterFormat

Images = List[Image]
Chapters = List[Chapter]
