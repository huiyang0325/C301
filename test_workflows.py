"""工作流转换测试 - 完整版"""
import json, httpx, asyncio

WORKFLOW_DIR = r'E:\咸鱼买工作流\模型和插件，下载后把里面文件夹剪切到压缩包解压后得comfyui文件夹内覆盖即可(1)\ComfyUI-aki-v2\ComfyUI\user\default\workflows'

TYPE_MAP = {'Reroute': 'ReroutePrimitive|pysssss'}
# 只跳过真正的辅助节点，保留Reroute和其他功能性节点
SKIP_TYPES = {
    'Note', 'Label (rgthree)', 'Fast Groups Bypasser (rgthree)',
    'PrimitiveNode', 'SetNode', 'GetNode'
}

async def get_available():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get('http://127.0.0.1:8188/object_info')
    return set(r.json().keys())

def convert(workflow, available, object_info=None):
    """转换工作流：保留Reroute，级联删除引用跳过节点的节点，使用input_order分配widget值"""
    link_map = {}
    for link in workflow.get('links', []):
        if len(link) >= 3:
            link_map[link[0]] = [link[1], link[2]]

    skip_ids = {str(n['id']) for n in workflow['nodes'] if n.get('type') in SKIP_TYPES}

    prompt = {}
    for n in workflow['nodes']:
        nid = str(n['id'])
        if nid in skip_ids:
            continue  # Skip nodes in SKIP_TYPES
        ct = n.get('type', '')
        ct = TYPE_MAP.get(ct, ct)

        inputs = {}
        wvs = n.get('widgets_values') or []
        if not isinstance(wvs, list):
            wvs = []

        # 如果有object_info且节点是is_input_list类型，使用input_order分配widget值
        widgets_values_idx = 0
        input_name_to_wvs_idx = {}
        if object_info and ct in object_info:
            node_info = object_info[ct]
            input_order = node_info.get('input_order', {})
            is_input_list = node_info.get('is_input_list', False)
            if input_order and is_input_list:
                # For is_input_list nodes, wvs are in input_order sequence
                required_order = input_order.get('required', [])
                for name in required_order:
                    if widgets_values_idx < len(wvs):
                        input_name_to_wvs_idx[name] = widgets_values_idx
                        widgets_values_idx += 1
        else:
            # For non-is_input_list nodes, need to match wvs to actual API-required inputs
            # This requires knowing the API input order for this node type
            # Fallback: map by checking which inputs are not linked
            pass

        for inp in n.get('inputs', []):
            name = inp.get('name', '')
            # Reroute nodes have empty input name in workflow file, but API expects 'value'
            if name == '' and ct == 'ReroutePrimitive|pysssss':
                name = 'value'
            link = inp.get('link')
            if link is not None and link in link_map:
                inputs[name] = link_map[link]
            elif name in input_name_to_wvs_idx:
                inputs[name] = wvs[input_name_to_wvs_idx[name]]
            elif widgets_values_idx < len(wvs):
                inputs[name] = wvs[widgets_values_idx]
                widgets_values_idx += 1

        # 清理空值
        for key in list(inputs.keys()):
            if inputs[key] is None or inputs[key] == '':
                del inputs[key]

        prompt[nid] = {'class_type': ct, 'inputs': inputs}

    # Cascade removal
    bad_ids = set(skip_ids)
    changed = True
    while changed:
        changed = False
        to_remove = set()
        for nid, data in prompt.items():
            for val in data.get('inputs', {}).values():
                if isinstance(val, list) and len(val) == 2:
                    if str(val[0]) in bad_ids:
                        to_remove.add(nid)
                        break
        if to_remove:
            for nid in to_remove:
                prompt.pop(nid, None)
            bad_ids.update(to_remove)
            changed = True

    return prompt

def fix_prompt(prompt):
    """修复常见问题"""
    for nid, data in list(prompt.items()):
        ct = data.get('class_type', '')
        inputs = data.get('inputs', {})

        # SaveImage需要filename_prefix
        if ct == 'SaveImage' and 'filename_prefix' not in inputs:
            inputs['filename_prefix'] = 'output'

        # LoadImage替换为测试图片
        if ct == 'LoadImage' and 'image' in inputs:
            inputs['image'] = 'image1.png'

        # KSampler的seed如果是randomize则替换为0
        if ct == 'KSampler' and 'seed' in inputs:
            if inputs['seed'] == 'randomize' or not isinstance(inputs['seed'], (int, float)):
                inputs['seed'] = 0

        # 清理空字符串
        for key in list(inputs.keys()):
            if inputs[key] == '' or inputs[key] is None:
                del inputs[key]

        data['inputs'] = inputs

def set_text(prompt):
    """替换文本输入为测试文本"""
    for nid, data in prompt.items():
        inputs = data.get('inputs', {})
        for key in ['text', 'prompt', 'text_g', 'text_l', 'positive', 'edited_text_widget']:
            if key in inputs and isinstance(inputs[key], str) and len(inputs[key]) > 3:
                inputs[key] = 'a beautiful landscape, high quality'
                return True
    return False

async def submit(prompt, desc=''):
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt})
    if r.status_code == 200:
        print(f'  [OK] {r.json().get("prompt_id")}')
        return True
    else:
        try:
            err = r.json()
            details = err.get('error', {}).get('details', '')[:80]
            ne = err.get('error', {}).get('node_errors', {})
            print(f'  [FAIL] {details}')
            for nid, e in list(ne.items())[:2]:
                errs = e.get('errors', [{}])
                msg = (errs[0].get('message', '') if errs else '')[:80]
                print(f'    Node {nid}: {msg}')
        except:
            print(f'  [FAIL] {r.text[:100]}')
        return False

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get('http://127.0.0.1:8188/object_info')
    object_info = r.json()
    available = set(object_info.keys())
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
    print('=== baseline ===')
    await submit(baseline, 'baseline')

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
            prompt = convert(workflow, available, object_info)
            fix_prompt(prompt)
            has_text = set_text(prompt)
            if not has_text:
                print('  [SKIP] no text input')
                results.append((wf_name, 'SKIP'))
            else:
                ok = await submit(prompt, wf_name)
                results.append((wf_name, 'OK' if ok else 'FAIL'))
        except Exception as e:
            print(f'  [ERROR] {e}')
            results.append((wf_name, 'ERROR'))

    print(f'\n\n=== 汇总 ===')
    ok_count = sum(1 for _, s in results if s == 'OK')
    print(f'通过: {ok_count}/{len(results)}')
    for name, status in results:
        print(f'  {status.ljust(8)}: {name}')

asyncio.run(main())