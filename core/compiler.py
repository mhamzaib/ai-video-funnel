import os
import json
import re
from moviepy import AudioFileClip, ImageClip, concatenate_videoclips, CompositeAudioClip

def compile_video():
    print(f"startomg compilation of video...")

    #script load?
    script_path = os.path.join('output', 'temp', 'current_script.json')
    with open(script_path, 'r') as f:
        script = json.load(f)
    
    episode_title = script.get('episode_title', 'unknown episode')

    scenes = script['scenes']
    clips = []

    for scene in scenes:
        scene_id = scene['id']
        image_path = os.path.join('output', 'temp', 'video', f"image_{scene_id}.jpg")
        audio_path = os.path.join('output', 'temp', 'audio', f"audio_{scene_id}.mp3")

        if not os.path.exists(image_path) or not os.path.exists(audio_path):
            continue

        voice_audio = AudioFileClip(audio_path)

        #SFX matching
        sfx_match = re.search(r'\[(.*?)\]', scene['voiceover'])
        final_audio = voice_audio

        if sfx_match:
            sfx_tag = sfx_match.group(1).lower().replace(" ", "_")
            sfx_file = f"assets/sfx/{sfx_tag}.mp3"

            # Merge sfx with audio
            if os.path.exists(sfx_file):
                sfx_audio = AudioFileClip(sfx_file).with_volume_scaled(0.3)
                final_audio = CompositeAudioClip([voice_audio, sfx_audio.with_start(0)])
        
        #finalize video clip
        img_clip = (ImageClip(image_path).with_duration(voice_audio.duration)).resized(height=1920)
        
        #adding audio later as per gemini's instructions. Change as needed
        img_clip = img_clip.with_audio(final_audio)
        clips.append(img_clip)

    if clips:
        final_video = concatenate_videoclips(clips, method="compose")
        output_filename = f"{episode_title.replace(' ', '_')}.mp4"
        output_path = os.path.join("output", output_filename)

        final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")

if __name__ == '__main__':
    compile_video()