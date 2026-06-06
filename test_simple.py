"""简化版工作流测试：只提取核心生成节点，跳过辅助节点"""
import json, httpx, asyncio

WORKFLOW_DIR = r'E:\咸鱼买工作流\模型和插件，下载后把里面文件夹剪切到压缩包解压后得comfyui文件夹内覆盖即可(1)\ComfyUI-aki-v2\ComfyUI\user\default\workflows'

SKIP_TYPES = {
    'Reroute', 'Note', 'Label (rgthree)', 'Fast Groups Bypasser (rgthree)',
    'VRAMCleanup', 'RAMCleanup', 'PrimitiveNode', 'SetNode', 'GetNode'
}
TYPE_MAP = {'Reroute': 'ReroutePrimitive|pysssss'}

# 可用的文本输入类型
TEXT_INPUT_TYPES = {'CLIPTextEncode', 'CR Prompt Text', 'TextEncodeQwenImageEditPlus', 'CLIPTextEncodeSDXLI',
                   'SDXL Power Prompt - Positive', 'SDXL Power Prompt - Simple / Negative',
                   'Power Prompt', 'Power Prompt - Simple', 'CR Text', 'easy promptList'}

async def get_available():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get('http://127.0.0.1:8188/object_info')
    return set(r.json().keys())

def convert_minimal(workflow, available):
    """只提取核心节点，跳过所有辅助节点"""
    link_map = {}
    for link in workflow.get('links', []):
        if len(link) >= 3:
            link_map[link[0]] = [link[1], link[2]]

    # 跳过这些类型
    skip_ids = {str(n['id']) for n in workflow['nodes'] if n.get('type') in SKIP_TYPES}

    # 过滤 link_map
    filtered = {k: v for k, v in link_map.items() if str(v[0]) not in skip_ids}

    prompt = {}
    for node in workflow['nodes']:
        nid = str(node['id'])
        if nid in skip_ids:
            continue
        ct = node.get('type', '')
        ct = TYPE_MAP.get(ct, ct)
        if ct not in available:
            continue

        inputs = {}
        wvs = node.get('widgets_values') or []
        idx = 0
        # widgets_values 可能是 list 或 dict（如 VHS_VideoCombine 是 dict）
        if not isinstance(wvs, list):
            wvs = []
        for inp in node.get('inputs', []):
            name = inp.get('name', '')
            link = inp.get('link')
            if link is not None and link in filtered:
                inputs[name] = filtered[link]
            elif idx < len(wvs):
                inputs[name] = wvs[idx]
                idx += 1

        prompt[nid] = {'class_type': ct, 'inputs': inputs}
    return prompt

def find_and_set_text(prompt):
    """找一个文本输入并设置提示词"""
    for nid, data in prompt.items():
        if data.get('class_type') not in TEXT_INPUT_TYPES:
            continue
        inputs = data.get('inputs', {})
        for key in ['text', 'prompt', 'positive', 'text_g', 'text_l']:
            if key in inputs and isinstance(inputs[key], str) and len(inputs[key]) > 3:
                inputs[key] = 'a beautiful landscape, high quality'
                return True
    return False

async def submit(prompt, desc=''):
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt})
    if r.status_code == 200:
        print(f'  [OK] {desc} -> {r.json().get("prompt_id")}')
        return True
    else:
        msg = r.text[:150].replace('\n', ' ')
        print(f'  [FAIL] {desc}: {msg}')
        return False

async def main():
    available = await get_available()
    print(f'Available: {len(available)} nodes\n')

    # 基线测试
    baseline = {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'Qwen-Rapid-AIO-NSFW-v18.safetensors'}},
        '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': 'test', 'clip': ['1', 1]}},
        '3': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 512, 'height': 512, 'batch_size': 1}},
        '4': {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['2', 0], 'latent_image': ['3', 0], 'seed': 0, 'steps': 1, 'cfg': 1, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1}},
        '5': {'class_type': 'VAEDecode', 'inputs': {'samples': ['4', 0], 'vae': ['1', 2]}},
        '6': {'class_type': 'SaveImage', 'inputs': {'images': ['5', 0], 'filename_prefix': 'test'}},
    }
    await submit(baseline, 'baseline')

    # 只测试工作流2（之前失败说是缺少edited_text，这是一个明确错误）
    print('\n=== 工作流2详细调试 ===')
    wf2 = '2-【闲鱼萌宝】2511单图出分镜图.json'
    with open(f'{WORKFLOW_DIR}/{wf2}', encoding='utf-8') as f:
        workflow = json.load(f)

    link_map = {}
    for link in workflow['links']:
        if len(link) >= 3:
            link_map[link[0]] = [link[1], link[2]]

    skip_ids = {str(n['id']) for n in workflow['nodes'] if n.get('type') in SKIP_TYPES}
    filtered = {k: v for k, v in link_map.items() if str(v[0]) not in skip_ids}

    prompt = {}
    for node in workflow['nodes']:
        nid = str(node['id'])
        if nid in skip_ids:
            continue
        ct = node.get('type', '')
        ct = TYPE_MAP.get(ct, ct)
        if ct not in available:
            continue

        inputs = {}
        wvs = node.get('widgets_values') or []
        idx = 0
        # widgets_values 可能是 list 或 dict（如 VHS_VideoCombine 是 dict）
        if not isinstance(wvs, list):
            wvs = []
        for inp in node.get('inputs', []):
            name = inp.get('name', '')
            link = inp.get('link')
            if link is not None and link in filtered:
                inputs[name] = filtered[link]
            elif idx < len(wvs):
                inputs[name] = wvs[idx]
                idx += 1

        prompt[nid] = {'class_type': ct, 'inputs': inputs}

    # 找缺失的输入
    missing = {}
    for nid, data in prompt.items():
        for name, val in data.get('inputs', {}).items():
            if val is None or (isinstance(val, list) and val[0] is None):
                missing[f'{nid}.{name}'] = val

    if missing:
        print(f'  缺失的输入: {list(missing.keys())[:10]}')

    # 尝试只提交核心采样链
    core_prompt = {}
    for nid, data in prompt.items():
        ct = data['class_type']
        if ct in ('CLIPTextEncode', 'CheckpointLoaderSimple', 'EmptyLatentImage', 'KSampler', 'VAEDecode', 'SaveImage'):
            core_prompt[nid] = data

    if core_prompt:
        print(f'  核心节点数: {len(core_prompt)}')
        # 找一个CLIPTextEncode并设置文本
        for nid, data in core_prompt.items():
            if data['class_type'] == 'CLIPTextEncode' and 'text' in data['inputs']:
                data['inputs']['text'] = 'beautiful landscape'
                print(f'  设置文本在节点 {nid}')
                break
        await submit(core_prompt, 'core_only')

    workflows = [
        '1-【闲鱼萌宝】2511单图编辑 .json',
        '2-【闲鱼萌宝】2511单图出分镜图.json',
        '3-【闲鱼萌宝】2511双图编辑+姿态迁移 .json',
        '4-【闲鱼萌宝】2511三图编辑.json',
        '5-【闲鱼萌宝】单图可视化出多角度.json',
        '6-【闲鱼萌宝】Z-image 高清出图.json',
        '7-【闲鱼萌宝】自动反推洗图+sd放大.json',
        '8-【闲鱼萌宝】图片sd放大.json',
        '9-【闲鱼萌宝】双采样超多细节文生图.json',
        '10-11-【闲鱼萌宝】LTX-2.3 文&图生视频优化版.json',
        '12-【闲鱼萌宝】LTX2.3-首尾帧视频优化版.json',
        '13-【闲鱼萌宝】LTX 2.3单人对口型工作流 .json',
        '14-【闲鱼萌宝】LTX2.3双人对话对口型 .json',
        '15-【闲鱼萌宝】LTX2.3多图参考引导生成工作流 .json',
    ]

    results = []
    for wf_name in workflows:
        print(f'\n=== {wf_name} ===')
        try:
            with open(f'{WORKFLOW_DIR}/{wf_name}', encoding='utf-8') as f:
                workflow = json.load(f)
            prompt = convert_minimal(workflow, available)
            if not find_and_set_text(prompt):
                print(f'  [SKIP] 无文本输入')
                results.append((wf_name, 'SKIP_NO_TEXT'))
                continue
            ok = await submit(prompt, wf_name)
            results.append((wf_name, 'OK' if ok else 'FAIL'))
        except Exception as e:
            print(f'  [ERROR] {e}')
            results.append((wf_name, f'ERROR: {e}'))

    print('\n\n=== 汇总 ===')
    for name, status in results:
        print(f'{status:12s} : {name}')

asyncio.run(main())