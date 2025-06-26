import argparse
import csv
import html
import json
import os
from pathlib import Path
import regex
import sys
import time
from typing import List, Tuple, Union

from chapters_and_images import Chapter, Chapters, Image, Images
from generate_alt_text import AltTextGenerator
from process_repo_files import (
    read_atlas_json, 
    check_asciidoctor_installed, 
    check_tilt_gem_installed,
    collect_image_data_from_chapter_file,
    detect_format,
    replace_alt_text_in_chapter_content,
    encode_image_to_base64,
    get_mimetype
    )


def write_backup_to_json_file(input_data: list[Chapter], output_filepath: Union[str, Path]):
    """ 
    Serialize Chapter and Image model data and save in JSON file.
    """
    with open(str(output_filepath), 'w') as f:
        json.dump([i.model_dump(mode="json") for i in input_data], f)


def read_backup_from_json_file(input_filepath: Union[str, Path]):
    """ 
    Read JSON file and and validate data as Chapter and Image model data.
    """
    with open(str(input_filepath), 'r') as f:
        chapter_data = json.load(f)
        return [Chapter.model_validate(c) for c in chapter_data]

def write_review_data_to_csv_file(input_data: list[Image], output_filepath: Union[str, Path]):
    """
    Write Image data (src path and AI-generate alt text) to CSV file.
    """
    img_filepath_and_alt_texts = [
        (image.image_src, image.generated_alt_text) for image in input_data 
        if image.generated_alt_text
    ]
    with open(str(output_filepath), 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file, quoting=csv.QUOTE_MINIMAL)
        writer.writerows(img_filepath_and_alt_texts)

def read_review_data_from_csv_file(input_filepath: Union[str, Path]) -> List[Tuple[str, str]]:
    """
    Read a 2-column CSV with: image path, alt-text.

    Returns:
        A list of (img_path, html_escaped_alt_text) tuples.
    """
    img_src_and_alt_text: List[Tuple[str, str]] = []
    errors: List[str] = []

    with open(str(input_filepath), 'r', encoding='utf-8', newline='') as file:
        for lineno, line in enumerate(file, start=1):
            raw_line = line.rstrip('\n')

            try:
                # help ensure internal quotes are escaped (not bulletproof)
                quoted_field_pattern = r'(?<=^|,[ ]*)"(.*?)"(?=$|,[ ]*|\n|\r)' # quoted fields (not including the external quotes)
                quoted_fields = regex.findall(quoted_field_pattern, raw_line, flags=regex.MULTILINE)
                if quoted_fields:
                    for field in quoted_fields:
                        unescaped_quote_pattern = r'(?<!")"(?!")'
                        unescaped_quotes = regex.findall(unescaped_quote_pattern, field)
                        if unescaped_quotes:
                            raise ValueError(f"Line {lineno} with quoted field has unescaped internal quotes:\n{raw_line}")

                # Use csv.reader to split
                row = next(csv.reader([raw_line], delimiter=',', quotechar='"'))
                if len(row) != 2:
                    raise ValueError(f"Line {lineno}: Expected 2 fields, got {len(row)}: {row}")

                img_path = row[0].strip()
                alt_text = html.escape(row[1].strip())  # escape for HTML
                img_src_and_alt_text.append((img_path, alt_text))
            except Exception as e:
                errors.append(f"{str(e)}")
        if errors:
            all_errors = "\n\n".join(errors)
            raise ValueError(f"The following errors were found while reading the CSV:\n\n{all_errors}")

    return img_src_and_alt_text

def merge_review_data_with_repo_data(
        updated_img_src_and_alt_text: list[tuple[str, str]],
        all_chapters: list[Chapter]
    ):
    """
    Merge edited/updated alt text into Chapter data

    Args:
        updated_img_src_and_alt_text: list of tuples (img_src, alt_text)
        all_chapters: list of Chapter data    
    """
    img_src_alt_text_map = {img_src: alt_text for img_src, alt_text in updated_img_src_and_alt_text}
    for chapter in all_chapters:
        for image in chapter.images:
            if img_src_alt_text_map.get(image.image_src, None):
                image.generated_alt_text = img_src_alt_text_map[image.image_src]
            
def main():
    parser = argparse.ArgumentParser(description="Script for generating alt text for images in an ORM book repo.")
    parser.add_argument("atlas_path", help="Path to the atlas.json file")
    parser.add_argument("--do-not-replace-existing-alt-text", action="store_true", help="Skip generation of alt text for any images that already have it. By default, all alt text is replaced.")
    parser.add_argument("--image-file-filter", default=None, help="Provide the path to an optional newline-delimited text file of image filenames. If path is provided, only images matching the filenames in the text file will be processed.")
    parser.add_argument("--load-data-from-json", default=None, help="Provide the path to an optional JSON file of data backed up from a previous session. Useful for continuing your progress after a session is interrupted, without having to send all data back to the AI service. Use of this option supercedes the `--image-file-filter` option, as the image scope from backed-up session will be used. NOTE: Do not use this option if you've made changes in the repo since the backup file was produced, as it may overwrite your changes.")
    parser.add_argument("--update-alt-text-from-csv", default=None, help="Provide the path to an optional CSV file of img src paths and alt text to be used in making replacements. Useful for making adjustments to AI-generated alt text before adding that text to the repo. This option is safe to use if you've made changes in the repo since the CSV review file was produced.")

    args = parser.parse_args()

    if not input("This script edits HTML and Asciidoc files and renames image files in place. It should only be run in a clean Git repo. Do you wish to continue (y/n)? ").strip().lower() in ['y', 'yes']:
        print("Exiting!")
        sys.exit(0)

    atlas_filepath = Path(args.atlas_path)

    project_dir = atlas_filepath.parent
    cwd = os.getcwd()
    backup_filepath = Path(cwd) / f"backup_{int(time.time())}.json"
    review_filepath = Path(cwd) / f"review_{int(time.time())}.csv"
    
    chapter_filepaths = read_atlas_json(atlas_filepath)

    csv_filepath = None
    img_filename_filter_list = None
    path_to_conversion_templates = Path(__file__).parent / "templates"

    # handle file filter
    if args.image_file_filter and not args.load_data_from_json:
        image_file_filter_filepath = Path(args.image_file_filter)
        if (
            not image_file_filter_filepath.exists() or 
            not image_file_filter_filepath.is_file() or
            image_file_filter_filepath.suffix[1:].lower() != 'txt'
            ):
            raise ValueError("Image file filter filepath must point to a valid text (.txt) file.")
        with open(image_file_filter_filepath, 'r') as f:
            img_filename_filter_list = [
                line.strip() for line in f
                if line.strip() and not line.strip().startswith("#")
            ]    
        img_filename_filter_list_str = '\n'.join(img_filename_filter_list)
        if not input(f"Permitted image filenames based on your filter file include the following:\n{img_filename_filter_list_str}\nDo you wish to continue (y/n)? ").strip().lower() in ['y', 'yes']:
            print("Exiting!")
            sys.exit(0)

    # handle CSV option
    if csv_filepath := args.update_alt_text_from_csv:
        csv_filepath = Path(csv_filepath)
        if (
            not csv_filepath.exists() or 
            not csv_filepath.is_file() or
            csv_filepath.suffix[1:].lower() != 'csv'
            ):
            raise ValueError("CSV filepath must point to a valid CSV (.csv) file.")

    # load from json
    if args.load_data_from_json:
        print("Loading repo data from JSON...")
        all_chapters = read_backup_from_json_file(args.load_data_from_json)
    else:
        # perform repo processing
        # asciidoc notice and prep
        # Note: we'll do this with the update_alt_text_from_csv use case as well, 
        # to ensure the replacements are made with fresh content
        if any(f.name.lower().endswith(('.asciidoc', '.adoc')) for f in chapter_filepaths):
            print("Project contains asciidoc files. Please be patient as asciidoc files are converted to html in memory.")
            print("This will not convert your actual asciidoc files to html.")
            check_asciidoctor_installed()
            check_tilt_gem_installed()

        files_to_skip = ["cover.html"]

        all_chapters: Chapters = []

        print("Extracting repo data...")

        # collect chapter data
        for chapter_filepath in chapter_filepaths:
            if all(skip_str not in chapter_filepath.name for skip_str in files_to_skip):
                chapter_format = detect_format(chapter_filepath)
                with open(chapter_filepath, 'r', encoding='utf-8') as f:
                    chapter_text_content = f.read()
                all_chapters.append(
                    Chapter(
                        filepath=chapter_filepath,
                        content=chapter_text_content,
                        chapter_format=chapter_format
                    )
                )

        # collect image data
        for chapter in all_chapters:
            chapter_images: Images = collect_image_data_from_chapter_file(
                chapter_text_content=chapter.content, 
                chapter_filepath=chapter.filepath,
                project_dir=project_dir, 
                conversion_templates_dir=path_to_conversion_templates,
                skip_existing_alt_text=args.do_not_replace_existing_alt_text, 
                img_filename_filter_list=(img_filename_filter_list if img_filename_filter_list else None),
                chapter_format=chapter.chapter_format
                )
            chapter.images = chapter_images

    # create flattened chapter images list
    all_images = []
    for chapter in all_chapters:
        for image in chapter.images:
            all_images.append(image)

    if not csv_filepath:
        # this is executed in the case of load_data_from_json
        # to ensure we finish accumulating alt text, if/as needed
        alt_text_generator = AltTextGenerator()
        
        print(f"Sending data to AI service. Data will be iteratively backed up at {backup_filepath}")

        # generate new alt text
        for i, image in enumerate(all_images):   
            if not image.generated_alt_text:
                print(f"Generating alt text for image {i+1} of {len(all_images)}...")
                
                img_filepath = image.image_filepath
                base64_str = encode_image_to_base64(img_filepath)
                data_uri = f"data:{get_mimetype(img_filepath)};base64,{base64_str}"
                
                new_alt_text = alt_text_generator.generate_alt_text(image, data_uri)
                image.generated_alt_text = new_alt_text
                write_backup_to_json_file(all_chapters, backup_filepath)
            else:
                print(f"Skipping image {i+1} of {len(all_images)} (alt text already generated)...")
    else:
        # merge CSV data into all_chapters
        print("Loading and merging alt text data from CSV...")
        updated_img_src_and_alt_text = read_review_data_from_csv_file(csv_filepath)
        merge_review_data_with_repo_data(updated_img_src_and_alt_text, all_chapters)

    # output review file
    write_review_data_to_csv_file(all_images, review_filepath)

    if input(f"Alt text printed to file {review_filepath}. Would you like to proceed to making replacements? (y/n) ").strip().lower() not in ['y', 'yes']:
        print("Exiting.")
        sys.exit(0)

    # replace alt text in chapters
    for chapter in all_chapters:
        if not chapter.images:
            continue   
        print(f"Replacing alt text in chapter file: {chapter.filepath.name}")
        updated_chapter_content = replace_alt_text_in_chapter_content(
            chapter_content=chapter.content, 
            chapter_format=chapter.chapter_format,
            images=chapter.images, 
            replace_existing_alt=not(args.do_not_replace_existing_alt_text)
            )
        with open(str(chapter.filepath), 'w') as f:
            f.write(updated_chapter_content)
        for image in chapter.images:
            if image.alt_text_replaced:
                print(f"Alt text replaced for image {image.image_src.split('/')[-1]}")
    
    # final backup
    write_backup_to_json_file(all_chapters, backup_filepath)

    print("Scripted completed.")
    

if __name__ == '__main__':
    main()
