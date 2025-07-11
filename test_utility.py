import os
import json
import time
import base64
from io import BytesIO
from pdf2image import convert_from_path
from markitdown import MarkItDown  # Microsoft's library for converting documents to markdown
from PIL import Image


TEST_DATA_FOLDER = "data/invoices"


def test_all(process_fun, output_folder):

    files = []
    for dirpath, _, filenames in os.walk(TEST_DATA_FOLDER):
        for filename in filenames:
            if filename.endswith(('.pdf', '.jpg', '.jpeg', '.png')):
                files.append(os.path.join(dirpath, filename))

    for file in files:
        print(f"File: {file}")

        output_filename = os.path.join(output_folder, os.path.splitext(file)[0] + ".json")

        if os.path.exists(output_filename):
            with open(output_filename, "r") as f:
                existing_data = json.load(f)
            if existing_data:
                if "error" in existing_data:
                    print(f"Error in existing output: {existing_data['error']}")
                else:
                    print(f"Output already exists for {file}, skipping processing.")
                    continue  # Skip processing if output already exists

        t0 = time.time()
        out = process_fun(file)
        if isinstance(out, list):
            if len(out) == 1:
                out = out[0]
                out["time"] = time.time() - t0
        else:
            out["time"] = time.time() - t0
                

        if not os.path.exists(os.path.dirname(output_filename)):
            os.makedirs(os.path.dirname(output_filename))
        with open(output_filename, "w") as f:
            json.dump(out, f, indent=2)

        print(out)


def text_to_json(text):
    json_start = text.find("```json\n") + len("```json\n")
    json_end = text.find("```", json_start)
    json_str = text[json_start:json_end].strip()

    out = json.loads(json_str)
    return out


def process_pdf(file_path):
    # Use MarkItDown to convert PDF to markdown text
    md = MarkItDown(enable_plugins=False)
    with open(file_path, 'rb') as f:
        result = md.convert_stream(f, mime_type='application/pdf')
    
    markdown_text = result.text_content
    if len(markdown_text) > 4000:
        print(f"Warning: PDF text content is very long ({len(markdown_text)} characters). This may affect processing.")
        markdown_text = markdown_text[:4000]  # Limit to first 4,000 characters

    prompt_fragment = f"\n\nHere is the extracted text from the PDF:\n{markdown_text}"

    # Also convert PDF to image for visual analysis

    contents = convert_from_path(file_path)
    if len(contents) > 5:
        contents = contents[:5]  # Limit to first 5 pages
        print(f"PDF has more than 5 pages, limiting to first 5 pages")
    
    images = []
    for page in contents:
        buffer = BytesIO()
        page.save(buffer, format="JPEG")
        buffer.seek(0)
        img = Image.open(buffer)
        images.append(img)

    return images, prompt_fragment
    
