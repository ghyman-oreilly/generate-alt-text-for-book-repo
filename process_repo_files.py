from bs4 import BeautifulSoup
import json
import logging
import os
import subprocess
import sys

from images import Image, Images


logger = logging.getLogger(__name__)


class AsciidoctorMissingError(RuntimeError):
    """Raised when the Asciidoctor CLI is not found."""
    pass


class AsciidoctorConversionError(RuntimeError):
    """Raised when Asciidoctor fails to convert a file."""
    pass


def read_atlas_json(atlas_path):
    """
    Get list of chapter files
    from atlas.json
    """
    # Load the atlas.json file
    with open(atlas_path, 'r', encoding='utf-8') as f:
        atlas_data = json.load(f)
    
    project_dir = os.path.dirname(os.path.abspath(atlas_path))
    chapter_files = [os.path.join(project_dir, path) for path in atlas_data.get("files", [])]
    
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


def collect_image_data_from_chapter_file(filepath: str) -> Images:
    """
    Given a filepath of an HTML or Asciidoc file, 
    collect data on image references, using Image structure.
    """
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
        img_path = img_elem.get('src', None)
        img_alt_text = img_elem.get('alt', '')

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

        if img_path is not None:
            images.append(
                Image(
                    filepath=filepath,
                    image_path=img_path,
                    preceding_para_text=preceding_para_text,
                    succeeding_para_text=succeeding_para_text,
                    caption_text=caption_text,
                    original_alt_text=img_alt_text
                )
            )

    return images


