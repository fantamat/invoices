import requests
import base64
import json
import time
import os

from test_utility import test_all, text_to_json
from invoice_service.invoice_types import Invoice
import traceback


def ollama_test_model(ollama_model_name, ollama_host="http://localhost:11434"):
    print(f"Using Ollama model: {ollama_model_name} on host: {ollama_host}")

    # Ensure the Ollama model is available
    tags_response = requests.get(f"{ollama_host}/api/tags")
    tags_response.raise_for_status()
    tags = tags_response.json().get("models", [])
    model_names = [m["name"] for m in tags]
    if ollama_model_name not in model_names:
        return {"error": f"Ollama API request failed: Model {ollama_model_name} not found on {ollama_host}"}

    def process_image(image_path):
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()
            base64_image = base64.b64encode(image_data).decode("utf-8")

            payload = {
                "model": ollama_model_name,
                "prompt": "Extract the structured data from the image in the given JSON format.",
                "images": [base64_image],
                "stream": False,  # Get the full response at once
                "format": Invoice.model_json_schema()
            }
            
            api_url = f"{ollama_host}/api/generate"
            
            print(f"Sending request to Ollama for {image_path}...")
            response = requests.post(api_url, json=payload) # Added timeout
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            response_json = response.json()
            
            # The actual generated text field can vary based on Ollama version or model.
            # Common fields are "response" for /api/generate or "message.content" for /api/chat
            generated_text = response_json.get("response")
            invoice = Invoice.model_validate_json(generated_text)
            if invoice is None:
                print(f"Warning: Could not parse generated text as Invoice for {image_path}. Generated text: {generated_text}")
                return {"error": "Could not parse generated text as Invoice", "generated_text": generated_text}
            
            print(f"Parsed Invoice for {image_path}: {invoice.model_dump_json(indent=2)}")
            return invoice.model_dump()

        except requests.exceptions.Timeout:
            print(f"Error: Request to Ollama timed out for image {image_path}.")
            return {"error": "Ollama request timed out"}
        except requests.exceptions.RequestException as e:
            print(f"Error: Could not connect to Ollama or API error for image {image_path}: {e}")
            return {"error": f"Ollama API request failed: {str(e)}"}
        except Exception as e:
            print(f"Error processing image {image_path} with Ollama: {e}")
            traceback_str = traceback.format_exc()
            print(traceback_str)
            return {"error": f"General error processing with Ollama: {str(e)}", "traceback": traceback_str}

    # Define the output directory for Ollama results
    base_model_name = ollama_model_name.replace(":", "_").replace("/", "_")
    output_dir = f"data/outputs/ollama_{base_model_name}/"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    test_all(process_image, output_dir)



def main():
    # Ensure you have a multimodal model like LLaVA running in Ollama.
    # You can set the OLLAMA_MODEL environment variable or change the default here.
    
    TEST_MODELS = [
        # "gemma3:4b",
        # "qwen2.5vl:7b",
        # "llava:7b",
        # "llava-llama3:8b",
        # larger models
        #"llama3.2-vision:11b",
        #"gemma3:12b",       
        #"llama4:16x17b",
        "llava:34b",
    ]
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")  # Default Ollama host
    for model_name in TEST_MODELS:
        print(f"Testing Ollama model: {model_name} on host: {ollama_host}")
        t0 = time.time()
        ollama_test_model(model_name, ollama_host)
        print(f"Finished testing model {model_name} in {time.time() - t0:.2f} seconds\n")


if __name__ == "__main__":
    main()
