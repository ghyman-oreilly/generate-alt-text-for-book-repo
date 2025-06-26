import pytest
import os
import subprocess
import sys


class DummyImage:
    def __init__(self):
        self.preceding_para_text = "A dog is running."
        self.succeeding_para_text = "The dog stops."
        self.caption_text = "A brown dog."
        self.image_src = "images/dog.jpg"
        self.original_img_elem_str = '<img src="images/dog.jpg" alt="">'
        self.image_filepath = None
        self.original_alt_text = ""
        self.generated_alt_text = None


def test_create_prompt():
    """
    Test generate_alt_text.create_prompt
    """
    import generate_alt_text
    image = DummyImage()
    generator = generate_alt_text.AltTextGenerator()
    data_uri = "data:image/jpeg;base64,FAKEBASE64DATA"
    prompt = generator.create_prompt(image, data_uri)
    assert isinstance(prompt, list)
    assert prompt[0]["role"] == "user"
    content = prompt[0]["content"]
    assert any(c.get("type") == "input_text" for c in content)
    assert any(c.get("type") == "input_image" for c in content)
    # Check that context is included
    text_part = next(c["text"] for c in content if c.get("type") == "input_text")
    assert "A dog is running." in text_part
    assert "The dog stops." in text_part
    assert "A brown dog." in text_part
    assert data_uri in [c["image_url"] for c in content if c.get("type") == "input_image"]

def test_generate_alt_text(monkeypatch):
    """
    Test generate_alt_text.generate_alt_text
    """
    import generate_alt_text
    image = DummyImage()
    generator = generate_alt_text.AltTextGenerator()
    data_uri = "data:image/jpeg;base64,FAKEBASE64DATA"
    class FakeResponse:
        output_text = "This is an image of a dog."
    class FakeClient:
        class responses:
            @staticmethod
            def create(model, input):
                return FakeResponse()
    monkeypatch.setattr("generate_alt_text.client", FakeClient())
    alt_text = generator.generate_alt_text(image, data_uri)
    assert "dog" in alt_text.lower()


def test_openai_key_missing(monkeypatch, tmp_path):
    """Test that OpenAIKeyMissingError is raised if the API key is missing."""
    from generate_alt_text import check_api_key, OpenAIKeyMissingError
    
    # Create empty .env file in tmp_path
    empty_env = tmp_path / ".env"
    empty_env.touch()
    
    # Remove API key from environment
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    
    with pytest.raises(OpenAIKeyMissingError):
        check_api_key(dotenv_path=empty_env)

