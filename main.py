import argparse
import os
import sys

from images import Images
from process_repo_files import read_atlas_json, check_asciidoctor_installed, collect_image_data_from_chapter_file


def main():
    parser = argparse.ArgumentParser(description="Script for generating alt text for images in an ORM book repo.")
    parser.add_argument("atlas_path", help="Path to the atlas.json file")
    parser.add_argument("--do-not-replace-existing-alt-text", action="store_true", help="Skip generation of alt text for any images that already have it. By default, all alt text is replaced.")

    args = parser.parse_args()

    if not input("This script edits HTML and Asciidoc files and renames image files in place. It should only be run in a clean Git repo. Do you wish to continue (y/n)? ").strip().lower() in ['y', 'yes']:
        print("Exiting!")
        sys.exit(0)

    project_dir = os.path.dirname(args.atlas_path)
    chapter_files = read_atlas_json(args.atlas_path)

    if len([f for f in chapter_files if ".asciidoc" in f.lower() or ".adoc" in f.lower()]) > 0:
        print("Project contains asciidoc files. Please be patient as asciidoc files are converted to html in memory.")
        print("This will not convert your actual asciidoc files to html.")
        check_asciidoctor_installed()

    files_to_skip = ["cover.html"]

    all_images: Images = []

    for file in chapter_files:
        if all(skip_str not in file for skip_str in files_to_skip):
            chapter_images: Images = collect_image_data_from_chapter_file(file)
            all_images.extend(chapter_images)

    print("test")

    # TODO: find each image pattern in each chapter file
    # TODO: build dict: file, complete line/elem text, image path, existing alt text
    # TODO: process dict: validate image at path, convert to base64, add to dict
    # TODO: generate new alt text from base64
    # TODO: make replacements

if __name__ == '__main__':
    main()