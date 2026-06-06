"""Debug workflow 6 - check submission"""
import json, httpx, asyncio

async def main():
    # Test with correct scheduler and string node IDs
    prompt = {
        '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'z_image_turbo_bf16.safetensors', 'weight_dtype': 'default'}},
        '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': 'qwen_3_4b.safetensors', 'type': 'qwen_image', 'device': 'default'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'zimage ae.safetensors'}},
        '4': {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'positive': ['5', 0], 'negative': ['6', 0], 'latent_image': ['7', 0], 'seed': 0, 'steps': 9, 'cfg': 1, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1}},
        '5': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['2', 0], 'text': 'test'}},
        '6': {'class_type': 'ConditioningZeroOut', 'inputs': {'conditioning': ['5', 0]}},
        '7': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 720, 'height': 1280, 'batch_size': 1}},
        '8': {'class_type': 'VAEDecode', 'inputs': {'samples': ['4', 0], 'vae': ['3', 0]}},
        '20': {'class_type': 'SaveImage', 'inputs': {'images': ['8', 0], 'filename_prefix': 'test'}},
    }

    print("Test A: With string node IDs and correct scheduler")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt})
    if r.status_code == 200:
        print('  [OK] ' + str(r.json().get('prompt_id')))
    else:
        try:
            err = r.json()
            print('  [FAIL] ' + str(err.get('error', {}).get('details', '')))
            ne = err.get('node_errors', {})
            for nid, e in list(ne.items())[:2]:
                print(f"    Node {nid}: {e.get('errors', [{}])[0].get('details', '')[:100]}")
        except:
            print('  [FAIL] ' + r.text[:100])

    # Test with integer node IDs
    prompt2 = {
        1: {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'z_image_turbo_bf16.safetensors', 'weight_dtype': 'default'}},
        2: {'class_type': 'CLIPLoader', 'inputs': {'clip_name': 'qwen_3_4b.safetensors', 'type': 'qwen_image', 'device': 'default'}},
        3: {'class_type': 'VAELoader', 'inputs': {'vae_name': 'zimage ae.safetensors'}},
        4: {'class_type': 'KSampler', 'inputs': {'model': [1, 0], 'positive': [5, 0], 'negative': [6, 0], 'latent_image': [7, 0], 'seed': 0, 'steps': 9, 'cfg': 1, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1}},
        5: {'class_type': 'CLIPTextEncode', 'inputs': {'clip': [2, 0], 'text': 'test'}},
        6: {'class_type': 'ConditioningZeroOut', 'inputs': {'conditioning': [5, 0]}},
        7: {'class_type': 'EmptyLatentImage', 'inputs': {'width': 720, 'height': 1280, 'batch_size': 1}},
        8: {'class_type': 'VAEDecode', 'inputs': {'samples': [4, 0], 'vae': [3, 0]}},
        20: {'class_type': 'SaveImage', 'inputs': {'images': [8, 0], 'filename_prefix': 'test'}},
    }

    print("\nTest B: With integer node IDs")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt2})
    if r.status_code == 200:
        print('  [OK] ' + str(r.json().get('prompt_id')))
    else:
        try:
            err = r.json()
            print('  [FAIL] ' + str(err.get('error', {}).get('details', '')))
        except:
            print('  [FAIL] ' + r.text[:100])

asyncio.run(main())