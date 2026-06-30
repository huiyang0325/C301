#!/usr/bin/env python3
"""长视频生成完整流程测试脚本

测试内容：
1. 检查已生成的短视频文件
2. 调用 Windows ffmpeg 拼接视频
3. 更新编排文件的 long_video_groups 字段
4. 调用 getArrangement API 验证数据
5. 验证视频 URL 可访问

与项目代码 generation_tasks.py 的逻辑一致，但不改变项目代码。
"""

import asyncio
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Optional

import httpx

# ============================================================================
# 配置
# ============================================================================

PROJECT_NAME = "1-ff6183db"
PROJECT_PATH = Path(f"/mnt/e/ArcReel/projects/{PROJECT_NAME}")
OUTPUT_DIR = PROJECT_PATH / "videos"
ARRANGEMENT_FILE = PROJECT_PATH / "arrangements" / "episode_1.json"

# API 配置
API_BASE_URL = "http://172.26.175.147:1246/api/v1"
AUTH_TOKEN = "dummy"  # 测试用 token

# 已生成的短视频文件（模拟 segment_ids 对应的视频）
SEGMENT_IDS = ["E01S01", "E01S02", "E01S03"]
VIDEO_FILES = [
    OUTPUT_DIR / "scene_long_video_1_lv_1.mp4",
    OUTPUT_DIR / "scene_long_video_1_lv_2.mp4",
    OUTPUT_DIR / "scene_long_video_1_lv_3.mp4",
]

# ============================================================================
# 工具函数
# ============================================================================


def _linux_to_windows_path(linux_path: str) -> str:
    """将 WSL/Linux 路径转换为 Windows 路径。"""
    if linux_path.startswith("/mnt/"):
        # /mnt/e/ArcReel/... → E:\ArcReel\...
        return linux_path.replace("/mnt/e/", "E:\\").replace("/", "\\")
    return linux_path


def _decode_output(data: bytes) -> str:
    """尝试多种编码解码 Windows cmd 输出。"""
    for enc in ("utf-8", "gbk", "gb2312", "latin1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


# ============================================================================
# 步骤 1: 检查短视频文件
# ============================================================================


def step1_check_video_files():
    """检查短视频文件是否存在。"""
    print("=" * 60)
    print("步骤 1: 检查短视频文件")
    print("=" * 60)

    valid_files = []
    for seg_id, video_file in zip(SEGMENT_IDS, VIDEO_FILES):
        exists = video_file.exists()
        size = video_file.stat().st_size / 1024 / 1024 if exists else 0
        status = "✅" if exists else "❌"
        print(f"  {status} {seg_id}: {video_file.name} ({size:.1f} MB)")
        if exists:
            valid_files.append(video_file)

    if not valid_files:
        print("\n错误: 没有可用的短视频文件")
        return None

    print(f"\n有效视频文件: {len(valid_files)} 个")
    return valid_files


# ============================================================================
# 步骤 2: 拼接视频（与 generation_tasks.py 的 _concat_videos 逻辑一致）
# ============================================================================


async def step2_concat_videos(valid_files: list[Path]) -> Optional[Path]:
    """使用 ffmpeg 拼接视频。"""
    print("\n" + "=" * 60)
    print("步骤 2: 拼接视频")
    print("=" * 60)

    # 生成唯一的输出文件名（与项目代码一致）
    segment_ids_hash = hashlib.md5(",".join(sorted(SEGMENT_IDS)).encode()).hexdigest()[:8]
    output_path = OUTPUT_DIR / f"long_video_long_video_1_{segment_ids_hash}.mp4"

    print(f"输出文件: {output_path.name}")

    # 创建 concat file（在 Windows 可访问的位置）
    concat_file = PROJECT_PATH / "videos" / "concat_test.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for p in valid_files:
            # 直接使用 Linux 路径
            f.write(f"file '{p.resolve()}'\n")

    print(f"Concat 文件: {concat_file}")
    print("Concat 内容:")
    with open(concat_file, "r") as f:
        for line in f:
            print(f"  {line.strip()}")

    # 调用 Linux ffmpeg
    ffmpeg_path = os.path.expanduser("~/bin/ffmpeg")
    concat_file_path = str(concat_file.resolve())
    output_path_str = str(output_path.resolve())

    cmd = [ffmpeg_path, "-y", "-f", "concat", "-safe", "0", "-i", concat_file_path, "-c", "copy", output_path_str]

    print(f"\n执行命令: {' '.join(cmd)}")

    result = await asyncio.to_thread(
        subprocess.run,
        cmd,
        capture_output=True,
    )

    if result.returncode != 0:
        stderr_msg = _decode_output(result.stderr)
        print(f"❌ 拼接失败!")
        print(f"stderr: {stderr_msg[:500]}")
        return None

    print("✅ 拼接成功!")

    # 检查输出文件
    if output_path.exists():
        size = output_path.stat().st_size / 1024 / 1024
        print(f"输出文件大小: {size:.1f} MB")
    else:
        print("❌ 输出文件不存在")
        return None

    # 清理 concat file
    concat_file.unlink(missing_ok=True)

    return output_path


# ============================================================================
# 步骤 3: 更新编排文件的 long_video_groups（与 generation_tasks.py 逻辑一致）
# ============================================================================


def step3_update_arrangement(final_video_path: Path):
    """更新编排文件的 long_video_groups 字段。"""
    print("\n" + "=" * 60)
    print("步骤 3: 更新编排文件")
    print("=" * 60)

    if not ARRANGEMENT_FILE.exists():
        print(f"❌ 编排文件不存在: {ARRANGEMENT_FILE}")
        return False

    # 读取编排文件
    with open(ARRANGEMENT_FILE, "r", encoding="utf-8") as f:
        arrangement = json.load(f)

    # 生成 key（与项目代码一致：按 segment_ids 排序后用逗号拼接）
    key = ",".join(sorted(SEGMENT_IDS))

    # 计算相对路径
    rel_path = str(final_video_path.relative_to(PROJECT_PATH))

    # 更新 long_video_groups
    if "long_video_groups" not in arrangement:
        arrangement["long_video_groups"] = {}

    arrangement["long_video_groups"][key] = rel_path

    # 保存编排文件
    with open(ARRANGEMENT_FILE, "w", encoding="utf-8") as f:
        json.dump(arrangement, f, ensure_ascii=False, indent=2)

    print(f"✅ 已更新编排文件")
    print(f"  key: {key}")
    print(f"  path: {rel_path}")
    print(f"  long_video_groups: {json.dumps(arrangement['long_video_groups'], indent=2)}")

    return True


# ============================================================================
# 步骤 4: 调用 getArrangement API 验证
# ============================================================================


async def step4_verify_arrangement_api():
    """调用 getArrangement API 验证数据。"""
    print("\n" + "=" * 60)
    print("步骤 4: 调用 getArrangement API")
    print("=" * 60)

    url = f"{API_BASE_URL}/projects/{PROJECT_NAME}/arrangements/1"

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Bearer {AUTH_TOKEN}"},
            )

        if resp.status_code != 200:
            print(f"❌ API 调用失败: {resp.status_code}")
            print(f"响应: {resp.text[:500]}")
            return False

        data = resp.json()
        long_video_groups = data.get("long_video_groups", {})

        print(f"✅ API 调用成功")
        print(f"  long_video_groups 包含 {len(long_video_groups)} 个条目")

        for key, path in long_video_groups.items():
            print(f"  - key: {key[:50]}...")
            print(f"    path: {path}")

        return True

    except Exception as e:
        print(f"❌ API 调用异常: {e}")
        return False


# ============================================================================
# 步骤 5: 验证视频 URL 可访问
# ============================================================================


async def step5_verify_video_url():
    """验证视频 URL 可访问。"""
    print("\n" + "=" * 60)
    print("步骤 5: 验证视频 URL 可访问")
    print("=" * 60)

    # 从编排文件读取最新的长视频路径
    with open(ARRANGEMENT_FILE, "r", encoding="utf-8") as f:
        arrangement = json.load(f)

    long_video_groups = arrangement.get("long_video_groups", {})
    if not long_video_groups:
        print("❌ long_video_groups 为空")
        return False

    # 获取最后一个
    key = list(long_video_groups.keys())[-1]
    video_path = long_video_groups[key]

    # 构建文件 URL
    file_url = f"{API_BASE_URL}/files/{PROJECT_NAME}/{video_path}"

    print(f"视频 URL: {file_url}")

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(file_url)

        if resp.status_code in (200, 206):  # 206 = 部分内容（流媒体）
            content_length = resp.headers.get("content-length", "未知")
            content_type = resp.headers.get("content-type", "未知")
            print(f"✅ 视频可访问")
            print(f"  status: {resp.status_code}")
            print(f"  content-length: {content_length}")
            print(f"  content-type: {content_type}")
            return True
        else:
            print(f"❌ 视频不可访问: {resp.status_code}")
            return False

    except Exception as e:
        print(f"❌ 验证异常: {e}")
        return False


# ============================================================================
# 主流程
# ============================================================================


async def main():
    """执行完整测试流程。"""
    print("\n" + "=" * 60)
    print("长视频生成完整流程测试")
    print("=" * 60)
    print(f"项目: {PROJECT_NAME}")
    print(f"Segment IDs: {SEGMENT_IDS}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"编排文件: {ARRANGEMENT_FILE}")
    print()

    # 步骤 1: 检查短视频
    valid_files = step1_check_video_files()
    if not valid_files:
        print("\n测试失败: 没有可用的短视频文件")
        return

    # 步骤 2: 拼接视频
    final_video = await step2_concat_videos(valid_files)
    if not final_video:
        print("\n测试失败: 视频拼接失败")
        return

    # 步骤 3: 更新编排文件
    if not step3_update_arrangement(final_video):
        print("\n测试失败: 更新编排文件失败")
        return

    # 步骤 4: 验证 API
    api_ok = await step4_verify_arrangement_api()
    if not api_ok:
        print("\n测试失败: API 验证失败")
        return

    # 步骤 5: 验证视频 URL
    url_ok = await step5_verify_video_url()
    if not url_ok:
        print("\n测试失败: 视频 URL 验证失败")
        return

    print("\n" + "=" * 60)
    print("🎉 所有测试通过!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())