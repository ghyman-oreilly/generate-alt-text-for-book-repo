# Generate Alt Text

A script for generating alt text for images in an ORM book repository.

## Requirements

- Python 3.7+
- OpenAI API key
- [Asciidoctor](https://asciidoctor.org)

### Setup

1. Clone the repository or download the source files:

	```bash
	git clone git@github.com:ghyman-oreilly/generate-alt-text-for-book-repo.git
	
	cd generate-alt-text-for-book-repo
	```

2. Install required dependencies:

	```bash
	pip install -r requirements.txt
	```

3. Create an `.env` file in the project directory to store your OpenAI credentials:

	```bash
	echo "OPENAI_API_KEY=sk-your-api-key-here" >> .env
	```

4. Install [Asciidoctor](https://asciidoctor.org) on your system. On mac, you can use brew to install Asciidoctor:

	```bash
	brew doctor
	```

## Usage

To use the script, run the following command, providing the path to the `atlas.json` file in your book repo:

```bash
python main.py path/to/atlas.json
```

Options:
- `--do-not-replace-existing-alt-text`: (Optional) Pass this flag to skip replacement of any existing alt text
- `--image-file-filter`: (Optional) Pass this flag with the path to a `.txt` file containing a list of filenames delimited by newlines. Only images whose filename matches the filenames in the list will have alt text generated and added.

Note: Because the script rewrites files in place, it's recommended that it be run only on clean Git repos, so the changes can easily be reviewed and reverted, as needed.