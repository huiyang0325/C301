"""工作流转换测试 - 智能处理GetNode/SetNode/Primitive节点"""
import json, httpx, asyncio

WORKFLOW_DIR = r'E:\咸鱼买工作流\模型和插件，下载后把里面文件夹剪切到压缩包解压后得comfyui文件夹内覆盖即可(1)\ComfyUI-aki-v2\ComfyUI\user\default\workflows'

# 只跳过辅助节点，保留Primitive*类型
SKIP_TYPES = {
    'Reroute', 'Note', 'Label (rgthree)', 'Fast Groups Bypasser (rgthree)',
    'VRAMCleanup', 'RAMCleanup', 'SetNode', 'GetNode'
}
TYPE_MAP = {'Reroute': 'ReroutePrimitive|pysssss'}

async def get_available():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get('http://127.0.0.1:8188/object_info')
    return set(r.json().keys())

def convert_smart(workflow, available):
    """智能转换：跳过GetNode/SetNode，解析Primitive*节点，追踪变量链"""
    link_map = {}
    for link in workflow.get('links', []):
        if len(link) >= 3:
            link_map[link[0]] = [link[1], link[2]]

    skip_ids = {str(n['id']) for n in workflow['nodes'] if n.get('type') in SKIP_TYPES}
    node_by_id = {n['id']: n for n in workflow['nodes']}

    # 建立变量名 -> 源节点的映射 (SetNode.var_name -> source node)
    var_to_source = {}
    for node in workflow['nodes']:
        if node.get('type') == 'SetNode':
            wvs = node.get('widgets_values', [])
            if not wvs:
                continue
            var_name = wvs[0]
            for inp in node.get('inputs', []):
                link = inp.get('link')
                if link is not None and link in link_map:
                    src_id, src_slot = link_map[link]
                    if str(src_id) not in skip_ids:
                        var_to_source[var_name] = [src_id, src_slot]
                        break

    # 解析GetNode链接：resolve link_map中的GetNode引用
    resolved_links = {}
    for link_id, (src_id, src_slot) in link_map.items():
        src_str = str(src_id)
        if src_str in skip_ids:
            src_node = node_by_id.get(src_id)
            if src_node and src_node.get('type') == 'GetNode':
                wvs = src_node.get('widgets_values', [])
                if wvs and wvs[0] in var_to_source:
                    resolved_links[link_id] = var_to_source[wvs[0]]
        else:
            resolved_links[link_id] = [src_id, src_slot]

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
        if not isinstance(wvs, list):
            wvs = []
        idx = 0
        for inp in node.get('inputs', []):
            name = inp.get('name', '')
            link = inp.get('link')
            if link is not None and link in resolved_links:
                inputs[name] = resolved_links[link]
            elif idx < len(wvs):
                inputs[name] = wvs[idx]
                idx += 1

        for key in list(inputs.keys()):
            if inputs[key] is None or inputs[key] == '':
                del inputs[key]

        prompt[nid] = {'class_type': ct, 'inputs': inputs}
    return prompt

def remove_bad_refs(prompt):
    """移除引用了不存在节点的输入"""
    while True:
        bad_nodes = set()
        for nid, data in prompt.items():
            for val in data.get('inputs', {}).values():
                if isinstance(val, list) and len(val) == 2:
                    if str(val[0]) not in prompt:
                        bad_nodes.add(nid)
                        break
        if bad_nodes:
            for nid in bad_nodes:
                prompt.pop(nid, None)
        else:
            break
    return prompt

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

    workflows = [
        '10-11-【闲鱼萌宝】LTX-2.3 文&图生视频优化版.json',
    ]

    for wf_name in workflows:
        print(f'\n=== {wf_name} ===')
        try:
            with open(f'{WORKFLOW_DIR}/{wf_name}', encoding='utf-8') as f:
                workflow = json.load(f)
            prompt = convert_smart(workflow, available)
            remove_bad_refs(prompt)
            print(f'  Nodes: {len(prompt)}')
            await submit(prompt, wf_name)
        except Exception as e:
            print(f'  [ERROR] {e}')

asyncio.run(main())
