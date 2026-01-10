import asyncio
import os
import json
import edge_tts
import fal_client
from openai import OpenAI
from dotenv import load_dotenv
import requests

load_dotenv()

#use standard client, not using this at the moment, testing...
# client = OpenAI (
#     api_key=os.getenv("OPENAI_API_KEY")
# )

def generate_voiceover(scene_id, text):
    print(f"Generating audio for scene {scene_id}...")
    
    ## ONLY TESTING SO USING Edge tts
    # response = client.audio.speech.create(
    #     model="tts-1",
    #     voice="onyx",
    #     input=text
    # )
    # path = f"output/temp/audio_{scene_id}.mp3"
    # response.write_to_file(path)
    voice = "en-IN-NeerjaNeural" 
    path = f"output/temp/audio_{scene_id}.mp3"
    
    # edge-tts is asynchronous, so we run it simply like this:
    communicate = edge_tts.Communicate(text, voice)
    asyncio.run(communicate.save(path))
    
    return path

##For now testing so disabling this
def generate_video_clip(scene_id, prompt):
    return
    # print(f"Generating video for scene {scene_id}...")

    # handler = fal_client.submit(
    #     "fal-ai/wan/v2.1/1.3b/text-to-video",
    #     arguments={
    #         "prompt": prompt,
    #         "aspect_ratio": "9:16"
    #     }
    # )
    # result = handler.get()
    # video_url = result['video']['url']

    # path = f"output/temp/video_{scene_id}.mp4"
    # r = requests.get(video_url)
    # with open(path, 'wb') as f:
    #     f.write(r.content)
    # return path

def process_all_assets():
    script_path = 'output/temp/current_script.json'

    if not os.path.exists(script_path):
        print("Error: current_script.json not found, run brain.py first!")
        return
    with open(script_path) as f:
        script = json.load(f)
    
    for scene in script['scenes']:
        generate_voiceover(scene['id'], scene['voiceover'])
        generate_video_clip(scene['id'], scene['visual_prompt'])

    print("Assets generated in output/temp/")

## FOR TESTING ONLY
if __name__ == "__main__":
    process_all_assets()