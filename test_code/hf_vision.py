import torch
from transformers import AutoProcessor, AutoModelForVision2Seq
from PIL import Image
import gradio as gr

# Load vision-language model (adjust to your GPU capabilities)
model_name = "llava-hf/llava-1.5-7b-hf"  # Hugging Face variant of LLaVA

processor = AutoProcessor.from_pretrained(model_name)
model = AutoModelForVision2Seq.from_pretrained(
    model_name,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    low_cpu_mem_usage=True,
).eval()

if torch.cuda.is_available():
    model = model.to("cuda")

# Czech prompt support
CZ_PROMPT_TEMPLATE = "Popiš, co vidíš na tomto obrázku česky:\n"

def process(image, prompt):
    inputs = processor(images=image, text=CZ_PROMPT_TEMPLATE + prompt, return_tensors="pt").to(model.device)
    with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=100)
    response = processor.batch_decode(output, skip_special_tokens=True)[0]
    return response

# Gradio UI
gr.Interface(
    fn=process,
    inputs=[
        gr.Image(type="pil", label="Obrázek"),
        gr.Textbox(lines=2, label="Český dotaz", value="Co je na obrázku?"),
    ],
    outputs="text",
    title="Vision LLM s podporou češtiny",
    description="Nahraj obrázek a zeptej se na něj česky.",
).launch()







from transformers import Blip2Processor, Blip2ForConditionalGeneration

processor = Blip2Processor.from_pretrained("Salesforce/blip2-opt-2.7b")
model = Blip2ForConditionalGeneration.from_pretrained(
    "Salesforce/blip2-opt-2.7b", torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
)
model.to("cuda" if torch.cuda.is_available() else "cpu")

def cz_caption(image):
    prompt = "Popiš tento obrázek česky:"
    inputs = processor(image, prompt, return_tensors="pt").to(model.device)
    out = model.generate(**inputs, max_new_tokens=100)
    return processor.decode(out[0], skip_special_tokens=True)
