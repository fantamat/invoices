from transformers import AutoProcessor, AutoModelForCausalLM
import torch
import time
import json
import os
import base64
from markitdown import MarkItDown
from pdf2image import convert_from_path

from test_utility import test_all, text_to_json

from invoice_service.invoice_types import Invoice



from huggingface_hub import login
login(token=os.environ.get("HF_TOKEN", ""))


def hf_prepare_message_content(file_path):
    image_files = []
    temp_folder = "data/temp_images"
    os.makedirs(temp_folder, exist_ok=True)
    prompt = "Extract the structured data from the image in the JSON format. Return the response as valid JSON within ```json and ``` markers."
    if file_path.endswith(".jpg") or file_path.endswith(".jpeg") or file_path.endswith(".png"):
        image_files.append(file_path)
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
            temp_filename = os.path.join(temp_folder, f"page_{len(image_files)}.jpg")
            page.save(temp_filename, format="JPEG")
            image_files.append(temp_filename)
    
    out = [{
        "type": "text",
        "text": prompt,
    }]

    for image_file in image_files:
        out.append({
            "type": "image",
            "path": image_file,
        })

    return out




def main():
    from transformers import pipeline
    
    # Initialize the pipeline with a suitable model
    pipe = pipeline(model="CohereLabs/aya-vision-32b", task="image-text-to-text", device_map="auto")
    
    # Function to process an image and return structured JSON
    def process_image_with_pipeline(file_path):
        # Format message with the model's chat template                
        messages = [
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": "You are an invoice processing assistant. Extract all relevant invoice information accurately."}
                ]
            },
            {
                "role": "user",
                "content": hf_prepare_message_content(file_path)
            },
        ]

        # Try to extract and parse JSON from the response
        for i in range(5):
            # Generate output from the model
            outputs = pipe(text=messages)
            response = outputs[0] if isinstance(outputs, list) else outputs
            try:
                parsed_json = text_to_json(response)
                break
            except json.JSONDecodeError as e:
                print(f"Attempt {i+1}: Failed to parse JSON, retrying... Error: {e}")
        else:
            return {"error": "Failed to parse JSON after multiple attempts", "raw_response": response}
        return {
            "invoice": parsed_json,
        }
    
    # Test the pipeline with your invoice images
    test_all(process_image_with_pipeline, "data/test_outputs/hf_aya_vision_32b/")


if __name__ == "__main__":
    main()