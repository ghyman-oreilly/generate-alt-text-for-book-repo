import base64
from bs4 import BeautifulSoup, NavigableString, Tag
import json
import logging
import mimetypes
from pathlib import Path
import re
import subprocess
from typing import Optional
from urllib.parse import urlparse

from chapters_and_images import Image, Images, ChapterFormat


logger = logging.getLogger(__name__)

class AsciidoctorMissingError(RuntimeError):
    """Raised when the Asciidoctor CLI is not found."""
    pass


class AsciidoctorConversionError(RuntimeError):
    """Raised when Asciidoctor fails to convert a file."""
    pass


def read_atlas_json(atlas_path: Path) -> Optional[list[Path]]:
    """
    Get list of chapter files from atlas.json.

    Args:
        atlas_path (Path): Path to the atlas.json file.

    Returns:
        List of absolute chapter file Paths, or None if no files found.
    """
    atlas_path = Path(atlas_path)  # Ensure atlas_path is a Path object
    project_dir = atlas_path.parent

    try:
        atlas_data = json.loads(atlas_path.read_text(encoding='utf-8'))
    except Exception as e:
        logger.error(f"Failed to read or parse atlas.json: {e}")
        return None

    chapter_files = [project_dir / Path(p) for p in atlas_data.get("files", [])]

    if not chapter_files:
        logger.warning("No chapter files found in the atlas.json file.")
        return None

    return chapter_files


def check_asciidoctor_installed(raise_on_error=True) -> bool:
    """Check if the asciidoctor CLI is available on the system."""
    try:
        result = subprocess.run(
            ["asciidoctor", "-v"],
            capture_output=True,
            text=True,
            check=True
        )
        logger.debug(f"Asciidoctor version: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        message = (
            "The 'asciidoctor' CLI was not found. Please install it and ensure it's in your PATH."
        )
        logger.error(message)
        if raise_on_error:
            raise AsciidoctorMissingError(message)
        return False
    except subprocess.CalledProcessError as e:
        logger.error("Asciidoctor CLI returned an error.")
        logger.debug(f"Subprocess stderr: {e.stderr}")
        if raise_on_error:
            raise AsciidoctorMissingError("Asciidoctor CLI returned an error.") from e
        return False


def convert_asciidoc_string_to_html(asciidoc_content: str) -> str:
    """
    Convert an AsciiDoc string to HTML using the Asciidoctor CLI.

    Args:
        asciidoc_content (str): AsciiDoc content as a string.

    Returns:
        str: HTML resulting from the AsciiDoc conversion.

    Raises:
        AsciidoctorConversionError: If the conversion fails.
    """
    try:
        result = subprocess.run(
            [
                "asciidoctor",
                "-a", "stylesheet!",
                "-a", "caption",
                "-",             # input from stdin
                "-o", "-"        # output to stdout
            ],
            input=asciidoc_content,
            capture_output=True,
            text=True,
            check=True
        )
        logger.debug("Converted AsciiDoc string to HTML successfully.")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error("Asciidoctor conversion from string failed.")
        logger.debug(f"Command: {e.cmd}")
        logger.debug(f"Exit code: {e.returncode}")
        logger.debug(f"Stdout: {e.stdout}")
        logger.error(f"Stderr: {e.stderr}")
        raise AsciidoctorConversionError("Failed to convert AsciiDoc string to HTML.") from e
    except FileNotFoundError:
        logger.error("The 'asciidoctor' CLI was not found. Is it installed?")
        raise AsciidoctorConversionError("Asciidoctor CLI not found.")


def collect_image_data_from_chapter_file(
        chapter_text_content: str,
        chapter_filepath: Path,
        project_dir: Path, 
        skip_existing_alt_text: bool = False,
        img_filename_filter_list: Optional[list] = None,
        chapter_format: ChapterFormat = 'html'
    ) -> Images:
    """
    Given a filepath of an HTML or Asciidoc file, 
    collect data on image references, using Image structure.
    """   
    if chapter_format.lower() == 'html':
        img_pattern = r'<img\b[^>]*?>'
        soup = BeautifulSoup(chapter_text_content, 'html.parser')
    elif chapter_format.lower() == 'asciidoc':
        img_pattern = r'^(image:{1,2}(.*?)\[.*?\])'
        html_text = convert_asciidoc_string_to_html(chapter_text_content)
        soup = BeautifulSoup(html_text, 'html.parser')
    else:
        raise ValueError(f"Unsupported file format: {chapter_format}.")

    supported_filetypes = ['png', 'jpeg', 'jpg', 'webp', 'gif'] # types supported by OpenAI
    
    images: Images = []
    
    img_elements = soup.find_all('img')

    img_tag_matches = re.findall(img_pattern, chapter_text_content, flags=re.I | re.DOTALL | re.MULTILINE)

    original_img_tags_by_src = {}

    for img_tag_match in img_tag_matches:
        if chapter_format.lower() == 'html':
            temp_soup = BeautifulSoup(img_tag_match, 'html.parser')
            tag = temp_soup.find('img')
            if tag and tag.has_attr('src'):
                src = tag['src']
                img_tag_string = img_tag_match
        elif len(img_tag_match) > 1:
            # asciidoc case
            # first tuple member is full img string, second is src
            src = img_tag_match[1]
            img_tag_string = img_tag_match[0]
        if src:
            original_img_tags_by_src.setdefault(src, []).append(img_tag_string)  # Handle duplicates

    images = []

    for img_elem in img_elements:
        caption_tag = None
        preceding_para = None
        succeeding_para = None
        
        img_src = img_elem.get('src')
        
        if not img_src:
            continue
        elif 'callouts/' in img_src:
            continue

        img_filepath = resolve_image_path(project_dir, img_src)
        
        if not img_filepath.exists:
            logger.warning(f"File doesn't exist. Skipping image: {img_src}")
            continue

        if (
            img_filename_filter_list is not None and
            img_filepath.name not in img_filename_filter_list
            ):
            # if a filter list is present, skip images not in list
            continue

        if not img_filepath.suffix[1:].lower() in supported_filetypes:
            logger.warning(f"Image filetype not supported. Skipping image: {img_src}")
            continue

        img_alt_text = img_elem.get('alt', '')

        if skip_existing_alt_text and img_alt_text.strip() != '':
            logger.info(f"Image has existing alt text. Skipping image: {img_src}")
            continue

        # Get the first raw string that matched this src
        original_img_tag = (original_img_tags_by_src.get(img_src) or [None])[0]

        if skip_existing_alt_text and img_elem.get('alt', '').strip():
            continue

        # Look for paragraph and caption context
        if img_elem.parent.name == 'figure':
            preceding_para = img_elem.parent.find_previous('p')
            succeeding_para = img_elem.parent.find_next('p')
            caption_tag = (
                img_elem.parent.find('figcaption')
                or img_elem.parent.find('caption')
            )
        else:
            preceding_para = img_elem.find_previous('p')
            succeeding_para = img_elem.find_next('p')
            
        # AsciiDoc case: <div class="content"><img ...></div> <div class="title">...</div>
        if img_elem.parent.name == 'div' and 'content' in img_elem.parent.get('class', []):
            next_elem = get_next_non_whitespace_sibling(img_elem.parent)
            if next_elem and next_elem.name == 'div' and 'title' in next_elem.get('class', []):
                caption_tag = next_elem
            else:
                caption_tag = None

        # Convert elements to text
        preceding_text = (preceding_para.get_text() if preceding_para else '').strip()
        succeeding_text = (succeeding_para.get_text() if succeeding_para else '').strip()
        caption_text = (caption_tag.get_text() if caption_tag else '').strip()

        img_filepath = resolve_image_path(project_dir, img_src)
        if not img_filepath.exists():
            continue

        images.append(Image(
            chapter_filepath=chapter_filepath,
            original_img_elem_str=original_img_tag,
            image_src=img_src,
            image_filepath=img_filepath,
            preceding_para_text=preceding_text,
            succeeding_para_text=succeeding_text,
            caption_text=caption_text,
            original_alt_text=img_alt_text
        ))

    return images


def get_next_non_whitespace_sibling(tag):
    next_sibling = tag.next_sibling
    while next_sibling:
        if isinstance(next_sibling, NavigableString):
            if next_sibling.strip():  # if not just whitespace
                # It's non-whitespace text, not an element — stop
                break
        elif isinstance(next_sibling, Tag):
            return next_sibling
        next_sibling = next_sibling.next_sibling
    return None


def is_local_relative_path(src: str) -> bool:
    parsed = urlparse(src)
    return (
        not parsed.scheme  # excludes http, https, data, file, etc.
        and not parsed.netloc  # excludes example.com
        and not src.startswith('/')  # excludes root-relative web paths
    )


def resolve_image_path(project_dir: Path, src: str) -> Optional[Path]:
    if is_local_relative_path(src):
        candidate_path = project_dir / src
        if candidate_path.exists():
            return candidate_path.resolve()
    return None


def encode_image_to_base64(filepath: Path) -> str:
    """
    Read an image file and return a base64-encoded string.
    
    Args:
        filepath (Path): Path to the image file
    
    Returns:
        str: Base64 string (without data URI prefix)
    """
    with open(filepath, "rb") as image_file:
        encoded_bytes = base64.b64encode(image_file.read())
        return encoded_bytes.decode("utf-8")


def get_mimetype(filepath: Path) -> str:
    """
    Return mimetype string for given filepath (Posix Path).
    """
    mime_type, _ = mimetypes.guess_type(filepath)
    if mime_type is None:
        raise ValueError(f"Could not determine MIME type for file: {filepath}")
   
    return mime_type


def detect_format(path: Path) -> ChapterFormat:
    """
    Return a ChapterFormat string, given Path
    to an html or asciidoc file
    """
    if path.suffix.lower() in (".html", ".htm"):
        return "html"
    else:
        return "asciidoc"


def replace_alt_text_in_chapter_content(
    chapter_content: str,
    images: Images,
    replace_existing_alt: bool = True
) -> str:
    """
    Generate updated chapter content string by
    replacing existing alt text with newly generated
    alt text
    """
    updated_chapter_content = chapter_content

    for image in images:
        string_to_replace = image.original_img_elem_str
        if (replace_existing_alt or not image.original_alt_text):
            replacement_string = image.original_img_elem_str.replace(image.original_alt_text, image.generated_alt_text)
            updated_chapter_content = updated_chapter_content.replace(string_to_replace, replacement_string)
            image.alt_text_replaced = True

    return updated_chapter_content
    