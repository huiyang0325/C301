"""Debug remaining failures"""
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
        for i, name in enumerate(unlinked_inputs):
            if i < len(wvs):
                input_widget_map[name] = i

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
        ct = data.get('class_type', '')
        for key in list(inputs.keys()):
            val = inputs[key]
            if key == 'filename_prefix' and (val is None or val == ''):
                inputs[key] = 'output'
            if key == 'image' and isinstance(val, str):
                inputs[key] = 'image1.png'
            if key == 'seed' and (val == 'randomize' or not isinstance(val, (int, float))):
                inputs[key] = 0
            if ct in ('KSampler', 'KSamplerAdvanced') and key in ('seed', 'noise_seed'):
                if val == 'randomize' or not isinstance(val, (int, float)):
                    inputs[key] = 0
            if ct in ('KSampler', 'KSamplerAdvanced') and key == 'steps':
                if val == 'randomize' or not isinstance(val, int):
                    inputs[key] = 9
            if ct in ('KSampler', 'KSamplerAdvanced') and key == 'sampler_name':
                valid_samplers = ('euler', 'euler_ancestral', 'euler_cfg_pp', 'dpm_2', 'dpmpp_2m', 'ddim', 'lcm', 'heun', 'dpm_fast', 'dpm_adaptive')
                if not isinstance(val, str) or val not in valid_samplers:
                    inputs[key] = 'euler'
            if ct in ('KSampler', 'KSamplerAdvanced') and key == 'scheduler':
                valid_schedulers = ('simple', 'sgm_uniform', 'karras', 'exponential', 'ddim_uniform', 'beta', 'normal', 'linear_quadratic', 'kl_optimal', 'bong_tangent', 'beta57')
                if not isinstance(val, str) or val not in valid_schedulers:
                    inputs[key] = 'simple'
            if ct in ('KSampler', 'KSamplerAdvanced') and key == 'denoise':
                if not isinstance(val, float) or val > 1.0:
                    inputs[key] = 1.0
            if ct in ('KSampler', 'KSamplerAdvanced') and key == 'cfg':
                if not isinstance(val, (int, float)):
                    inputs[key] = 1.0
            if ct == 'TextEncodeQwenImageEditPlus' and key == 'prompt' and 'edited_text_widget' not in inputs:
                inputs['edited_text_widget'] = ''
            if key == 'frame_rate' and (val is None or val == ''):
                inputs[key] = 24
            if val == '':
                del inputs[key]
        if 'edited_text_widget' not in inputs and ct in ('TextEncodeQwenImageEditPlus', 'TextEncode', 'CLIPTextEncode', 'Prompt_Edit'):
            inputs['edited_text_widget'] = ''
        if ct == 'SaveImage' and 'filename_prefix' not in inputs:
            inputs['filename_prefix'] = 'output'
        if ct == 'VHS_VideoCombine':
            if 'frame_rate' not in inputs:
                inputs['frame_rate'] = 24
            if 'loop_count' not in inputs:
                inputs['loop_count'] = 1
            if 'filename_prefix' not in inputs:
                inputs['filename_prefix'] = 'output'
            if 'format' not in inputs:
                inputs['format'] = 'video/h264-mp4'
            if 'pingpong' not in inputs:
                inputs['pingpong'] = False
            if 'save_output' not in inputs:
                inputs['save_output'] = True

async def debug_workflow(wf_name):
    object_info = await get_object_info()
    available = set(object_info.keys())

    print(f'\n=== {wf_name} ===')
    with open(WORKFLOW_DIR + '/' + wf_name, encoding='utf-8') as f:
        workflow = json.load(f)

    prompt = convert_workflow(workflow, available, object_info)

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

    print(f"Nodes after conversion: {len(prompt)}")

    has_text = set_text(prompt)
    if not has_text:
        print('  [SKIP] no text input')
        return

    fix_prompt(prompt)

    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post('http://127.0.0.1:8188/prompt', json={'prompt': prompt})
    if r.status_code == 200:
        print('  [OK] ' + str(r.json().get('prompt_id')))
    else:
        print(f'  [FAIL] Status={r.status_code}')
        print(f'  Response: {r.text[:500]}')

async def main():
    await debug_workflow('1-【闲鱼萌宝】2511单图编辑 .json')
    await debug_workflow('7-【闲鱼萌宝】自动反推洗图+sd放大.json')
    await debug_workflow('9-【闲鱼萌宝】双采样超多细节文生图.json')
    await debug_workflow('12-【闲鱼萌宝】LTX2.3-首尾帧视频优化版.json')
    await debug_workflow('14-【闲鱼萌宝】LTX2.3双人对话对口型 .json')
    await debug_workflow('15-【闲鱼萌宝】LTX2.3多图参考引导生成工作流 .json')

asyncio.run(main())
