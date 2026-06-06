"""Debug workflow 6 - minimal test"""
import json, httpx, asyncio

async def main():
    # Minimal test with exact same structure as workflow 6 converted
    prompt = {
        '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'z_image_turbo_bf16.safetensors', 'weight_dtype': 'default'}},
        '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': 'qwen_3_4b.safetensors', 'type': 'qwen_image', 'device': 'default'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'zimage ae.safetensors'}},
        '4': {'class_type': 'KSampler', 'inputs': {'model': [1, 0], 'positive': [5, 0], 'negative': [6, 0], 'latent_image': [7, 0], 'seed': 700127413627084, 'steps': 9, 'cfg': 9, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1.0}},
        '5': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': [2, 0], 'text': 'test'}},
        '6': {'class_type': 'ConditioningZeroOut', 'inputs': {'conditioning': [5, 0]}},
        '7': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 720, 'height': 1280, 'batch_size': 1}},
        '8': {'class_type': 'VAEDecode', 'inputs': {'samples': [4, 0], 'vae': [3, 0]}},
        '11': {'class_type': 'easy promptList', 'inputs': {'optional_prompt_list': 't1', 'prompt_1': 't2', 'prompt_2': 't3', 'prompt_3': 't4', 'prompt_4': 't5'}},
        '20': {'class_type': 'SaveImage', 'inputs': {'images': [8, 0], 'filename_prefix': 'test'}},
    }

    print("Submitting minimal workflow 6...")
    print(f"Prompt keys: {list(prompt.keys())}")
    print(f"Node 8 exists: {'8' in prompt}")
    print(f"Node 8: {prompt.get('8')}")

    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt})
    if r.status_code == 200:
        print('  [OK] ' + str(r.json().get('prompt_id')))
    else:
        try:
            err = r.json()
            print('  [FAIL] ' + str(err))
        except:
            print('  [FAIL] ' + r.text[:200])

asyncio.run(main())