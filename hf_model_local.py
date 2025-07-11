from transformers import AutoProcessor, AutoModelForCausalLM
import torch
import time
import json

from test_utility import test_all, text_to_json




def test_model(model_id, out_folder):
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id
        # attn_implementation="flex_attention",
        # device_map="auto",  
        # torch_dtype=torch.bfloat16,
    )

    def process_image(image_path):
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "path": image_path},
                    {"type": "text", "text": "Extract the structured data from the image in the JSON format."},
                ]
            },
        ]

        inputs = processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        ).to(model.device)

        outputs = model.generate(
            **inputs,
            max_new_tokens=256,
        )

        response = processor.batch_decode(outputs[:, inputs["input_ids"].shape[-1]:])[0]
        print(response)

        out = text_to_json(response)
        return out


    test_all(process_image, f"data/outputs/{out_folder}_local/")




def main2():

    TESTS = [
        
        ("deepseek_1.3B", "deepseek-ai/deepseek-vl-1.3b-chat"),
        ("qwen2", "Qwen/Qwen2-VL-7B-Instruct"),
        
        
        ("gemma_3n", "google/gemma-3n-E4B-it-litert-preview"),

        ("llama4_17B", "meta-llama/Llama-4-Scout-17B-16E-Instruct"),
    ]

    for out_folder, model_id in TESTS:
        print(f"Testing model {model_id} with output folder {out_folder}")
        t0 = time.time()
        test_model(model_id, out_folder)
        print(f"Finished testing model {model_id} in {time.time() - t0:.2f} seconds\n")

def main():
    from transformers import pipeline
    
    # Initialize the pipeline with a suitable model
    pipe = pipeline(model="CohereLabs/aya-vision-32b", task="image-text-to-text", device_map="auto")
    
    # Function to process an image and return structured JSON
    def process_image_with_pipeline(image_path):
        # Format message with the model's chat template
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "path": image_path},
                    {"type": "text", "text": "Extract the structured data from the image in the JSON format. Return the response as valid JSON within ```json and ``` markers."},
                ]
            },
        ]
        
        # Generate output from the model
        outputs = pipe(text=messages, max_new_tokens=1024, return_full_text=False)
        response = outputs[0] if isinstance(outputs, list) else outputs
        
        try:
            # Try to extract and parse JSON from the response
            parsed_json = text_to_json(response)
            return parsed_json
        except Exception as e:
            return {"error": f"Failed to parse JSON response: {str(e)}", "raw_response": response}
    
    # Test the pipeline with your invoice images
    test_all(process_image_with_pipeline, "data/outputs/pipeline_structured/")


if __name__ == "__main__":
    main()