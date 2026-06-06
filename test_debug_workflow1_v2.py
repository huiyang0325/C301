"""调试工作流1 - 检查提交的内容"""
import json, httpx, asyncio

WORKFLOW_DIR = r'E:\咸鱼买工作流\模型和插件，下载后把里面文件夹剪切到压缩包解压后得comfyui文件夹内覆盖即可(1)\ComfyUI-aki-v2\ComfyUI\user\default\workflows'

SKIP_TYPES = {
    'Note', 'Label (rgthree)', 'Fast Groups Bypasser (rgthree)',
    'VRAMCleanup', 'RAMCleanup', 'PrimitiveNode', 'SetNode', 'GetNode'
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

async def main():
    object_info = await get_object_info()
    available = set(object_info.keys())
    print('Available: ' + str(len(available)) + ' nodes\n')

    wf_name = '1-【闲鱼萌宝】2511单图编辑 .json'
    print('\n=== ' + wf_name + ' ===')
    with open(WORKFLOW_DIR + '/' + wf_name, encoding='utf-8') as f:
        workflow = json.load(f)

    prompt = convert_workflow(workflow, available, object_info)

    # Cascade removal
    iteration = 0
    while True:
        iteration += 1
        bad_ids = [nid for nid, d in prompt.items() if d.get('_bad_link')]
        if not bad_ids:
            break

        print(f"Iteration {iteration}: removing {bad_ids}")

        for nid in bad_ids:
            prompt.pop(nid, None)

        newly_bad = []
        for nid, d in prompt.items():
            for key, val in list(d.get('inputs', {}).items()):
                if isinstance(val, list) and len(val) == 2:
                    if str(val[0]) in bad_ids:
                        newly_bad.append(nid)
                        break

        for nid in newly_bad:
            if nid in prompt:
                prompt[nid]['_bad_link'] = True

    for d in prompt.values():
        d.pop('_bad_link', None)

    print(f"\nAfter cascade removal: {len(prompt)} nodes")

    has_text = set_text(prompt)
    fix_prompt(prompt)

    # Print the actual JSON we're sending
    print("\nJSON being sent:")
    print(json.dumps({'prompt': prompt}, indent=2, ensure_ascii=False)[:2000])

    # Submit
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt})
    if r.status_code == 200:
        print('\n  [OK] ' + str(r.json().get('prompt_id')))
    else:
        print('\n  [FAIL] Status: ' + str(r.status_code))
        try:
            err = r.json()
            print('  Error: ' + str(err))
        except:
            print('  Response: ' + r.text[:200])

asyncio.run(main())