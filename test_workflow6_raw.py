"""测试workflow 6 - 直接发送完整JSON"""
import json, httpx, asyncio

WORKFLOW_DIR = r'E:\咸鱼买工作流\模型和插件，下载后把里面文件夹剪切到压缩包解压后得comfyui文件夹内覆盖即可(1)\ComfyUI-aki-v2\ComfyUI\user\default\workflows'

async def main():
    wf_name = '6-【闲鱼萌宝】Z-image 高清出图.json'
    with open(WORKFLOW_DIR + '/' + wf_name, encoding='utf-8') as f:
        workflow = json.load(f)

    # Build the prompt exactly as our converter does
    prompt = {}
    for node in workflow['nodes']:
        nid = str(node['id'])
        if nid in ['13', '14']:  # Skip Note, Fast Groups Bypasser
            continue
        ct = node.get('type', '')
        if ct == 'Reroute':
            ct = 'ReroutePrimitive|pysssss'

        inputs = {}
        wvs = node.get('widgets_values') or []
        if not isinstance(wvs, list):
            wvs = []

        # Simple widget assignment (no object_info)
        idx = 0
        for inp in node.get('inputs', []):
            name = inp.get('name', '')
            if name == '' and ct == 'ReroutePrimitive|pysssss':
                name = 'value'
            link = inp.get('link')
            if link is not None:
                # Parse link to get [src_node, src_output]
                for l in workflow.get('links', []):
                    if l[0] == link:
                        inputs[name] = [str(l[1]), l[2]]
                        break
            elif idx < len(wvs):
                inputs[name] = wvs[idx]
                idx += 1

        # Clean empty inputs
        for key in list(inputs.keys()):
            if inputs[key] is None or inputs[key] == '':
                del inputs[key]

        prompt[nid] = {'class_type': ct, 'inputs': inputs}

    # Fix seed and image
    for nid, data in prompt.items():
        inputs = data.get('inputs', {})
        for key in list(inputs.keys()):
            val = inputs[key]
            if key == 'image' and isinstance(val, str):
                inputs[key] = 'image1.png'
            if key == 'seed' and (val == 'randomize' or not isinstance(val, (int, float))):
                inputs[key] = 0

    # Print the prompt
    print("Prompt to submit:")
    print(json.dumps(prompt, indent=2, ensure_ascii=False)[:2000])

    # Check node 8
    print(f"\nNode 8 exists: {'8' in prompt}")
    if '8' in prompt:
        print(f"Node 8: {prompt['8']}")

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