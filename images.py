from pathlib import Path
from typing import TypedDict, List


class Image(TypedDict, total=False):
	filepath: Path
	image_src: str
	image_filepath: Path
	preceding_para_text: str
	succeeding_para_text: str
	caption_text: str
	original_alt_text: str
	generated_alt_text: str
	base64_str: str

Images = List[Image]
