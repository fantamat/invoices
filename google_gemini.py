import os

from PIL import Image
from google import genai

from test_utility import test_all, process_pdf


from invoice_service.invoice_types import Invoice



def main():
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    def process_image(file_path):

        base_prompt = "Extract the structured data from the image in the given JSON format."

        if file_path.endswith('.pdf'):
            images, prompt_fragment = process_pdf(file_path)
            contents = images + [base_prompt + prompt_fragment]
        else:
            
            image = Image.open(file_path)
            contents = [image, base_prompt]
            # response = client.models.generate_content(
            #     model="gemini-2.5-pro-exp-03-25",
            #     contents=[image, "Extract the structured data from the image in the JSON format."],
            # )

        response = client.models.generate_content(
            model="gemini-2.5-pro-preview-03-25",
            contents=contents,
            config={
                'response_mime_type': 'application/json',
                'response_schema': Invoice,
            },
        )
        invoice: Invoice = response.parsed
        return {
            "invoice": invoice.model_dump(),
            "total_token_count": response.usage_metadata.total_token_count,
        }

    test_all(process_image, "data/test_outputs/gemini-pro-preview/")


if __name__ == "__main__":
    main()