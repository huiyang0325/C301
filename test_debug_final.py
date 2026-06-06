"""Debug workflow 6 conversion with print"""
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

        input_order = []
        is_input_list = False
        if object_info and ct in object_info:
            info = object_info[ct]
            input_order = info.get('input_order', {}).get('required', [])
            is_input_list = info.get('is_input_list', False)

        unlinked_inputs = []
        for inp in node.get('inputs', []):
            name = inp.get('name', '')
            if name == '' and ct == 'ReroutePrimitive|pysssss':
                name = 'value'
            link = inp.get('link')
            if link is not None and link in link_map:
                continue
            unlinked_inputs.append(name)

        input_widget_map = {}
        wvs_idx = 0
        for name in unlinked_inputs:
            if wvs_idx < len(wvs):
                input_widget_map[name] = wvs_idx
                wvs_idx += 1

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
            # Fix KSampler parameters - they might be in wrong format
            if nid == '4' or data.get('class_type') == 'KSampler':
                if key == 'seed' and (val == 'randomize' or not isinstance(val, (int, float))):
                    inputs[key] = 0
                if key == 'steps' and (val == 'randomize' or not isinstance(val, int)):
                    inputs[key] = 9  # Default steps
                if key == 'sampler_name' and not isinstance(val, str):
                    inputs[key] = 'euler'  # Default sampler
                if key == 'scheduler' and not isinstance(val, str):
                    inputs[key] = 'simple'  # Default scheduler
                if key == 'denoise' and not isinstance(val, float):
                    inputs[key] = 1.0  # Default denoise
            if val == '':
                del inputs[key]

async def main():
    object_info = await get_object_info()
    available = set(object_info.keys())

    wf_name = '6-【闲鱼萌宝】Z-image 高清出图.json'
    print('\n=== ' + wf_name + ' ===')
    with open(WORKFLOW_DIR + '/' + wf_name, encoding='utf-8') as f:
        workflow = json.load(f)

    print(f"Workflow has {len(workflow['nodes'])} nodes")
    print(f"Skip IDs would be: {SKIP_TYPES}")

    prompt = convert_workflow(workflow, available, object_info)
    print(f"\nAfter convert_workflow: {len(prompt)} nodes")

    # Cascade removal
    removed = True
    while removed:
        removed = False
        bad_ids = [nid for nid, d in prompt.items() if d.get('_bad_link')]
        if bad_ids:
            print(f"Removing bad nodes: {bad_ids}")
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

    print(f"After cascade removal: {len(prompt)} nodes")
    for nid in sorted(prompt.keys(), key=int):
        print(f"  {nid}: {prompt[nid].get('class_type')}")

    set_text(prompt)
    fix_prompt(prompt)

    # Print node 4 (KSampler) to verify fix_prompt worked
    if '4' in prompt:
        print(f"\nNode 4 after fix_prompt: {prompt['4']}")

    # Submit
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt})
    if r.status_code == 200:
        print('\n  [OK] ' + str(r.json().get('prompt_id')))
    else:
        try:
            err = r.json()
            print('\n  [FAIL] ' + str(err))
        except:
            print('\n  [FAIL] ' + r.text[:200])

asyncio.run(main())