"""查看特定节点的object_info"""
import json, httpx, asyncio

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get('http://127.0.0.1:8188/object_info')
    info = r.json()

    # Check LayerUtility nodes
    for key in info:
        if 'LayerUtility' in key or 'ImageReel' in key or 'Reel' in key:
            print(f"\n{key}:")
            inputs = info[key].get('input', {})
            required = inputs.get('required', {})
            optional = inputs.get('optional', {})
            print(f"  required: {list(required.keys())}")
            print(f"  optional: {list(optional.keys())}")

asyncio.run(main())