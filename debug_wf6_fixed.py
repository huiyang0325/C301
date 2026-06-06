"""Debug workflow 6 with correct mapping"""
import json, httpx, asyncio

WORKFLOW_DIR = r'E:\咸鱼买工作流\模型和插件，下载后把里面文件夹剪切到压缩包解压后得comfyui文件夹内覆盖即可(1)\ComfyUI-aki-v2\ComfyUI\user\default\workflows'

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get('http://127.0.0.1:8188/object_info')
    object_info = r.json()
    available = set(object_info.keys())

    wf_name = '6-【闲鱼萌宝】Z-image 高清出图.json'
    with open(WORKFLOW_DIR + '/' + wf_name, encoding='utf-8') as f:
        workflow = json.load(f)

    SKIP_TYPES = {
        'Note', 'Label (rgthree)', 'Fast Groups Bypasser (rgthree)',
        'PrimitiveNode', 'SetNode', 'GetNode'
    }
    TYPE_MAP = {'Reroute': 'ReroutePrimitive|pysssss'}

    link_map = {}
    for link in workflow.get('links', []):
        if len(link) >= 3:
            link_map[link[0]] = [str(link[1]), link[2]]

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

        # Get input_order from object_info
        input_order = []
        if object_info and ct in object_info:
            input_order = object_info[ct].get('input_order', {}).get('required', [])

        # Build map: input_name -> wvs_index using input_order
        # wvs[i] corresponds to input_order[i]
        input_widget_map = {}
        for i, name in enumerate(input_order):
            if i < len(wvs):
                input_widget_map[name] = i

        for inp in node.get('inputs', []):
            name = inp.get('name', '')
            if name == '' and ct == 'ReroutePrimitive|pysssss':
                name = 'value'
            link = inp.get('link')
            if link is not None and link in link_map:
                inputs[name] = link_map[link]
            elif name in input_widget_map:
                inputs[name] = wvs[input_widget_map[name]]

        for key in list(inputs.keys()):
            if inputs[key] is None or inputs[key] == '':
                del inputs[key]

        has_bad_link = False
        for key, val in inputs.items():
            if isinstance(val, list) and len(val) == 2 and str(val[0]) in skip_ids:
                has_bad_link = True
                break

        prompt[nid] = {'class_type': ct, 'inputs': inputs, '_bad_link': has_bad_link}

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

    print(f"Converted {len(prompt)} nodes")

    if '4' in prompt:
        print(f"KSampler inputs: {prompt['4']['inputs']}")

    # Set text
    for nid, data in prompt.items():
        inputs = data.get('inputs', {})
        for key in ['text', 'prompt', 'text_g', 'text_l', 'positive', 'edited_text_widget']:
            if key in inputs and isinstance(inputs[key], str) and len(inputs[key]) > 3:
                inputs[key] = 'a beautiful landscape, high quality'

    # Fix prompt
    for nid, data in prompt.items():
        inputs = data.get('inputs', {})
        ct = data.get('class_type', '')
        for key in list(inputs.keys()):
            val = inputs[key]
            if key == 'filename_prefix' and (val is None or val == ''):
                inputs[key] = 'output'
            if key == 'image' and isinstance(val, str):
                inputs[key] = 'image1.png'
            if key == 'seed' and (val == 'randomize' or not isinstance(val, (int, float))):
                inputs[key] = 0
            if ct == 'TextEncodeQwenImageEditPlus' and key == 'prompt' and 'edited_text_widget' not in inputs:
                inputs['edited_text_widget'] = ''
            if key == 'frame_rate' and (val is None or val == ''):
                inputs[key] = 24
            if val == '':
                del inputs[key]

    print(f"KSampler after fix: {prompt.get('4')}")

    # Submit
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt})
    print(f"\nStatus: {r.status_code}")
    if r.status_code == 200:
        print('  [OK] ' + str(r.json().get('prompt_id')))
    else:
        print('  [FAIL] ' + r.text[:300])

asyncio.run(main())
