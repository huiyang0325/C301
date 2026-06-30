"""
Windows-compatible subprocess patch for Python 3.12.

Patches asyncio.create_subprocess_exec to use create_subprocess_shell on Windows,
which avoids NotImplementedError in ProactorEventLoop._make_subprocess_transport.

This must be applied BEFORE the application imports asyncio.create_subprocess_exec.
"""

from __future__ import annotations

import asyncio
import logging
import platform
import shlex
import sys
from typing import Any

logger = logging.getLogger(__name__)

# Only apply on Windows
SHOULD_PATCH = platform.system() == "Windows"

# Store original
_original_create_subprocess_exec: Any = None


async def _patched_create_subprocess_exec(
    program: str,
    *args: Any,
    stdin: Any = None,
    stdout: Any = None,
    stderr: Any = None,
    limit: int = 65536,
    **kwds: Any,
) -> asyncio.subprocess.Process:
    """Patched version that uses create_subprocess_shell on Windows.

    The issue is that create_subprocess_exec triggers
    ProactorEventLoop._make_subprocess_transport which raises NotImplementedError
    on Windows Python 3.12.
    """
    if platform.system() != "Windows":
        return await _original_create_subprocess_exec(
            program, *args, stdin=stdin, stdout=stdout, stderr=stderr, limit=limit, **kwds
        )

    # Build command string for shell
    cmd_parts = [program] + list(args)
    if platform.system() == "Windows":
        # On Windows with cmd.exe, don't quote - just join with spaces
        cmd_str = ' '.join(str(arg) for arg in cmd_parts)
    else:
        # On Unix, use shlex.quote for safety
        cmd_str = ' '.join(shlex.quote(str(arg)) for arg in cmd_parts)

    # Use create_subprocess_shell instead
    return await asyncio.create_subprocess_shell(
        cmd_str,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        cwd=kwds.get('cwd'),
        env=kwds.get('env'),
        creationflags=kwds.get('creationflags', 0),
    )


def apply_patch() -> None:
    """Apply the Windows subprocess patch."""
    global _original_create_subprocess_exec

    if not SHOULD_PATCH:
        logger.info("Windows subprocess patch not needed")
        return

    # Store original and patch
    _original_create_subprocess_exec = asyncio.create_subprocess_exec
    asyncio.create_subprocess_exec = _patched_create_subprocess_exec

    logger.info("Windows subprocess patch loaded: create_subprocess_exec now uses create_subprocess_shell")


if __name__ == "__main__":
    print(f"Platform: {platform.system()}")
    print(f"Python: {sys.version_info}")
    print(f"Should patch: {SHOULD_PATCH}")
    if SHOULD_PATCH:
        apply_patch()
        print("Patch applied")

        # Test
        import asyncio
        from subprocess import PIPE

        async def test():
            print('Testing patched create_subprocess_exec...')
            proc = await asyncio.create_subprocess_exec(
                'cmd.exe', '/c', 'echo hello',
                stdin=PIPE, stdout=PIPE, stderr=PIPE
            )
            stdout, stderr = await proc.communicate()
            print(f'Result: returncode={proc.returncode}, stdout={stdout}')

        asyncio.run(test())
    else:
        print("Patch not needed")