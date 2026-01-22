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

    #first get bible context if available
    bible_context = ""
    if os.path.exists('database/world_bible.txt'):
        with open('database/world_bible.txt') as b:
            bible_context = b.read()

    #Load memory from DB
    with open('database/series_progress.json') as f:
        state = json.load(f)

        system_msg = "You are a cinematic scriptwriter. You ONLY respond in valid JSON. Never add conversational text. Base your story logic on the following World Bible context: \n "
        f"{bible_context}"

        #prompt for gemini
        prompt = f"""
                Write a 60-second high-tension narration script for Episode {state['current_episode']} of '{state['series_name']}'.

                TECHNICAL REQUIREMENT:
                - Every single 'voiceover' and 'visual_prompt' MUST include the string: "(seed {state['protagonist']['visual_seed']})".
                - If you mention the main character or secondary characters by their name or pronoun, you must attach that seed. This is for image generation consistency.

                STRICT NARRATIVE STYLE:
                1. THE NARRATOR: You are an indifferent witness recording a subject. No emotions.
                2. NO SLOP: Do not use flowery metaphors. No 'rot', 'doom', 'void', or 'gods'.
                3. THE DICTION: Use blue-collar English. Describe physical facts. 
                - Instead of: "He feels the weight of his sins," 
                - Use: "His heart rate is 110. He is sweating."
                4. STRUCTURE: 10 scenes. Total duration 60 seconds. Each scene ~6 seconds. Around 15-20 words per scene.

                STRICT METADATA:
                - SFX must be in [BRACKETS] at the very end of the voiceover field.

                OUTPUT FORMAT EXAMPLE (JSON ONLY):
                {{
                "episode_title": "{state['series_name']} - Episode {state['current_episode']}",
                "lore_update": "One sentence summarizing the permanent change in the world or character state.",
                "scenes": [
                    {{
                    "id": 1,
                    "voiceover": "Elias (seed {state['protagonist']['visual_seed']}) enters the radio station. The air is heavy. [FOOTSTEPS ON GRIT]",
                    "visual_prompt": "Found footage style, gritty DC Comics aesthetic, 9:16. Elias (seed {state['protagonist']['visual_seed']}) steps into a dark station with a flashlight.",
                    "duration": 6
                    }}
                ]
                }}
                """
        
        
        response = client.chat.completions.create(
            model="google/gemini-3-flash-preview",
            messages=[{"role": "system", "content": system_msg},{"role": "user", "content": prompt}],
            response_format={"type":"json_object"}
        )
        raw_content = response.choices[0].message.content
        clean_json = re.sub(r"```json|```","",raw_content).strip()
        data = json.loads(clean_json)
    
        os.makedirs('output/temp', exist_ok=True)
        with open('output/temp/current_script.json', 'w') as f:
            json.dump(data, f, indent=2)
        
        return data

def update_world_bible(new_episode_data):
    lore = new_episode_data.get('lore_update', "Subject Elias continued forward. No significant lore changes recorded.")
    episode_num = new_episode.get('episode_title', "Unknown Episode")

    bible_path="database/world_bible.txt"
    with open(bible_path, 'a') as f:
        f.write(f"\n Episode Log [{episode_num}]: {lore}")
    print(f"Lore added to Bible: {lore}")



#prevent regeneration of same episode, append to progress
def update_series_state(new_episode_data):
    with open('database/series_progress.json') as f:
        state = json.load(f)

    state['current_episode'] +=1
    state['protagonist']['current_status'] = new_episode_data.get('next_status', "The story continues...")

    with open('database/series_progress.json', 'w') as f:
        json.dump(state, f, indent=2)

    update_world_bible(new_episode_data)
    
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