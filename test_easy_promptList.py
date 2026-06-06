"""测试easy promptList节点"""
import json, httpx, asyncio

async def main():
    # Test if easy promptList node works
    prompt = {
        '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'z_image_turbo_bf16.safetensors', 'weight_dtype': 'default'}},
        '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': 'qwen_3_4b.safetensors', 'type': 'qwen_image', 'device': 'default'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'zimage ae.safetensors'}},
        '4': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 720, 'height': 1280, 'batch_size': 1}},
        '5': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['2', 0], 'text': 'a beautiful landscape'}},
        '11': {'class_type': 'easy promptList', 'inputs': {'optional_prompt_list': 'test1', 'prompt_1': 'test2', 'prompt_2': 'test3', 'prompt_3': 'test4', 'prompt_4': 'test5'}},
        '6': {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'positive': ['5', 0], 'negative': ['5', 0], 'latent_image': ['4', 0], 'seed': 0, 'steps': 9, 'cfg': 1, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1}},
        '7': {'class_type': 'VAEDecode', 'inputs': {'samples': ['6', 0], 'vae': ['3', 0]}},
        '8': {'class_type': 'SaveImage', 'inputs': {'images': ['7', 0], 'filename_prefix': 'test'}},
    }

    print("Submitting with easy promptList...")
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