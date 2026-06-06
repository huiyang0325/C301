"""检查workflow 6的链接"""
import json

WORKFLOW_DIR = r'E:\咸鱼买工作流\模型和插件，下载后把里面文件夹剪切到压缩包解压后得comfyui文件夹内覆盖即可(1)\ComfyUI-aki-v2\ComfyUI\user\default\workflows'

wf_name = '6-【闲鱼萌宝】Z-image 高清出图.json'
with open(WORKFLOW_DIR + '/' + wf_name, encoding='utf-8') as f:
    workflow = json.load(f)

print("Links in workflow 6:")
for link in workflow.get('links', []):
    print(f"  Link {link[0]}: node {link[1]} output {link[2]} -> node {link[3]} input '{link[4]}'")

print("\nNodes with id and type:")
for n in workflow['nodes']:
    nid = n.get('id')
    ct = n.get('type', '')
    print(f"  Node {nid}: {ct}")