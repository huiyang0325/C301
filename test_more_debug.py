"""Debug workflow 6 - without node 11"""
import json, httpx, asyncio

async def main():
    # Without node 11
    prompt = {
        '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'z_image_turbo_bf16.safetensors', 'weight_dtype': 'default'}},
        '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': 'qwen_3_4b.safetensors', 'type': 'qwen_image', 'device': 'default'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'zimage ae.safetensors'}},
        '4': {'class_type': 'KSampler', 'inputs': {'model': [1, 0], 'positive': [5, 0], 'negative': [6, 0], 'latent_image': [7, 0], 'seed': 700127413627084, 'steps': 9, 'cfg': 9, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1.0}},
        '5': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': [2, 0], 'text': 'test'}},
        '6': {'class_type': 'ConditioningZeroOut', 'inputs': {'conditioning': [5, 0]}},
        '7': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 720, 'height': 1280, 'batch_size': 1}},
        '8': {'class_type': 'VAEDecode', 'inputs': {'samples': [4, 0], 'vae': [3, 0]}},
        '20': {'class_type': 'SaveImage', 'inputs': {'images': [8, 0], 'filename_prefix': 'test'}},
    }

    print("Test 1: Without node 11")
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

    # With node 11 but scheduler='simple'
    prompt['11'] = {'class_type': 'easy promptList', 'inputs': {'optional_prompt_list': 't1', 'prompt_1': 't2', 'prompt_2': 't3', 'prompt_3': 't4', 'prompt_4': 't5'}}
    print("\nTest 2: With node 11, scheduler=simple")
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

    # Change node IDs to not start with 1
    prompt2 = {
        'a1': prompt['1'],
        'a2': prompt['2'],
        'a3': prompt['3'],
        'a4': prompt['4'],
        'a5': prompt['5'],
        'a6': prompt['6'],
        'a7': prompt['7'],
        'a8': prompt['8'],
        'a11': prompt['11'],
        'a20': prompt['20'],
    }
    # Fix references
    prompt2['a4']['inputs']['model'] = ['a1', 0]
    prompt2['a4']['inputs']['positive'] = ['a5', 0]
    prompt2['a4']['inputs']['negative'] = ['a6', 0]
    prompt2['a4']['inputs']['latent_image'] = ['a7', 0]
    prompt2['a5']['inputs']['clip'] = ['a2', 0]
    prompt2['a6']['inputs']['conditioning'] = ['a5', 0]
    prompt2['a8']['inputs']['samples'] = ['a4', 0]
    prompt2['a8']['inputs']['vae'] = ['a3', 0]
    prompt2['a20']['inputs']['images'] = ['a8', 0]

    print("\nTest 3: With letter node IDs")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt2})
    if r.status_code == 200:
        print('  [OK] ' + str(r.json().get('prompt_id')))
    else:
        try:
            err = r.json()
            print('  [FAIL] ' + str(err))
        except:
            print('  [FAIL] ' + r.text[:200])

asyncio.run(main())