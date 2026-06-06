"""测试工作流6 - 手动构建正确的prompt"""
import json, httpx, asyncio

async def main():
    # 基于workflow 6的结构，但简化版
    # 注意：workflow 6是纯文生图（Z-image），不需要输入图片
    prompt = {
        '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'z_image_turbo_bf16.safetensors', 'weight_dtype': 'default'}},
        '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': 'qwen_3_4b.safetensors', 'type': 'qwen_image', 'device': 'default'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'zimage ae.safetensors'}},
        '4': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 720, 'height': 1280, 'batch_size': 1}},
        '5': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['2', 0], 'text': 'a beautiful landscape, high quality'}},
        '6': {'class_type': 'ConditioningZeroOut', 'inputs': {'conditioning': ['5', 0]}},
        '7': {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'positive': ['5', 0], 'negative': ['6', 0], 'latent_image': ['4', 0], 'seed': 0, 'steps': 9, 'cfg': 1, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1}},
        '8': {'class_type': 'VAEDecode', 'inputs': {'samples': ['7', 0], 'vae': ['3', 0]}},
        '9': {'class_type': 'SaveImage', 'inputs': {'images': ['8', 0], 'filename_prefix': 'zimage_test'}},
    }

    print("Submitting Z-image test...")
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