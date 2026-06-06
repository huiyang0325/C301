"""Debug KSampler widget assignment"""
import json, httpx, asyncio

WORKFLOW_DIR = r'E:\咸鱼买工作流\模型和插件，下载后把里面文件夹剪切到压缩包解压后得comfyui文件夹内覆盖即可(1)\ComfyUI-aki-v2\ComfyUI\user\default\workflows'

async def main():
    wf_name = '6-【闲鱼萌宝】Z-image 高清出图.json'
    with open(WORKFLOW_DIR + '/' + wf_name, encoding='utf-8') as f:
        workflow = json.load(f)

    # Get object_info
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get('http://127.0.0.1:8188/object_info')
    object_info = r.json()

    # Find KSampler node
    ksampler_node = None
    for n in workflow['nodes']:
        if n.get('type') == 'KSampler':
            ksampler_node = n
            break

    print(f"KSampler widgets_values: {ksampler_node.get('widgets_values')}")
    print(f"KSampler inputs: {ksampler_node.get('inputs')}")

    # Build link_map
    link_map = {}
    for link in workflow.get('links', []):
        if len(link) >= 3:
            link_map[link[0]] = [link[1], link[2]]

    # Test my conversion logic
    wvs = ksampler_node.get('widgets_values', [])
    print(f"\nwvs: {wvs}")
    print(f"wvs[0]={wvs[0]}, wvs[1]={wvs[1]}, wvs[2]={wvs[2]}, wvs[3]={wvs[3]}, wvs[4]={wvs[4]}, wvs[5]={wvs[5]}")

    ct = 'KSampler'
    node_input_order = []
    is_input_list = False
    if ct in object_info:
        info = object_info[ct]
        node_input_order = info.get('input_order', {}).get('required', [])
        is_input_list = info.get('is_input_list', False)

    print(f"\nKSampler input_order: {node_input_order}")
    print(f"KSampler is_input_list: {is_input_list}")

    # Build unlinked_input_order
    unlinked_input_order = []
    for inp in ksampler_node.get('inputs', []):
        name = inp.get('name', '')
        link = inp.get('link')
        if link is not None and link in link_map:
            print(f"  Linked input: {name} -> link {link}")
            continue
        print(f"  Unlinked input: {name}")
        unlinked_input_order.append(name)

    print(f"\nunlinked_input_order: {unlinked_input_order}")

    # Build input_widget_map
    input_widget_map = {}
    wvs_idx = 0
    for name in unlinked_input_order:
        if wvs_idx < len(wvs):
            input_widget_map[name] = wvs_idx
            print(f"  {name} -> wvs[{wvs_idx}] = {wvs[wvs_idx]}")
            wvs_idx += 1

    print(f"\ninput_widget_map: {input_widget_map}")

    # Apply to inputs
    inputs = {}
    for inp in ksampler_node.get('inputs', []):
        name = inp.get('name', '')
        link = inp.get('link')
        if link is not None and link in link_map:
            inputs[name] = link_map[link]
            print(f"Input {name} = linked {link_map[link]}")
        elif name in input_widget_map:
            inputs[name] = wvs[input_widget_map[name]]
            print(f"Input {name} = wvs[{input_widget_map[name]}] = {wvs[input_widget_map[name]]}")

    print(f"\nFinal inputs: {inputs}")

asyncio.run(main())