"""调试工作流转换 - 查看节点6的问题"""
import json, httpx, asyncio

WORKFLOW_DIR = r'E:\咸鱼买工作流\模型和插件，下载后把里面文件夹剪切到压缩包解压后得comfyui文件夹内覆盖即可(1)\ComfyUI-aki-v2\ComfyUI\user\default\workflows'

SKIP_TYPES = {
    'Reroute', 'Note', 'Label (rgthree)', 'Fast Groups Bypasser (rgthree)',
    'VRAMCleanup', 'RAMCleanup', 'PrimitiveNode', 'SetNode', 'GetNode'
}
TYPE_MAP = {'Reroute': 'ReroutePrimitive|pysssss'}

async def get_available():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get('http://127.0.0.1:8188/object_info')
    return set(r.json().keys())

def convert(workflow, available):
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
        wvs_idx = 0

        for inp in node.get('inputs', []):
            name = inp.get('name', '')
            link = inp.get('link')
            if link is not None and link in link_map:
                inputs[name] = link_map[link]
            elif wvs_idx < len(wvs):
                inputs[name] = wvs[wvs_idx]
                wvs_idx += 1

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
    available = await get_available()
    print('Available: ' + str(len(available)) + ' nodes\n')

    wf_name = '3-【闲鱼萌宝】2511双图编辑+姿态迁移 .json'
    print('\n=== ' + wf_name + ' ===')
    with open(WORKFLOW_DIR + '/' + wf_name, encoding='utf-8') as f:
        workflow = json.load(f)

    # Print node 6 details
    print("Looking for node 6...")
    for n in workflow['nodes']:
        if str(n.get('id')) == '6':
            print(f"  Node 6: type={n.get('type')}, widgets={n.get('widgets_values')}, inputs={n.get('inputs')}")

    prompt = convert(workflow, available)

    # Print all nodes in converted prompt
    print("\nAll converted prompt nodes:")
    for nid in sorted(prompt.keys(), key=int):
        d = prompt[nid]
        print(f"  Node {nid}: class={d.get('class_type')}, inputs={d.get('inputs')}")

    # Cascade removal
    removed = True
    while removed:
        removed = False
        bad_ids = [nid for nid, d in prompt.items() if d.get('_bad_link')]
        for nid in bad_ids:
            print(f"  Removing node {nid} due to bad link")
            prompt.pop(nid, None)
            removed = True
        if removed:
            for nid, d in list(prompt.items()):
                for key, val in list(d.get('inputs', {}).items()):
                    if isinstance(val, list) and len(val) == 2:
                        if str(val[0]) in bad_ids:
                            print(f"  Removing node {nid} because it references {val[0]}")
                            prompt.pop(nid, None)
                            removed = True
                            break

    for d in prompt.values():
        d.pop('_bad_link', None)

    print("\nAfter cascade removal:")
    for nid in sorted(prompt.keys(), key=int):
        d = prompt[nid]
        print(f"  Node {nid}: class={d.get('class_type')}, inputs={d.get('inputs')}")

    # Check if node 6 exists
    if '6' in prompt:
        print(f"\nNode 6 exists: class={prompt['6'].get('class_type')}, inputs={prompt['6'].get('inputs')}")
    else:
        print("\nNode 6 was removed!")

    has_text = set_text(prompt)
    if has_text:
        fix_prompt(prompt)

    # Submit and see error
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt})
    if r.status_code == 200:
        print('\n  [OK] ' + str(r.json().get('prompt_id')))
    else:
        try:
            err = r.json()
            print('\n  [FAIL] ' + str(err.get('error', {}).get('details', '')))
            node_errors = err.get('error', {}).get('node_errors', {})
            for nid, e in list(node_errors.items())[:5]:
                errs = e.get('errors', [{}])
                msg = (errs[0].get('message', '') if errs else '')
                print(f'    Node {nid}: {msg[:100]}')
        except:
            print('\n  [FAIL] ' + r.text[:100])

asyncio.run(main())