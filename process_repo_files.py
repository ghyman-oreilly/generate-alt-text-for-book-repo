import base64
from bs4 import BeautifulSoup
import json
import logging
import mimetypes
from pathlib import Path
import os
import subprocess
from typing import Optional
from urllib.parse import urlparse

from images import Image, Images


logger = logging.getLogger(__name__)


class AsciidoctorMissingError(RuntimeError):
    """Raised when the Asciidoctor CLI is not found."""
    pass


class AsciidoctorConversionError(RuntimeError):
    """Raised when Asciidoctor fails to convert a file."""
    pass


def read_atlas_json(atlas_path: Path) -> list[Path] | None:
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


def convert_asciidoc_to_htmlbook(file_path: str) -> str:
    """
    Convert an AsciiDoc file to HTML using the Asciidoctor CLI.

    Stylesheets and captioning are turned off with `-a stylesheet!` and `-a caption`.
    Output is captured and returned as a string.

    Args:
        file_path (str): Path to the AsciiDoc file to convert.

    Returns:
        str: HTML content generated from the AsciiDoc input.

    Raises:
        AsciidoctorConversionError: If the conversion process fails.
    """
    try:
        result = subprocess.run(
            [
                'asciidoctor',
                '-a', 'stylesheet!',
                '-a', 'caption',
                '-o', '-',  # output to stdout
                file_path
            ],
            capture_output=True,
            text=True,
            check=True  # ← raises CalledProcessError on failure
        )
        logger.debug(f"Converted {file_path} to HTML successfully.")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error("Asciidoctor conversion failed.")
        logger.debug(f"Command: {e.cmd}")
        logger.debug(f"Exit code: {e.returncode}")
        logger.debug(f"Stdout: {e.stdout}")
        logger.error(f"Stderr: {e.stderr}")
        raise AsciidoctorConversionError(
            f"Failed to convert AsciiDoc file '{file_path}' to HTML."
        ) from e
    except FileNotFoundError:
        logger.error("The 'asciidoctor' CLI was not found. Is it installed?")
        raise AsciidoctorConversionError("Asciidoctor CLI not found.")


def collect_image_data_from_chapter_file(
        filepath: Path, 
        project_dir: Path, 
        skip_existing_alt_text: bool = False,
        img_filename_filter_list: Optional[list] = None
    ) -> Images:
    """
    Given a filepath of an HTML or Asciidoc file, 
    collect data on image references, using Image structure.
    """
    supported_filetypes = ['png', 'jpeg', 'jpg', 'webp', 'gif'] # types supported by OpenAI
    
    images: Images = []
    
    if os.path.splitext(filepath)[1].lower() == ".html":
        with open(filepath, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
    elif os.path.splitext(filepath)[1].lower() in [".asciidoc", ".adoc"]:
        html = convert_asciidoc_to_htmlbook(filepath)
        soup = BeautifulSoup(html, 'html.parser')
    else:
        # filetype not supported
        logger.warning(f"File format {os.path.splitext(filepath)[1].lower()} not supported. Skipping...")

    img_elems = soup.find_all('img')

    for img_elem in img_elems:
        img_src = img_elem.get('src', None)

        if img_src is None:
            continue
        elif 'callouts/' in img_src:
            logger.info(f"Skipping callout image: {img_src}")
            continue

        img_filepath = resolve_image_path(project_dir, img_src)
        
        if not img_filepath.exists:
            logger.warning(f"File doesn't exist. Skipping image: {img_src}")
            continue
        
        if (
            img_filename_filter_list is not None and
            img_filepath.name not in img_filename_filter_list
            ):
            logger.info(f"Image not included in filter list. Skipping image: {img_src}")
            continue

        if not img_filepath.suffix[1:].lower() in supported_filetypes:
            logger.warning(f"Image filetype not supported. Skipping image: {img_src}")
            continue

        img_alt_text = img_elem.get('alt', '')

        if skip_existing_alt_text and img_alt_text.strip() != '':
            logger.info(f"Image has existing alt text. Skipping image: {img_src}")
            continue

        if img_elem.parent.name == 'figure':
            preceding_para = img_elem.parent.find_previous('p')
            succeeding_para = img_elem.parent.find_next('p')
            caption_tag = img_elem.parent.find('figcaption') or img_elem.parent.find('caption')
            
        else:
            preceding_para = img_elem.find_previous('p')
            succeeding_para = img_elem.find_next('p')
            caption_tag = None

        preceding_para_text = preceding_para.get_text() if preceding_para else ''
        succeeding_para_text = succeeding_para.get_text() if succeeding_para else ''
        caption_text = caption_tag.get_text() if caption_tag else ''

        base64_str = encode_image_to_base64(img_filepath)
        img_data_uri = f"data:{get_mimetype(img_filepath)};base64,{base64_str}"

        images.append(
            Image(
                filepath=filepath,
                image_src=img_src,
                image_filepath=img_filepath,
                preceding_para_text=preceding_para_text,
                succeeding_para_text=succeeding_para_text,
                caption_text=caption_text,
                original_alt_text=img_alt_text,
                base64_str=base64_str,
                img_data_uri=img_data_uri
            )
        )

    return images


def is_local_relative_path(src: str) -> bool:
    parsed = urlparse(src)
    return (
        not parsed.scheme  # excludes http, https, data, file, etc.
        and not parsed.netloc  # excludes example.com
        and not src.startswith('/')  # excludes root-relative web paths
    )


def resolve_image_path(project_dir: Path, src: str) -> Path | None:
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