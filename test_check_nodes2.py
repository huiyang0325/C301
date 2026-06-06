"""查看特定节点的详细信息"""
import json, httpx, asyncio

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get('http://127.0.0.1:8188/object_info')
    info = r.json()

    # Check specific nodes
    nodes_to_check = [
        'LayerUtility: ImageReelComposit',
        'LayerUtility: ImageReel',
        'CR Prompt Text',
        'TextEncodeQwenImageEditPlus',
    ]

    for key in nodes_to_check:
        if key in info:
            print(f"\n{key}:")
            input_info = info[key].get('input', {})
            required = input_info.get('required', {})
            optional = input_info.get('optional', {})
            print(f"  required: {list(required.keys())}")
            print(f"  optional: {list(optional.keys())}")
        else:
            print(f"\n{key}: NOT FOUND")

asyncio.run(main())