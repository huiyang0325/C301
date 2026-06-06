"""Debug workflow 6"""
import json, httpx, asyncio

WORKFLOW_DIR = r'E:\咸鱼买工作流\模型和插件，下载后把里面文件夹剪切到压缩包解压后得comfyui文件夹内覆盖即可(1)\ComfyUI-aki-v2\ComfyUI\user\default\workflows'

async def main():
    # Get object_info
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get('http://127.0.0.1:8188/object_info')
    object_info = r.json()
    available = set(object_info.keys())

    wf_name = '6-【闲鱼萌宝】Z-image 高清出图.json'
    with open(WORKFLOW_DIR + '/' + wf_name, encoding='utf-8') as f:
        workflow = json.load(f)

    print(f"Workflow has {len(workflow['nodes'])} nodes")

    # Find KSampler node
    for node in workflow['nodes']:
        if node.get('type') == 'KSampler':
            print(f"\nKSampler node {node['id']}:")
            print(f"  widgets_values: {node.get('widgets_values')}")
            print(f"  inputs:")
            for inp in node.get('inputs', []):
                print(f"    {inp['name']}: link={inp.get('link')}")

    # Convert
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

        prompt[nid] = {'class_type': ct, 'inputs': inputs}

    # Print KSampler inputs
    if '4' in prompt:
        print(f"\nConverted KSampler inputs: {prompt['4']['inputs']}")

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

    print(f"\nKSampler after fix_prompt: {prompt.get('4')}")

    # Submit
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt})
    print(f"\nStatus: {r.status_code}")
    if r.status_code == 200:
        print('  [OK] ' + str(r.json().get('prompt_id')))
    else:
        print('  [FAIL] ' + r.text[:300])

asyncio.run(main())
