import os
import json
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

        #prompt for gemini
        prompt = f"Write Episode {state['current_episode']} for {[state['series_name']]}. Context: {state['world_bible']}. Previous status: {state['protagonist']['current_status']}. Return JSON with scenes and a cliffhanger."
        response = client.chat.completions.create(
            model="google/gemini-3-flash-preview",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type":"json_object"}
        )

        return json.loads(response.choices[0].message.content)

#prevent regeneration of same episode, append to progress
def update_series_state(new_episode_data):
    with open('database/series_progress.json') as f:
        state = json.load(f)

    state['current_episode'] +=1
    state['protagonist']['current_status'] = new_episode_data['next_episode_hook']

    with open('database/series_progress', 'w') as f:
        json.dump(state, f, indent=2)
    
    print(f"Database updated to Episode {state['current_episode']}")