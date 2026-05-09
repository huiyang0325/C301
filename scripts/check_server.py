#!/usr/bin/env python3
"""通过服务器 API 测试 generate_overview。"""

import requests
import json
import sys

# 设置服务器地址
BASE_URL = "http://127.0.0.1:1241"

# 读取项目列表
try:
    resp = requests.get(f"{BASE_URL}/api/v1/projects")
    print(f"Projects API status: {resp.status_code}")
    if resp.status_code == 200:
        projects = resp.json()
        print(f"Found {len(projects)} projects")
        for p in projects[:5]:
            print(f"  - {p.get('name', p)}")
    else:
        print(f"Response: {resp.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

# 检查系统配置
try:
    resp = requests.get(f"{BASE_URL}/api/v1/providers")
    print(f"\nProviders API status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Providers: {json.dumps(data, indent=2)[:500]}")
except Exception as e:
    print(f"Error: {e}")