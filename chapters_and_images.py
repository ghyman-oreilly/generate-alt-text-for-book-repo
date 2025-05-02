from pathlib import Path
from typing import TypedDict, List, Literal


ChapterFormat = Literal["html", "asciidoc"]

class Chapter(TypedDict, total=False):
    filepath: Path
    content: str
    chapter_format: ChapterFormat
    images: 'Images'
    
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
    alt_text_replaced: bool = False

Images = List[Image]
Chapters = List[Chapter]




