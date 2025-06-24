from dotenv import load_dotenv
import html
import openai
import os

from chapters_and_images import Image


class OpenAIKeyMissingError(RuntimeError):
    """Raised when the OpenAI API key is not found in the environment."""
    pass

def check_api_key(dotenv_path=None):
    """Check for OpenAI API key and raise error if missing."""
    if dotenv_path is None:
        # Get the directory containing this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        dotenv_path = os.path.join(script_dir, '.env')
    
    load_dotenv(dotenv_path=dotenv_path)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIKeyMissingError(
            "OPENAI_API_KEY not found in environment. Please set it in your .env file or environment variables."
        )
    return api_key

# Run at import time so we fail fast
api_key = check_api_key()
client = openai.OpenAI(api_key=api_key)


class AllTextGenerator:
    def __init__(self, model="gpt-4o"):
        self.model = model

    def create_prompt(self, image: Image, data_uri: str, detail="high"):
        """
        Build the full user prompt for a vision service call.
        """
        preceding_para_text = image.preceding_para_text
        succeeding_para_text = image.succeeding_para_text
        caption_text = image.caption_text
        img_data_uri = data_uri

        if img_data_uri is None:
            return None

        input_text = "What's in this image?"
        input_text += "\nPlease begin your response with 'This is an image of' or 'This image illustrates'"
        input_text += "\nWhen responding, consider the image's context, including the Preceding Paragraph, Succeeding Paragraph, and Caption, if applicable." if preceding_para_text or succeeding_para_text or caption_text else ''
        input_text += f"\nPreceding Paragraph: {preceding_para_text}" if preceding_para_text else ''
        input_text += f"\nSucceeding Paragraph: {succeeding_para_text}" if succeeding_para_text else ''
        input_text += f"\nCaption: {caption_text}" if caption_text else ''

        return [
            {
                "role": "user",
                "content": [
                    { "type": "input_text", "text": input_text },
                    {
                        "type": "input_image",
                        "image_url": img_data_uri,
                        "detail": detail
                    },
                ],
            }
        ]

    def generate_alt_text(self, image: Image, data_uri: str,  detail="high"):
        """
        Generates alt text for a base64-encoded image
        """
        prompt = self.create_prompt(image, data_uri, detail)

        response = client.responses.create(
            model=self.model,
            input=prompt
        )
        
        return html.escape(response.output_text, quote=True)
