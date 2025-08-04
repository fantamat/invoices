import requests
import base64
import time
import os

from test_utility import test_all
from invoice_service.invoice_types import ExtendedInvoice
import traceback
from markitdown import MarkItDown  # Microsoft's library for converting documents to markdown
from pdf2image import convert_from_path
from io import BytesIO




def ollama_prepare_payload(ollama_model_name, file_path, output_model):
    images = []
    prompt = "Extract the structured data from the image in the given JSON format."
    if file_path.endswith(".jpg") or file_path.endswith(".jpeg") or file_path.endswith(".png"):
        with open(file_path, "rb") as f:
            image_data = f.read()
        base64_image = base64.b64encode(image_data).decode("utf-8")
        images.append(base64_image)
    elif file_path.endswith(".pdf"):
        # Use MarkItDown to convert PDF to markdown text
        md = MarkItDown(enable_plugins=False)
        with open(file_path, 'rb') as f:
            result = md.convert_stream(f, mime_type='application/pdf')
        
        markdown_text = result.text_content
        if len(markdown_text) > 4000:
            print(f"Warning: PDF text content is very long ({len(markdown_text)} characters). This may affect processing.")
            markdown_text = markdown_text[:4000]  # Limit to first 4,000 characters

        prompt += f"\n\nHere is the extracted text from the PDF:\n{markdown_text}"

        # Also convert PDF to image for visual analysis

        contents = convert_from_path(file_path)
        if len(contents) > 5:
            contents = contents[:5]  # Limit to first 5 pages
            print(f"PDF has more than 5 pages, limiting to first 5 pages")
        
        for page in contents:
            buffer = BytesIO()
            page.save(buffer, format="JPEG")
            buffer.seek(0)
            images.append(base64.b64encode(buffer.read()).decode("utf-8"))
    
    return {
        "model": ollama_model_name,
        "system": "You are an invoice processing assistant. Extract all relevant invoice information accurately.",
        "prompt": prompt,
        "images": images,
        "stream": False,  # Get the full response at once
        "format": output_model.model_json_schema()
    }


def ollama_test_model(ollama_model_name, ollama_host):
    print(f"Using Ollama model: {ollama_model_name} on host: {ollama_host}")

    # Ensure the Ollama model is available
    tags_response = requests.get(f"{ollama_host}/api/tags")
    tags_response.raise_for_status()
    tags = tags_response.json().get("models", [])
    model_names = [m["name"] for m in tags]
    if ollama_model_name not in model_names:
        return {"error": f"Ollama API request failed: Model {ollama_model_name} not found on {ollama_host}"}

    def process_file(file_path):
        try:
            payload = ollama_prepare_payload(ollama_model_name, file_path, ExtendedInvoice)
            
            api_url = f"{ollama_host}/api/generate"
            
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Sending request to Ollama for {file_path}...")
            response = requests.post(api_url, json=payload) # Added timeout
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            response_json = response.json()
            
            # The actual generated text field can vary based on Ollama version or model.
            # Common fields are "response" for /api/generate or "message.content" for /api/chat
            generated_text = response_json.get("response")
            invoice = ExtendedInvoice.model_validate_json(generated_text)
            if invoice is None:
                print(f"Warning: Could not parse generated text as Invoice for {file_path}. Generated text: {generated_text}")
                return {"error": "Could not parse generated text as Invoice", "generated_text": generated_text}
            
            print(f"Parsed Invoice for {file_path}: {invoice.model_dump_json(indent=2)}")
            return {
                "invoice": invoice.model_dump(),
                "total_token_count": response_json.get("usage", {}).get("total_token_count", 0),
                "file_path": file_path,

            }

        except requests.exceptions.Timeout:
            print(f"Error: Request to Ollama timed out for image {file_path}.")
            return {"error": "Ollama request timed out"}
        except requests.exceptions.RequestException as e:
            print(f"Error: Could not connect to Ollama or API error for image {file_path}: {e}")
            return {"error": f"Ollama API request failed: {str(e)}"}
        except Exception as e:
            print(f"Error processing image {file_path} with Ollama: {e}")
            traceback_str = traceback.format_exc()
            print(traceback_str)
            return {"error": f"General error processing with Ollama: {str(e)}", "traceback": traceback_str}

    # Define the output directory for Ollama results
    base_model_name = ollama_model_name.replace(":", "_").replace("/", "_")
    output_dir = f"data/test_outputs/ollama_{base_model_name}/"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    test_all(process_file, output_dir)



def main():
    # Ensure you have a multimodal model like LLaVA running in Ollama.
    # You can set the OLLAMA_MODEL environment variable or change the default here.
    
    TEST_MODELS = [
        "gemma3:4b",
        "qwen2.5vl:7b",
        "llava:7b",
        # larger models
        #"llama3.2-vision:11b",
        "gemma3:12b",       
        "llava:34b",
        #"mistral-small3.2:24b",
        "gemma3:27b",
        #"qwen2.5vl:32b",
        
    ]
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")  # Default Ollama host
    for model_name in TEST_MODELS:
        print(f"Testing Ollama model: {model_name} on host: {ollama_host}")
        t0 = time.time()
        ollama_test_model(model_name, ollama_host)
        print(f"Finished testing model {model_name} in {time.time() - t0:.2f} seconds\n")


if __name__ == "__main__":
    main()
