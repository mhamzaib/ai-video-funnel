import os
import json
import re
import requests
import fal_client
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

#use standard client, not using this at the moment, testing...
media_client = OpenAI (
    api_key=os.getenv("OPENAI_API_KEY")
)

def generate_voiceover(scene_id, text):
    print(f"Generating audio for scene {scene_id}...")
    clean_text = re.sub(r'\(.*?\)', '', text).strip()
    dramatic_text = clean_text.replace(". ", "...  ").replace("! ", "!!!  ")
    
    ## ONLY TESTING SO USING Edge tts
    response = media_client.audio.speech.create(
        model="tts-1-hd",
        voice="onyx",
        speed=1.1,
        input=dramatic_text
    )
    path = f"output/temp/audio/audio_{scene_id}.mp3"
    response.write_to_file(path)
    
    return path

##For now testing so disabling this
def generate_video_clip(scene_id, prompt):
    print(f"Scene {scene_id} Generating visuals...")
    fixed_seed = 6661013

    style_modifiers = "DC Comics style, cinematic graphic novel art, bold lines, cel-shaded, gritty atmosphere, highly detailed illustration, 9:16 aspect ratio"
    full_prompt = f"{prompt}, {style_modifiers}"
    
    # Using Flux for high-quality comic aesthetic
    handler = fal_client.submit(
        "fal-ai/flux/schnell",
        arguments={
            "prompt": full_prompt,
            "image_size": "portrait_16_9", 
            "num_inference_steps": 4,
            "seed": fixed_seed,
            "enable_safety_checker": True
        }
    )
    result = handler.get()
    image_url = result['images'][0]['url']
    
    path = f"output/temp/video/image_{scene_id}.jpg"
    r = requests.get(image_url)
    with open(path, 'wb') as f:
        f.write(r.content)
    return path

def process_all_assets():
    #check if script was generated
    script_path = 'output/temp/current_script.json'
    if not os.path.exists(script_path):
        print("Error: current_script.json not found, run brain.py first!")
        return
    with open(script_path) as f:
        script = json.load(f)
    
    os.makedirs('output/temp/audio', exist_ok=True)
    os.makedirs('output/temp/video', exist_ok=True)
    
    i = 0
    for scene in script['scenes']:
        if(i<2):
            generate_voiceover(scene['id'], scene['voiceover'])
            generate_video_clip(scene['id'], scene['visual_prompt'])
            i+=1
        else:
            break

    print("Assets generated in output/temp/")

## FOR TESTING ONLY
if __name__ == "__main__":
    process_all_assets()