#!/usr/bin/env python3
"""将 .env 中的 MiniMax API Key 注册到数据库作为活跃凭证。"""

import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))


async def register_minimax_credential():
    from lib.db import async_session_factory
    from lib.db.models.credential import ProviderCredential
    from sqlalchemy import select, update

    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        print("错误: MINIMAX_API_KEY 环境变量未设置")
        return

    print(f"MiniMax API Key: {api_key[:20]}...")

    async with async_session_factory() as session:
        # 检查是否已有 MiniMax 凭证
        stmt = select(ProviderCredential).where(
            ProviderCredential.provider == "minimax",
            ProviderCredential.is_active == True,  # noqa: E712
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"已有 MiniMax 活跃凭证 ID={existing.id}，更新 api_key...")
            existing.api_key = api_key
            await session.commit()
            print("更新成功")
        else:
            print("创建新的 MiniMax 凭证...")
            # 检查是否有未激活的凭证
            stmt2 = select(ProviderCredential).where(
                ProviderCredential.provider == "minimax"
            )
            result2 = await session.execute(stmt2)
            existing_any = result2.scalar_one_or_none()

            if existing_any:
                print(f"激活现有凭证 ID={existing_any.id}...")
                await session.execute(
                    update(ProviderCredential)
                    .where(ProviderCredential.provider == "minimax")
                    .values(api_key=api_key, is_active=True)
                )
            else:
                print("创建新凭证...")
                cred = ProviderCredential(
                    provider="minimax",
                    name="MiniMax API Key",
                    api_key=api_key,
                    is_active=True,
                )
                session.add(cred)
            await session.commit()

        # 验证
        stmt3 = select(ProviderCredential).where(
            ProviderCredential.provider == "minimax",
            ProviderCredential.is_active == True,  # noqa: E712
        )
        result3 = await session.execute(stmt3)
        active = result3.scalar_one_or_none()
        if active:
            print(f"成功: MiniMax 凭证已激活 (ID={active.id})")
        else:
            print("错误: 激活失败")


if __name__ == "__main__":
    import asyncio
    asyncio.run(register_minimax_credential())