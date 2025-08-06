# from ..invoice_service.invoice_types import ExtendedInvoice
# from transformers import pipeline
# import json

# pipe = pipeline("image-text-to-text", model="CohereLabs/aya-vision-32b")

# # Example image and prompt
# messages = [
#     {
#         "role": "system",
#         "content": [
#             {
#                 "type": "text", 
#                 "text": (
#                     "Extract all invoice information in the following JSON format. "
#                     "Respond ONLY with valid JSON, no explanations or extra text.\n"
#                     f"{json.dumps(ExtendedInvoice.model_json_schema(), indent=2)}"
#             )}
#         ]
#     },
#     {
#         "role": "user",
#         "content": [
#             {"type": "image", "url": "https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/p-blog/candy.JPG"},
#         ]
#     },
# ]

# result = pipe(text=messages)
# # Try to parse and validate the result
# try:
#     invoice = ExtendedInvoice.model_validate_json(result[0]['generated_text'])
#     print("Valid invoice:", invoice.model_dump_json(indent=2))
# except Exception as e:
#     print("Invalid invoice format:", e)








import os
from openai import OpenAI

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.environ["HF_TOKEN"],
)

completion = client.chat.completions.create(
    model="CohereLabs/aya-vision-32b",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Describe this image in one sentence."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "https://cdn.britannica.com/61/93061-050-99147DCE/Statue-of-Liberty-Island-New-York-Bay.jpg"
                    }
                }
            ]
        }
    ],
)

print(completion.choices[0].message)