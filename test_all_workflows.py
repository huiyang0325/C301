"""测试所有 ComfyUI 工作流"""
import json, httpx, asyncio

WORKFLOW_DIR = r'E:\咸鱼买工作流\模型和插件，下载后把里面文件夹剪切到压缩包解压后得comfyui文件夹内覆盖即可(1)\ComfyUI-aki-v2\ComfyUI\user\default\workflows'

workflows = [
    '1-【闲鱼萌宝】2511单图编辑 .json',
    '2-【闲鱼萌宝】2511单图出分镜图.json',
    '3-【闲鱼萌宝】2511双图编辑+姿态迁移 .json',
    '4-【闲鱼萌宝】2511三图编辑.json',
    '5-【闲鱼萌宝】单图可视化出多角度.json',
    '6-【闲鱼萌宝】Z-image 高清出图.json',
    '7-【闲鱼萌宝】自动反推洗图+sd放大.json',
    '8-【闲鱼萌宝】图片sd放大.json',
    '9-【闲鱼萌宝】双采样超多细节文生图.json',
    '10-11-【闲鱼萌宝】LTX-2.3 文&图生视频优化版.json',
    '12-【闲鱼萌宝】LTX2.3-首尾帧视频优化版.json',
    '13-【闲鱼萌宝】LTX 2.3单人对口型工作流 .json',
    '14-【闲鱼萌宝】LTX2.3双人对话对口型 .json',
    '15-【闲鱼萌宝】LTX2.3多图参考引导生成工作流 .json',
]

# 跳过这些类型节点
SKIP_TYPES = {'Reroute', 'Note', 'Label (rgthree)', 'Fast Groups Bypasser (rgthree)'}
# 类型映射
TYPE_MAP = {
    'Reroute': 'ReroutePrimitive|pysssss',
}

async def load_workflow(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def convert_workflow(workflow, available):
    nodes = {n['id']: n for n in workflow.get('nodes', [])}

    link_map = {}
    for link in workflow.get('links', []):
        if len(link) >= 3:
            link_map[link[0]] = [link[1], link[2]]

    skip_ids = {str(n['id']) for n in workflow['nodes'] if n.get('type') in SKIP_TYPES}

    # 过滤 link_map：排除来自跳过的节点的链接
    filtered_link_map = {k: v for k, v in link_map.items() if str(v[0]) not in skip_ids}

    prompt = {}
    skipped_types = []

    for node in workflow['nodes']:
        nid = str(node['id'])
        if nid in skip_ids:
            continue

        class_type = node.get('type', '')
        class_type = TYPE_MAP.get(class_type, class_type)

        if class_type not in available:
            skipped_types.append((nid, class_type))
            continue

        inputs = {}
        wvs = node.get('widgets_values') or []
        idx = 0
        for inp in node.get('inputs', []):
            name = inp.get('name', '')
            link = inp.get('link')
            if link is not None and link in filtered_link_map:
                inputs[name] = filtered_link_map[link]
            elif idx < len(wvs):
                inputs[name] = wvs[idx]
                idx += 1

        prompt[nid] = {'class_type': class_type, 'inputs': inputs}

    return prompt, skipped_types

def set_text_prompt(prompt):
    """在 prompt 中找一个文本输入并设置提示词"""
    for nid, data in prompt.items():
        inputs = data.get('inputs', {})
        for key in ['text', 'prompt', 'text_g', 'text_l']:
            if key in inputs and isinstance(inputs[key], str) and len(inputs[key]) > 5:
                inputs[key] = 'a beautiful landscape, high quality, detailed'
                return True
    return False

async def submit_workflow(name, prompt):
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt})
        if resp.status_code == 200:
            pid = resp.json().get('prompt_id')
            print(f'  [OK] prompt_id={pid}')
            return True
        else:
            err = resp.text[:200].replace('\n', ' ')
            print(f'  [FAIL] {err}')
            return False

async def main():
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get('http://127.0.0.1:8188/object_info')
        available = set(resp.json().keys())

    results = []
    for wf_name in workflows:
        print(f'\n=== {wf_name} ===')
        try:
            workflow = await load_workflow(f'{WORKFLOW_DIR}/{wf_name}')
            prompt, skipped = convert_workflow(workflow, available)
            if skipped:
                print(f'  [SKIP_NODES] {skipped[:3]}...')

            if not set_text_prompt(prompt):
                print(f'  [SKIP] 无文本输入')
                results.append((wf_name, 'SKIP_NO_TEXT', ''))
                continue

            ok = await submit_workflow(wf_name, prompt)
            results.append((wf_name, 'OK' if ok else 'FAIL', ''))
        except Exception as e:
            print(f'  [ERROR] {e}')
            results.append((wf_name, 'ERROR', str(e)))

    print('\n\n=== 汇总 ===')
    for name, status, _ in results:
        print(f'{status:8s} : {name}')

asyncio.run(main())