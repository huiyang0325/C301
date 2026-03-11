# Seedance 视频生成 API — Python 接入指南

## 概览

视频生成是**异步**流程：

1. 调用 `POST /contents/generations/tasks` 创建任务，获得 task ID
2. 轮询 `GET /contents/generations/tasks/{id}`，直到状态变为 `succeeded`
3. 从响应的 `content.video_url` 下载 MP4 文件

---

## 模型 ID

| 模型 | Model ID | 备注 |
|---|---|---|
| Seedance 1.5 pro | `doubao-seedance-1-5-pro-251215` | 支持音频、样片模式、首尾帧 |
| Seedance 1.0 pro | `doubao-seedance-1-0-pro-250528` | |
| Seedance 1.0 pro fast | `doubao-seedance-1-0-pro-fast-251015` | |
| Seedance 1.0 lite i2v | `doubao-seedance-1-0-lite-i2v-250428` | 支持参考图 |
| Seedance 1.0 lite t2v | `doubao-seedance-1-0-lite-t2v-250428` | |

> **注意**：Seedance 2.0 目前仅支持控制台体验，暂不支持 API 调用。

---

## 安装 SDK

```bash
pip install 'volcengine-python-sdk[ark]'
```

## 初始化客户端

```python
import os
from volcenginesdkarkruntime import Ark

client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.environ.get("ARK_API_KEY"),
)
```

---

## 基础使用

### 1. 文生视频

```python
import os
import time
from volcenginesdkarkruntime import Ark

client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.environ.get("ARK_API_KEY"),
)

create_result = client.content_generation.tasks.create(
    model="doubao-seedance-1-5-pro-251215",
    content=[
        {
            "type": "text",
            "text": "写实风格，晴朗的蓝天之下，一大片白色的雏菊花田"
        }
    ],
    ratio="16:9",
    duration=5,
    watermark=False,
)

task_id = create_result.id
while True:
    get_result = client.content_generation.tasks.get(task_id=task_id)
    status = get_result.status
    if status == "succeeded":
        print(get_result.content.video_url)
        break
    elif status == "failed":
        print(f"Error: {get_result.error}")
        break
    else:
        print(f"Status: {status}, retrying in 10s...")
        time.sleep(10)
```

### 2. 图生视频 — 首帧（含音频）

```python
create_result = client.content_generation.tasks.create(
    model="doubao-seedance-1-5-pro-251215",
    content=[
        {
            "type": "text",
            "text": "女孩睁开眼，温柔地看向镜头，镜头缓缓拉出"
        },
        {
            "type": "image_url",
            "image_url": {
                "url": "https://example.com/first_frame.png"  # 首帧图片 URL
            }
            # 默认 role 即为 first_frame，无需显式指定
        }
    ],
    generate_audio=True,
    ratio="adaptive",
    duration=5,
    watermark=False,
)
```

### 3. 图生视频 — 首尾帧（含音频）

```python
create_result = client.content_generation.tasks.create(
    model="doubao-seedance-1-5-pro-251215",
    content=[
        {
            "type": "text",
            "text": "360度环绕运镜"
        },
        {
            "type": "image_url",
            "image_url": {"url": "https://example.com/first_frame.jpeg"},
            "role": "first_frame"
        },
        {
            "type": "image_url",
            "image_url": {"url": "https://example.com/last_frame.jpeg"},
            "role": "last_frame"
        }
    ],
    generate_audio=True,
    ratio="adaptive",
    duration=5,
    watermark=False,
)
```

### 4. 图生视频 — 参考图（1-4张）

```python
create_result = client.content_generation.tasks.create(
    model="doubao-seedance-1-0-lite-i2v-250428",
    content=[
        {
            "type": "text",
            "text": "[图1]戴眼镜的男生和[图2]的柯基，坐在[图3]的草坪上，卡通风格"
        },
        {
            "type": "image_url",
            "image_url": {"url": "https://example.com/ref1.png"},
            "role": "reference_image"
        },
        {
            "type": "image_url",
            "image_url": {"url": "https://example.com/ref2.png"},
            "role": "reference_image"
        },
        {
            "type": "image_url",
            "image_url": {"url": "https://example.com/ref3.png"},
            "role": "reference_image"
        }
    ],
    ratio="16:9",
    duration=5,
    watermark=False,
)
```

---

## 进阶使用

### 5. 离线推理（flex 模式，价格为在线的 50%）

```python
create_result = client.content_generation.tasks.create(
    model="doubao-seedance-1-5-pro-251215",
    content=[...],
    ratio="adaptive",
    duration=5,
    watermark=False,
    service_tier="flex",           # 切换到离线推理
    execution_expires_after=172800, # 超时自动终止（秒），最大 48h
)
# 离线任务轮询间隔建议设为 60s
```

### 6. 样片模式（Draft — 仅 Seedance 1.5 pro）

**Step 1：生成低成本 Draft 视频**

- 仅支持 480p，不支持尾帧、离线推理
- 有声视频折算系数 0.6，显著降低抽卡成本

```python
create_result = client.content_generation.tasks.create(
    model="doubao-seedance-1-5-pro-251215",
    content=[
        {"type": "text", "text": "..."},
        {"type": "image_url", "image_url": {"url": "..."}}
    ],
    seed=20,
    duration=6,
    draft=True,   # 开启样片模式
)
draft_task_id = create_result.id  # 保存此 ID，用于生成正式视频
```

**Step 2：基于 Draft 生成正式视频**

- 平台自动复用 Draft 的 model、text、image_url、generate_audio、seed、ratio、duration、camera_fixed
- 其余参数（resolution、watermark、service_tier、return_last_frame）可重新指定
- Draft task ID 有效期 7 天

```python
create_result = client.content_generation.tasks.create(
    model="doubao-seedance-1-5-pro-251215",
    content=[
        {
            "type": "draft_task",
            "draft_task": {"id": draft_task_id}  # Step1 返回的 ID
        }
    ],
    watermark=False,
    resolution="720p",
    return_last_frame=True,
    service_tier="default",
)
```

### 7. 生成多个连续视频（尾帧接龙）

```python
import os
import time
from volcenginesdkarkruntime import Ark

client = Ark(
    base_url="https://ark.cn-beijing.volces.com/api/v3",
    api_key=os.environ.get("ARK_API_KEY"),
)

def generate_video_with_last_frame(prompt, initial_image_url=None):
    """生成视频，返回 (video_url, last_frame_url)"""
    content = [{"text": prompt, "type": "text"}]
    if initial_image_url:
        content.append({
            "image_url": {"url": initial_image_url},
            "type": "image_url"
        })

    create_result = client.content_generation.tasks.create(
        model="doubao-seedance-1-5-pro-251215",
        content=content,
        return_last_frame=True,  # 返回尾帧，用于下一段接龙
        ratio="adaptive",
        duration=5,
        watermark=False,
    )

    task_id = create_result.id
    while True:
        get_result = client.content_generation.tasks.get(task_id=task_id)
        status = get_result.status
        if status == "succeeded":
            return get_result.content.video_url, get_result.content.last_frame_url
        elif status == "failed":
            print(f"Failed: {get_result.error}")
            return None, None
        else:
            print(f"Status: {status}, retrying in 10s...")
            time.sleep(10)


if __name__ == "__main__":
    prompts = ["提示词1", "提示词2", "提示词3"]
    initial_image_url = "https://example.com/first.png"
    video_urls = []

    for i, prompt in enumerate(prompts):
        video_url, last_frame_url = generate_video_with_last_frame(prompt, initial_image_url)
        if video_url and last_frame_url:
            video_urls.append(video_url)
            initial_image_url = last_frame_url  # 上一段尾帧作为下一段首帧
        else:
            print(f"Video {i+1} failed")
            break

    print("All videos:", video_urls)
    # 使用 ffmpeg 拼接多段视频
```

---

## 设置视频输出规格

支持两种方式传入规格参数：

**新方式（推荐）：在 request body 中直接传入参数**（强校验，参数错误会返回报错）

```python
create_result = client.content_generation.tasks.create(
    model="doubao-seedance-1-5-pro-251215",
    content=[{"type": "text", "text": "小猫对着镜头打哈欠"}],
    resolution="720p",   # 分辨率
    ratio="16:9",        # 宽高比
    duration=5,          # 时长（秒）
    # frames=29,         # 帧数（与 duration 二选一，仅 1.0 pro/lite 支持）
    seed=11,             # 随机种子
    camera_fixed=False,  # 是否固定摄像头
    watermark=True,
)
```

**旧方式：在提示词后追加 `--[参数]`**（弱校验，参数错误时自动用默认值）

```python
"text": "小猫对着镜头打哈欠 --rs 720p --rt 16:9 --dur 5 --seed 11 --cf false --wm true"
# 等价写法：--resolution 720p --ratio 16:9 --duration 5 --seed 11 --camerafixed false --watermark true
```

### 各分辨率输出像素尺寸

#### 480p

| ratio | 1.5 pro | 1.0 pro / 1.0 pro-fast / 1.0 lite |
|---|---|---|
| 16:9 | 864×496 | 864×480 |
| 4:3 | 752×560 | 736×544 |
| 1:1 | 640×640 | 640×640 |
| 3:4 | 560×752 | 544×736 |
| 9:16 | 496×864 | 480×864 |
| 21:9 | 992×432 | 960×416 |

#### 720p

| ratio | 1.5 pro | 1.0 pro / 1.0 pro-fast / 1.0 lite |
|---|---|---|
| 16:9 | 1280×720 | 1248×704 |
| 4:3 | 1112×834 | 1120×832 |
| 1:1 | 960×960 | 960×960 |
| 3:4 | 834×1112 | 832×1120 |
| 9:16 | 720×1280 | 704×1248 |
| 21:9 | 1470×630 | 1504×640 |

#### 1080p

| ratio | 1.5 pro | 1.0 pro / 1.0 pro-fast / 1.0 lite |
|---|---|---|
| 16:9 | 1920×1080 | 1920×1088 |
| 4:3 | 1664×1248 | 1664×1248 |
| 1:1 | 1440×1440 | 1440×1440 |
| 3:4 | 1248×1664 | 1248×1664 |
| 9:16 | 1080×1920 | 1088×1920 |
| 21:9 | 2206×946 | 2176×928 |

> 1.0 lite 的参考图场景不支持 1080p 和 `camera_fixed`

### frames 参数（仅 1.0 pro / 1.0 lite）

支持 [29, 289] 区间内所有满足 `25 + 4n`（n 为正整数）格式的整数值，与 `duration` 二选一。

---

## 任务管理

### 查询任务列表

```python
resp = client.content_generation.tasks.list(
    page_size=3,
    status="succeeded",
)
```

### 删除/取消任务

```python
client.content_generation.tasks.delete(task_id="cgt-2025****")
```

---

## 请求参数参考

| 参数 | 类型 | 说明 |
|---|---|---|
| `model` | str | Model ID |
| `content` | list | 内容数组，含 text / image_url / draft_task |
| `resolution` | str | `480p` / `720p` / `1080p`，默认 1080p |
| `ratio` | str | `16:9` / `9:16` / `4:3` / `3:4` / `1:1` / `21:9` / `adaptive` |
| `duration` | int | 时长（秒）；1.5 pro: 4-12，其他: 2-12 |
| `seed` | int | 随机种子，用于复现结果 |
| `generate_audio` | bool | 是否生成音频（仅 1.5 pro 支持） |
| `camera_fixed` | bool | 是否固定摄像头 |
| `watermark` | bool | 是否添加水印 |
| `service_tier` | str | `default`（在线）/ `flex`（离线，50% 价格） |
| `execution_expires_after` | int | 离线任务超时秒数，最大 172800（48h） |
| `return_last_frame` | bool | 是否在响应中返回视频尾帧 URL |
| `draft` | bool | 开启样片模式（仅 1.5 pro，仅 480p） |
| `callback_url` | str | Webhook 回调地址 |

> **ratio=adaptive**：模型自动根据输入图片比例决定输出比例（图生视频推荐）

---

## 响应结构

```json
{
  "id": "cgt-2025****",
  "model": "doubao-seedance-1-5-pro-251215",
  "status": "succeeded",
  "content": {
    "video_url": "https://.../*.mp4",
    "last_frame_url": "https://.../*.png"  // 仅 return_last_frame=true 时存在
  },
  "usage": {
    "completion_tokens": 246840,
    "total_tokens": 246840
  },
  "created_at": 1765510475,
  "updated_at": 1765510559,
  "seed": 58944,
  "resolution": "1080p",
  "ratio": "16:9",
  "duration": 5,
  "framespersecond": 24,
  "service_tier": "default",
  "execution_expires_after": 172800
}
```

**status 枚举**：`queued` → `running` → `succeeded` / `failed` / `expired`

---

## 限流说明

| 模式 | 限制维度 | 1.5 pro / 1.0 pro / 1.0 pro-fast | 1.0 lite |
|---|---|---|---|
| 在线（default） | RPM | 600 | 300 |
| 在线（default） | 并发数 | 10 | 5 |
| 离线（flex） | TPD | 5000亿 token/天 | 2500亿 token/天 |

- **任务数据保留时间**：24 小时，请及时下载视频

---

## 关键注意事项

- `ratio=adaptive` 仅图生视频场景支持；文生视频须明确指定比例
- 图生视频时输入图片质量直接影响输出质量，建议上传高清图片
- 当指定 ratio 与上传图片比例不一致时，平台会**居中裁剪**
- 离线推理（flex）适合对时延不敏感的场景，建议将轮询间隔设为 60s
- Draft 样片仅支持 480p，Draft task ID 有效期 7 天
