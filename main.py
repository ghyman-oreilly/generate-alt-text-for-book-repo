import argparse
from collections import defaultdict
from pathlib import Path
import sys

from images import Images, Chapter, Chapters, ChapterFormat
from generate_alt_text import AllTextGenerator
from process_repo_files import (
    read_atlas_json, 
    check_asciidoctor_installed, 
    collect_image_data_from_chapter_file
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
    
    chapter_files = read_atlas_json(atlas_filepath)

    img_filename_filter_list = None

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

    if any(f.name.lower().endswith(('.asciidoc', '.adoc')) for f in chapter_files):
        print("Project contains asciidoc files. Please be patient as asciidoc files are converted to html in memory.")
        print("This will not convert your actual asciidoc files to html.")
        check_asciidoctor_installed()

    files_to_skip = ["cover.html"]

    all_images: Images = []

    for file in chapter_files:
        if all(skip_str not in file.name for skip_str in files_to_skip):
            chapter_images: Images = collect_image_data_from_chapter_file(
                file, 
                project_dir, 
                args.do_not_replace_existing_alt_text, 
                img_filename_filter_list=(img_filename_filter_list if img_filename_filter_list else None)
                )
            all_images.extend(chapter_images)

    alt_text_generator = AllTextGenerator()

    for i, image in enumerate(all_images):   
        print(f"Generating alt text for image {i+1} of {len(all_images)}...")
        new_alt_text = alt_text_generator.generate_alt_text(image)
        image["generated_alt_text"] = new_alt_text

    grouped_images: dict[Path, Images] = defaultdict(list)

    # group images by chapter
    for img in all_images:
        fp = img.get("chapter_filepath")
        if fp:
            grouped_images[fp].append(img)

    def detect_format(path: Path) -> ChapterFormat:
        if path.suffix.lower() in (".html", ".htm"):
            return "html"
        else:
            return "asciidoc"

    chapters: Chapters = [
        {
            "chapter_filepath": path,
            "images": images,
            "chapter_format": detect_format(path)
        }
        for path, images in grouped_images.items()
    ]

    for chapter in chapters:
        chapter_filepath = chapter.get("chapter_filepath", None)
        if chapter_filepath is not None:
            with open(chapter_filepath, 'r') as f:
                chapter_content = f.read()
            for image in chapter:
                # TODO: make replacements - probably this should all go in process_repo_files
                pass
        

    print("test")

    

if __name__ == '__main__':
    main()