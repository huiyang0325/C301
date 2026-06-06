from dotenv import load_dotenv
load_dotenv('.env')
import asyncio
from pathlib import Path
from lib.video_backends.grok_keyi import GrokKeyiVideoBackend
from lib.video_backends.base import VideoGenerationRequest
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

async def test():
    backend = GrokKeyiVideoBackend(api_key='sk-f95c535cbE1B48C99dB418fB69c9c812355B44bb959ECc3f')
    req = VideoGenerationRequest(
        prompt='女子缓缓转身，裙摆随风轻扬',
        start_image=Path('projects/1-ff6183db/storyboards/scene_E01S01.png'),
        duration_seconds=6,
        aspect_ratio='16:9',
        resolution='480p',
        output_path=Path('test_grok.mp4'),
    )
    result = await backend.generate(req)
    print(f'成功: {result.video_path}')

asyncio.run(test())
