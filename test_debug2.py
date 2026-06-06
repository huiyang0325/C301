"""调试工作流转换，打印详细错误和prompt"""
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
    filtered = {k: v for k, v in link_map.items() if str(v[0]) not in skip_ids}

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
            if link is not None and link in filtered:
                inputs[name] = filtered[link]
            elif idx < len(wvs):
                inputs[name] = wvs[idx]
                idx += 1

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
            # Fix LoadImage
            if key == 'image' and isinstance(val, str):
                inputs[key] = 'image1.png'
            # Fix KSampler seed
            if key == 'seed' and (val == 'randomize' or not isinstance(val, (int, float))):
                inputs[key] = 0
            # Fix PlaySound volume - must be float
            if key == 'volume' and isinstance(val, str) and not val.replace('.', '').replace('-', '').isdigit():
                try:
                    inputs[key] = float(val)
                except:
                    pass
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
    available = await get_available()
    print('Available: ' + str(len(available)) + ' nodes\n')

    # Test workflow 3 first to see the issue
    wf_name = '3-【闲鱼萌宝】2511双图编辑+姿态迁移 .json'
    print('\n=== ' + wf_name + ' ===')
    try:
        with open(WORKFLOW_DIR + '/' + wf_name, encoding='utf-8') as f:
            workflow = json.load(f)

        # Print the workflow structure for debugging
        print("Nodes with id, type, widgets_values:")
        for n in workflow['nodes']:
            nid = n.get('id')
            ct = n.get('type', '')
            wvs = n.get('widgets_values', [])
            inputs = n.get('inputs', [])
            print(f"  Node {nid}: type={ct}, widgets={wvs[:5] if wvs else []}, inputs={[(i.get('name'), i.get('link')) for i in inputs[:3]]}")

        prompt = convert(workflow, available)
        print("\nConverted prompt nodes:")
        for nid, data in list(prompt.items())[:10]:
            print(f"  Node {nid}: class={data.get('class_type')}, inputs={data.get('inputs')}")

        # Remove nodes with bad links
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

        print("\nAfter cascade removal:")
        for nid, data in list(prompt.items())[:10]:
            print(f"  Node {nid}: class={data.get('class_type')}, inputs={data.get('inputs')}")

        has_text = set_text(prompt)
        if not has_text:
            print('  [SKIP] no text input')
        else:
            fix_prompt(prompt)
            print("\nAfter fix_prompt:")
            for nid, data in list(prompt.items())[:10]:
                print(f"  Node {nid}: class={data.get('class_type')}, inputs={data.get('inputs')}")

            await submit_and_show(prompt, wf_name)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print('  [ERROR] ' + str(e))

asyncio.run(main())