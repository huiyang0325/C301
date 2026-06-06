"""工作流转换测试 - 最终版使用input_order"""
import json, httpx, asyncio

WORKFLOW_DIR = r'E:\咸鱼买工作流\模型和插件，下载后把里面文件夹剪切到压缩包解压后得comfyui文件夹内覆盖即可(1)\ComfyUI-aki-v2\ComfyUI\user\default\workflows'

SKIP_TYPES = {
    'Note', 'Label (rgthree)', 'Fast Groups Bypasser (rgthree)',
    'PrimitiveNode', 'SetNode', 'GetNode'
}
TYPE_MAP = {'Reroute': 'ReroutePrimitive|pysssss'}

async def get_object_info():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get('http://127.0.0.1:8188/object_info')
    return r.json()

def convert_workflow(workflow, available, object_info=None):
    """转换工作流，使用object_info的input_order正确分配widget值"""
    link_map = {}
    for link in workflow.get('links', []):
        if len(link) >= 3:
            link_map[link[0]] = [link[1], link[2]]

    skip_ids = {str(n['id']) for n in workflow['nodes'] if n.get('type') in SKIP_TYPES}

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

        # Get node's input order from object_info
        input_order = []
        is_input_list = False
        if object_info and ct in object_info:
            info = object_info[ct]
            input_order = info.get('input_order', {}).get('required', [])
            is_input_list = info.get('is_input_list', False)

        # Build map: input_name -> widget_value_index
        # Only for inputs that are NOT linked (linked inputs don't consume widgets)
        unlinked_input_order = []
        for inp in node.get('inputs', []):
            name = inp.get('name', '')
            if name == '' and ct == 'ReroutePrimitive|pysssss':
                name = 'value'
            link = inp.get('link')
            if link is not None and link in link_map:
                continue  # Skip linked inputs - they don't use widget values
            unlinked_input_order.append(name)

        # Map widget values to unlinked inputs in order
        input_widget_map = {}
        for i, name in enumerate(unlinked_input_order):
            if i < len(wvs):
                input_widget_map[name] = i

        # Also check if we should use input_order to filter/align widgets
        if input_order and not is_input_list:
            # For non-is_input_list nodes, align unlinked inputs with input_order
            # input_order contains all required inputs in API order
            # unlinked_input_order contains inputs in workflow order
            # We need to map widget values based on position in unlinked_input_order
            pass

        for inp in node.get('inputs', []):
            name = inp.get('name', '')
            if name == '' and ct == 'ReroutePrimitive|pysssss':
                name = 'value'
            link = inp.get('link')
            if link is not None and link in link_map:
                inputs[name] = link_map[link]
            elif name in input_widget_map:
                inputs[name] = wvs[input_widget_map[name]]

        # Clean empty inputs
        for key in list(inputs.keys()):
            if inputs[key] is None or inputs[key] == '':
                del inputs[key]

        # Check for bad links
        has_bad_link = False
        for key, val in inputs.items():
            if isinstance(val, list) and len(val) == 2 and str(val[0]) in skip_ids:
                has_bad_link = True
                break

        prompt[nid] = {'class_type': ct, 'inputs': inputs, '_bad_link': has_bad_link}
    return prompt

def set_text(prompt):
    for nid, data in prompt.items():
        inputs = data.get('inputs', {})
        for key in ['text', 'prompt', 'text_g', 'text_l', 'positive', 'edited_text_widget']:
            if key in inputs and isinstance(inputs[key], str) and len(inputs[key]) > 3:
                inputs[key] = 'a beautiful landscape, high quality'
                return True
    return False

def fix_prompt(prompt):
    for nid, data in prompt.items():
        inputs = data.get('inputs', {})
        for key in list(inputs.keys()):
            val = inputs[key]
            if key == 'filename_prefix' and (val is None or val == ''):
                inputs[key] = 'output'
            if key == 'image' and isinstance(val, str):
                inputs[key] = 'image1.png'
            if key == 'seed' and (val == 'randomize' or not isinstance(val, (int, float))):
                inputs[key] = 0
            if val == '':
                del inputs[key]

async def submit_and_show(prompt, desc):
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt})
    if r.status_code == 200:
        pid = r.json().get('prompt_id', '')
        print('  [OK] ' + str(pid))
        return True
    else:
        try:
            err = r.json()
            details = err.get('error', {}).get('details', '')
            node_errors = err.get('error', {}).get('node_errors', {})
            print('  [FAIL] ' + str(details[:100]))
            if node_errors:
                for nid, e in list(node_errors.items())[:3]:
                    errs = e.get('errors', [{}])
                    msg = (errs[0].get('message', '') if errs else '')[:80]
                    print('    Node ' + str(nid) + ': ' + str(msg))
        except Exception as ex:
            print('  [FAIL] ' + r.text[:100])
        return False

async def main():
    object_info = await get_object_info()
    available = set(object_info.keys())
    print('Available: ' + str(len(available)) + ' nodes\n')

    baseline = {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'Qwen-Rapid-AIO-NSFW-v18.safetensors'}},
        '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': 'test', 'clip': ['1', 1]}},
        '3': {'class_type': 'EmptyLatentImage', 'inputs': {'width': 512, 'height': 512, 'batch_size': 1}},
        '4': {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['2', 0], 'latent_image': ['3', 0], 'seed': 0, 'steps': 1, 'cfg': 1, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1}},
        '5': {'class_type': 'VAEDecode', 'inputs': {'samples': ['4', 0], 'vae': ['1', 2]}},
        '6': {'class_type': 'SaveImage', 'inputs': {'images': ['5', 0], 'filename_prefix': 'test'}},
    }
    print('=== baseline ===')
    await submit_and_show(baseline, 'baseline')

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
        print('\n=== ' + wf_name + ' ===')
        try:
            with open(WORKFLOW_DIR + '/' + wf_name, encoding='utf-8') as f:
                workflow = json.load(f)
            prompt = convert_workflow(workflow, available, object_info)

            # Cascade removal
            removed = True
            while removed:
                removed = False
                bad_ids = [nid for nid, d in prompt.items() if d.get('_bad_link')]
                for nid in bad_ids:
                    prompt.pop(nid, None)
                    removed = True
                if removed:
                    for nid, d in list(prompt.items()):
                        for key, val in list(d.get('inputs', {}).items()):
                            if isinstance(val, list) and len(val) == 2:
                                if str(val[0]) in bad_ids:
                                    prompt.pop(nid, None)
                                    removed = True
                                    break

            for d in prompt.values():
                d.pop('_bad_link', None)

            has_text = set_text(prompt)
            if not has_text:
                print('  [SKIP] no text input')
                results.append((wf_name, 'SKIP'))
            else:
                fix_prompt(prompt)
                ok = await submit_and_show(prompt, wf_name)
                results.append((wf_name, 'OK' if ok else 'FAIL'))
        except Exception as e:
            print('  [ERROR] ' + str(e))
            results.append((wf_name, 'ERROR'))

    print('\n\n=== 汇总 ===')
    ok_count = sum(1 for _, s in results if s == 'OK')
    print('通过: ' + str(ok_count) + '/' + str(len(results)))
    for name, status in results:
        print('  ' + str(status).ljust(8) + ': ' + name)

asyncio.run(main())