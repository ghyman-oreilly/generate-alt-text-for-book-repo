from typing import TypedDict, List


class Image(TypedDict, total=False):
	filepath: str
	image_path: str
	preceding_para_text: str
	succeeding_para_text: str
	caption_text: str
	original_alt_text: str
	generated_alt_text: str
	base64_str: str

Images = List[Image]
