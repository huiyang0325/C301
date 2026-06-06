"""调试workflow 6 - 检查转换后的prompt"""
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

        node_input_order = []
        if object_info and ct in object_info:
            input_schema = object_info[ct].get('input', {})
            required = input_schema.get('required', {})
            optional = input_schema.get('optional', {})
            node_input_order = list(required.keys()) + list(optional.keys())

        input_widget_map = {}
        if node_input_order and wvs:
            wvs_idx = 0
            for inp in node.get('inputs', []):
                name = inp.get('name', '')
                if name == '' and ct == 'ReroutePrimitive|pysssss':
                    name = 'value'
                link = inp.get('link')
                if link is not None and link in link_map:
                    continue
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

async def main():
    object_info = await get_object_info()
    available = set(object_info.keys())

    wf_name = '6-【闲鱼萌宝】Z-image 高清出图.json'
    print('\n=== ' + wf_name + ' ===')
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

    fix_prompt(prompt)

    print("\nConverted prompt:")
    for nid in sorted(prompt.keys(), key=int):
        print(f"  {nid}: {prompt[nid]}")

    # Check object_info for VAEDecode
    print("\nVAEDecode object_info:")
    if 'VAEDecode' in object_info:
        print(f"  {object_info['VAEDecode']}")
    else:
        print("  Not found!")

    # Check if VAELoader output is correct
    print("\nNode 3 (VAELoader) output check:")
    if '3' in prompt:
        print(f"  {prompt['3']}")

    print("\nNode 8 (VAEDecode) inputs check:")
    if '8' in prompt:
        print(f"  inputs: {prompt['8'].get('inputs')}")
        vae_input = prompt['8'].get('inputs', {}).get('vae')
        print(f"  vae input: {vae_input}, type: {type(vae_input)}")
        if isinstance(vae_input, list) and len(vae_input) == 2:
            ref_node = str(vae_input[0])
            print(f"  references node {ref_node}, which exists: {ref_node in prompt}")

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