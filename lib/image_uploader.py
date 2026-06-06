"""本地图片上传到图床，返回公网 URL。"""

import logging
from pathlib import Path

import httpx

from lib.retry import with_retry_async

logger = logging.getLogger(__name__)

IMGURL_BASE_URL = "https://www.imgurl.org"
IMGURL_TOKEN = "sk-aSH9QqtcuFcpdcYwoqcKhptxz1wztJujjRKUbb6vPJmJafvEhZW8KXkLZvY6P"


@with_retry_async(max_attempts=3, backoff_seconds=(1, 2, 4))
async def upload_image_to_imgurl(file_path: Path) -> str | None:
    """上传本地图片到 imgurl，返回公网 URL。"""
    file_path = Path(file_path)
    if not file_path.exists():
        logger.warning("上传文件不存在: %s", file_path)
        return None

    try:
        with open(file_path, "rb") as f:
            file_data = f.read()

        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            resp = await client.post(
                f"{IMGURL_BASE_URL}/api/v3/upload",
                files={"file": (file_path.name, file_data, "image/png")},
                headers={"Authorization": f"Bearer {IMGURL_TOKEN}"},
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("code") == 200:
            url = data["data"]["url"]
            logger.info("图片上传成功: %s -> %s", file_path.name, url)
            return url
        else:
            logger.warning("图片上传失败: %s", data.get("msg"))
            return None
    except Exception as e:
        logger.warning("图片上传异常: %s", e)
        return None


def upload_image_to_imgurl_sync(file_path: Path) -> str | None:
    """同步版本（供紧急情况同步调用）。"""
    import httpx

    file_path = Path(file_path)
    if not file_path.exists():
        return None

    try:
        with open(file_path, "rb") as f:
            file_data = f.read()

        resp = httpx.post(
            f"{IMGURL_BASE_URL}/api/v3/upload",
            files={"file": (file_path.name, file_data, "image/png")},
            headers={"Authorization": f"Bearer {IMGURL_TOKEN}"},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") == 200:
            return data["data"]["url"]
        return None
    except Exception:
        return None
