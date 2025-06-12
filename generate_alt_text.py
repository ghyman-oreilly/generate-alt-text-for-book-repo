from dotenv import load_dotenv
import html
import openai
import os

from chapters_and_images import Image

# Make sure API key is set
load_dotenv()

# initialize client
api_key = os.getenv("OPENAI_API_KEY")
client = openai.OpenAI(api_key=api_key)


class AllTextGenerator:
    def __init__(self, model="gpt-4o"):
        self.model = model

    def create_prompt(self, image: Image, detail="high"):
        """
        Build the full user prompt for a vision service call.
        """
        preceding_para_text = image.preceding_para_text
        succeeding_para_text = image.succeeding_para_text
        caption_text = image.caption_text
        img_data_uri = image.img_data_uri

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

    def generate_alt_text(self, image: Image, detail="high"):
        """
        Generates alt text for a base64-encoded image
        """
        prompt = self.create_prompt(image, detail)

        response = client.responses.create(
            model=self.model,
            input=prompt
        )
        
        return html.escape(response.output_text, quote=True)
