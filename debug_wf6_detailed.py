"""Debug workflow 6 - detailed trace"""
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

    print("=== Link Map ===")
    link_map = {}
    for link in workflow.get('links', []):
        if len(link) >= 3:
            link_map[link[0]] = [str(link[1]), link[2]]
    print(f"link_map: {link_map}")
    print()

    SKIP_TYPES = {
        'Note', 'Label (rgthree)', 'Fast Groups Bypasser (rgthree)',
        'PrimitiveNode', 'SetNode', 'GetNode'
    }
    TYPE_MAP = {'Reroute': 'ReroutePrimitive|pysssss'}

    skip_ids = {str(n['id']) for n in workflow['nodes'] if n.get('type') in SKIP_TYPES}
    print(f"skip_ids: {skip_ids}")
    print()

    prompt = {}
    for node in workflow['nodes']:
        nid = str(node['id'])
        ct = node.get('type', '')
        ct_mapped = TYPE_MAP.get(ct, ct)
        in_available = ct_mapped in available
        in_skip = nid in skip_ids

        print(f"Node {nid} ({ct}) -> {ct_mapped}: available={in_available}, skip={in_skip}")

        if nid in skip_ids:
            continue
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

        has_bad_link = False
        for key, val in inputs.items():
            if isinstance(val, list) and len(val) == 2 and str(val[0]) in skip_ids:
                has_bad_link = True
                break

        prompt[nid] = {'class_type': ct, 'inputs': inputs, '_bad_link': has_bad_link}
        print(f"  -> Added to prompt: inputs={inputs}")

    print()
    print("=== Cascade Removal ===")
    removed = True
    while removed:
        removed = False
        bad_ids = [nid for nid, d in prompt.items() if d.get('_bad_link')]
        if bad_ids:
            print(f"Removing bad IDs: {bad_ids}")
        for nid in bad_ids:
            prompt.pop(nid, None)
            removed = True
        if removed:
            for nid, d in list(prompt.items()):
                for key, val in list(d.get('inputs', {}).items()):
                    if isinstance(val, list) and len(val) == 2:
                        if str(val[0]) in bad_ids:
                            print(f"  Removing {nid} because it references {val[0]}")
                            prompt.pop(nid, None)
                            removed = True
                            break

    for d in prompt.values():
        d.pop('_bad_link', None)

    print()
    print("=== Final Prompt ===")
    for nid in sorted(prompt.keys(), key=int):
        print(f"  {nid}: {prompt[nid]['class_type']} -> {prompt[nid]['inputs']}")

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

    print()
    print("=== Submitting ===")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt})
    print(f"Status: {r.status_code}")
    if r.status_code != 200:
        print("FAIL:", r.text[:400])
    else:
        print("OK:", r.json().get('prompt_id'))

asyncio.run(main())
