import argparse
from collections import defaultdict
import logging
from pathlib import Path
import sys

from chapters_and_images import Images, Chapter, Chapters
from generate_alt_text import AllTextGenerator
from process_repo_files import (
    read_atlas_json, 
    check_asciidoctor_installed, 
    collect_image_data_from_chapter_file,
    detect_format,
    replace_alt_text_in_chapter_content
    )


def main():
    parser = argparse.ArgumentParser(description="Script for generating alt text for images in an ORM book repo.")
    parser.add_argument("atlas_path", help="Path to the atlas.json file")
    parser.add_argument("--do-not-replace-existing-alt-text", action="store_true", help="Skip generation of alt text for any images that already have it. By default, all alt text is replaced.")
    parser.add_argument("--image-file-filter", default=None, help="Provide the path to an optional newline-delimited text file of image filenames. If path is provided, only images matching the filenames in the text file will be processed.")

    args = parser.parse_args()

    if not input("This script edits HTML and Asciidoc files and renames image files in place. It should only be run in a clean Git repo. Do you wish to continue (y/n)? ").strip().lower() in ['y', 'yes']:
        print("Exiting!")
        sys.exit(0)

    atlas_filepath = Path(args.atlas_path)

    project_dir = atlas_filepath.parent
    
    chapter_filepaths = read_atlas_json(atlas_filepath)

    img_filename_filter_list = None

    # handle file filter
    if args.image_file_filter:
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
        if not input(f"Permitted image filenames based on your filter file include the following:\n{'\n'.join(img_filename_filter_list)}\nDo you wish to continue (y/n)? ").strip().lower() in ['y', 'yes']:
            print("Exiting!")
            sys.exit(0)

    # asciidoc notice and prep
    if any(f.name.lower().endswith(('.asciidoc', '.adoc')) for f in chapter_filepaths):
        print("Project contains asciidoc files. Please be patient as asciidoc files are converted to html in memory.")
        print("This will not convert your actual asciidoc files to html.")
        check_asciidoctor_installed()

    files_to_skip = ["cover.html"]

    all_chapters: Chapters = []

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
            chapter["content"], 
            chapter["filepath"],
            project_dir, 
            args.do_not_replace_existing_alt_text, 
            img_filename_filter_list=(img_filename_filter_list if img_filename_filter_list else None),
            chapter_format=chapter["chapter_format"]
            )
        chapter["images"] = chapter_images

    alt_text_generator = AllTextGenerator()
    
    # create flattened chapter images list,
    # in order to provide user with a counter
    all_images = []
    for chapter in all_chapters:
        for image in chapter["images"]:
            all_images.append(image)

    # generate new alt text
    for i, image in enumerate(all_images):   
        print(f"Generating alt text for image {i+1} of {len(all_images)}...")
        new_alt_text = alt_text_generator.generate_alt_text(image)
        image["generated_alt_text"] = new_alt_text

    # replace alt text in chapters
    for chapter in all_chapters:
        if not chapter["images"]:
            continue   
        print(f"Replacing alt text in chapter file: {chapter["filepath"].name}")
        updated_chapter_content = replace_alt_text_in_chapter_content(
            chapter["content"], 
            chapter["images"], 
            not(args.do_not_replace_existing_alt_text)
            )
        with open(chapter["filepath"], 'w') as f:
            f.write(updated_chapter_content)
        for image in chapter["images"]:
            if image["alt_text_replaced"]:
                print(f"Alt text replaced for image {image["image_src"].split('/')[-1]}")

    print("Scripted completed.")
    

if __name__ == '__main__':
    main()