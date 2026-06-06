"""调试workflow 6 KSampler值"""
import json, httpx, asyncio

WORKFLOW_DIR = r'E:\咸鱼买工作流\模型和插件，下载后把里面文件夹剪切到压缩包解压后得comfyui文件夹内覆盖即可(1)\ComfyUI-aki-v2\ComfyUI\user\default\workflows'

async def main():
    wf_name = '6-【闲鱼萌宝】Z-image 高清出图.json'
    with open(WORKFLOW_DIR + '/' + wf_name, encoding='utf-8') as f:
        workflow = json.load(f)

    # Find KSampler node
    for n in workflow['nodes']:
        if n.get('type') == 'KSampler':
            print(f"KSampler node: id={n['id']}")
            print(f"  widgets_values: {n.get('widgets_values')}")
            print(f"  inputs: {n.get('inputs')}")

    # Get object_info for KSampler
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get('http://127.0.0.1:8188/object_info')
    info = r.json()

    ksampler_info = info.get('KSampler', {})
    print(f"\nKSampler input_order: {ksampler_info.get('input_order')}")
    print(f"KSampler is_input_list: {ksampler_info.get('is_input_list')}")

    required = ksampler_info.get('input', {}).get('required', {})
    print(f"KSampler required inputs: {list(required.keys())}")

asyncio.run(main())