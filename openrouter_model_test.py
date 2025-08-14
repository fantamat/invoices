import os
import time
import base64
import traceback
import requests
import json

from test_utility import test_all
from invoice_service.invoice_types import Invoice
from markitdown import MarkItDown
from pdf2image import convert_from_path
from io import BytesIO


def openrouter_prepare_message_content(file_path):
    images = []
    prompt = "Extract the structured data from the image in the given JSON format."
    if file_path.endswith(".jpg") or file_path.endswith(".jpeg") or file_path.endswith(".png"):
        with open(file_path, "rb") as f:
            image_data = f.read()
        base64_image = base64.b64encode(image_data).decode("utf-8")
        if file_path.endswith(".png"):
            images.append(f"data:image/png;base64,{base64_image}")
        elif file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
            images.append(f"data:image/jpeg;base64,{base64_image}")
        elif file_path.endswith(".gif"):
            images.append(f"data:image/gif;base64,{base64_image}")
    elif file_path.endswith(".pdf"):
        md = MarkItDown(enable_plugins=False)
        with open(file_path, 'rb') as f:
            result = md.convert_stream(f, mime_type='application/pdf')
        markdown_text = result.text_content
        if len(markdown_text) > 4000:
            print(f"Warning: PDF text content is very long ({len(markdown_text)} characters). This may affect processing.")
            markdown_text = markdown_text[:4000]
        if markdown_text:
            prompt += f"\n\nHere is the extracted text from the PDF:\n{markdown_text}"
        contents = convert_from_path(file_path)
        if len(contents) > 5:
            contents = contents[:5]
            print(f"PDF has more than 5 pages, limiting to first 5 pages")
        for page in contents:
            buffer = BytesIO()
            page.save(buffer, format="JPEG")
            buffer.seek(0)
            base64_image = base64.b64encode(buffer.read()).decode("utf-8")
            images.append(f"data:image/jpeg;base64,{base64_image}")
    
    out = [{
        "type": "text",
        "text": prompt,
    }]

    for image_data in images:
        out.append({
            "type": "image_url",
            "image_url": {
                "url": image_data
            }
        })

    return out


def openrouter_send_request(model_name, api_key, user_content):

    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        data=json.dumps({
            "model": model_name,
            "messages": [
                {"role": "system", "content": "You are an invoice processing assistant. Extract all relevant invoice information accurately."},
                {"role": "user", "content": user_content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "InvoiceData",
                    "schema": Invoice.model_json_schema(),
                    "strict": True,
                },
            },
        })
    )

    if response.status_code != 200:
        raise Exception(f"OpenRouter API request failed: {response.status_code} - {response.text}")
    
    response_data = response.json()

    if "choices" not in response_data or len(response_data["choices"]) == 0:
        raise Exception("OpenRouter API response does not contain choices")
    
    generated_text = response_data["choices"][0]["message"]["content"]
    token_count = response_data["usage"]["total_tokens"]
    try:
        invoice = Invoice.model_validate_json(generated_text)
        return invoice, token_count
    except Exception as e:
        return None



def openrouter_test_model(model_name, api_key, site_url=None, site_title=None):
    print(f"Using OpenRouter model: {model_name}")

    extra_headers = {}
    if site_url:
        extra_headers["HTTP-Referer"] = site_url
    if site_title:
        extra_headers["X-Title"] = site_title

    def process_file(file_path):
        try:
            payload = openrouter_prepare_message_content(file_path)
            print(f"Processing file: {file_path}")
            invoice, token_count = openrouter_send_request(model_name, api_key, payload)
            if invoice is None:
                print(f"Warning: Could not parse generated text as Invoice for {file_path}. Generated text: {generated_text}")
                return {"error": "Could not parse generated text as Invoice", "generated_text": generated_text}
            print(f"Parsed Invoice for {file_path}: {invoice.model_dump_json(indent=2)}")
            return {
                "invoice": invoice.model_dump(),
                "file_path": file_path,
                "total_token_count": token_count,
            }
        except Exception as e:
            print(f"Error processing {file_path} with OpenRouter: {e}")
            traceback_str = traceback.format_exc()
            print(traceback_str)
            return {"error": f"General error processing with OpenRouter: {str(e)}", "traceback": traceback_str}

    base_model_name = model_name.replace(":", "_").replace("/", "_")
    output_dir = f"data/test_outputs/openrouter_{base_model_name}/"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    test_all(process_file, output_dir)

def main():
    # Set your OpenRouter API key in the environment variable OPENROUTER_API_KEY
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: Please set the OPENROUTER_API_KEY environment variable.")
        return

    TEST_MODELS = [
        "meta-llama/llama-4-maverick", # OK
        # "google/gemma-3-27b-it:free", # Missing `additionalProperties: False` in object schema\",\"type\":\"invalid_request_json_schema
        # "mistralai/mistral-medium-3", # Missing `additionalProperties: False` in object schema
        # "opengvlab/internvl3-14b", # May use data for training, not for inference
        "moonshotai/kimi-vl-a3b-thinking:free", # OK
        "meta-llama/llama-4-scout", 
        "mistralai/mistral-small-3.1-24b-instruct:free",
        "microsoft/phi-4-multimodal-instruct",
        "mistralai/pixtral-large-2411",
        # Add other OpenRouter model names here
    ]
    site_url = os.getenv("OPENROUTER_SITE_URL")
    site_title = os.getenv("OPENROUTER_SITE_TITLE")
    for model_name in TEST_MODELS:
        print(f"Testing OpenRouter model: {model_name}")
        t0 = time.time()
        openrouter_test_model(model_name, api_key, site_url, site_title)
        print(f"Finished testing model {model_name} in {time.time() - t0:.2f} seconds\n")

if __name__ == "__main__":
    main()