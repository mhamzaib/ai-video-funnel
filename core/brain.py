import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI (
    base_url='https://openrouter.ai/api/v1',
    api_key=os.getenv("OPENROUTER_API_KEY")
)

def get_next_episode():
    #Load memory from DB
    with open('database/series_progress.json') as f:
        state = json.load(f)

        system_msg = "You are a cinematic scriptwriter. You ONLY respond in valid JSON. Never add conversational text"

        #prompt for gemini
        prompt = f"""
                    Write a terrifying 30-second horror narration for Episode {state['current_episode']} of '{state['series_name']}'.
                    Character: {state['protagonist']['name']} - {state['protagonist']['description']}
                    Narrator: An ominous, cold, and detached observer.

                    STRICT PRODUCTION RULES:
                    1. THE HOOK: Scene 1 MUST start with a sound description in the voiceover (e.g., "[WET THUD]... They say some doors should never be opened.").
                    2. NARRATOR VOICE: Use ALL CAPS for emphasis. Use "..." for long, chilling pauses. Use descriptive, atmospheric horror language.
                    3. VISUAL STYLE: Use 'Found Footage style, cinematic graphic novel art, heavy film grain, VHS glitch, shaky cam, distorted faces, 9:16'.
                    4. THE SEED: Every visual_prompt MUST include 'seed {state['protagonist']['visual_seed']}' for Elias to keep him consistent.
                    5. NO SLOP: Focus on the scenario. Describe Elias's suffering in the third person.

                    Return a JSON object with EXACTLY 6 scenes:
                    {{
                    "episode_title": "The Digital Rot",
                    "scenes": [
                        {{
                        "id": 1,
                        "voiceover": "[STATIC CRACKLE]... In the dark... the code began to bleed. Elias (seed {state['protagonist']['visual_seed']}) didn't realize... his reality was already DELETING.",
                        "visual_prompt": "Found footage style, DC Comics aesthetic, Elias (seed {state['protagonist']['visual_seed']}) staring in horror at a glitching screen, heavy grain, bold lines, 9:16",
                        "duration": 5
                        }},
                        // ... total of 6 scenes
                    ],
                    "next_status": "A cliffhanger summary for the database"
                    }}
                """
        
        
        response = client.chat.completions.create(
            model="google/gemini-3-flash-preview",
            messages=[{"rote": "system", "content": system_msg},{"role": "user", "content": prompt}],
            response_format={"type":"json_object"}
        )
        raw_content = response.choices[0].message.content
        clean_json = re.sub(r"```json|```","",raw_content).strip()
        data = json.loads(clean_json)
    
        os.makedirs('output/temp', exist_ok=True)
        with open('output/temp/current_script.json', 'w') as f:
            json.dump(data, f, indent=2)
        
        return data

#prevent regeneration of same episode, append to progress
def update_series_state(new_episode_data):
    with open('database/series_progress.json') as f:
        state = json.load(f)

    state['current_episode'] +=1
    state['protagonist']['current_status'] = new_episode_data.get('next_status', "The story continues...")

    with open('database/series_progress.json', 'w') as f:
        json.dump(state, f, indent=2)
    
    print(f"Database updated to Episode {state['current_episode']}")


# FOR TESTING ONLY
if __name__ == "__main__":
    try:
        print("--- Testing Brain & Memory System ---")
        new_episode = get_next_episode()
        
        print(f"TITLE: {new_episode.get('episode_title')}")
        print(f"FIRST SCENE VO: {new_episode['scenes'][0]['voiceover']}")
        print(f"NEXT STATUS: {new_episode.get('next_status')}")
        
        update_series_state(new_episode)
        
        print("--- Test Successful ---")
    except Exception as e:
        print(f"--- Test Failed: {e} ---")