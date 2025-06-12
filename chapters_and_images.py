from pathlib import Path
from pydantic import BaseModel
from typing import List, Literal, Optional


ChapterFormat = Literal["html", "asciidoc"]

class Chapter(BaseModel):
    filepath: Path
    content: str
    chapter_format: ChapterFormat
    images: Optional['Images'] = None
    
class Image(BaseModel):
    chapter_filepath: Path
    original_img_elem_str: str
    image_src: str
    image_filepath: Path
    preceding_para_text: str
    succeeding_para_text: str
    caption_text: str
    original_alt_text: str
    generated_alt_text: Optional[str] = None
    alt_text_replaced: bool = False

Images = List[Image]
Chapters = List[Chapter]




