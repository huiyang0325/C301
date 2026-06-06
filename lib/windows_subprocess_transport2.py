"""
Windows-compatible subprocess transport using asyncio.create_subprocess_shell.
Avoids asyncio.create_subprocess_exec() which triggers NotImplementedError
on Windows Python 3.12 ProactorEventLoop.

This transport uses create_subprocess_shell instead, which works correctly.
"""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import shlex
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_MAX_BUFFER_SIZE = 1024 * 1024  # 1MB buffer limit


class AsyncioSubprocessTransport:
    """A subprocess transport using asyncio.create_subprocess_shell on Windows.

    This bypasses the broken asyncio.create_subprocess_exec() on Windows
    Python 3.12 which raises NotImplementedError in ProactorEventLoop.
    """

    def __init__(
        self,
        cmd: list[str],
        cwd: str | None,
        env: dict[str, str],
        *,
        max_buffer_size: int = _DEFAULT_MAX_BUFFER_SIZE,
    ):
        self._cmd = cmd
        self._cwd = cwd
        self._env = env
        self._max_buffer_size = max_buffer_size

        self._process: asyncio.subprocess.Process | None = None
        self._closed = False

    def _build_command_string(self) -> str:
        """Build the shell command string from cmd list."""
        if platform.system() == "Windows":
            # On Windows, use cmd.exe syntax
            if len(self._cmd) == 1:
                return self._cmd[0]
            # Quote arguments properly for cmd.exe
            parts = []
            for arg in self._cmd:
                if ' ' in arg or '"' in arg:
                    # Escape quotes and wrap in quotes
                    escaped = arg.replace('"', '"')
                    parts.append(f'"{escaped}"')
                else:
                    parts.append(arg)
            return ' '.join(parts)
        else:
            # On Unix, use sh syntax
            return ' '.join(shlex.quote(arg) for arg in self._cmd)

    async def connect(self) -> None:
        """Start the subprocess using asyncio.create_subprocess_shell."""
        if self._process is not None:
            return

        try:
            cmd_str = self._build_command_string()
            logger.info(f"AsyncioSubprocessTransport: running '{cmd_str}'")

            # Use create_subprocess_shell which works on Windows Python 3.12
            # On Windows, passing env={} to create_subprocess_shell clears the entire
            # environment which breaks cmd.exe. We must merge with os.environ.
            # Check explicitly for None since {} is falsy but means "use env as-is".
            if self._env is not None:
                # Merge os.environ with self._env (self._env takes precedence)
                import os
                merged_env = {**os.environ, **self._env}
            else:
                merged_env = None  # Pass None to inherit full environment

            self._process = await asyncio.create_subprocess_shell(
                cmd_str,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._cwd,
                env=merged_env,
            )

            logger.info(f"AsyncioSubprocessTransport: started PID={self._process.pid}")
        except FileNotFoundError as e:
            raise RuntimeError(f"Executable not found: {self._cmd[0]}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to start subprocess: {e}") from e

    async def write(self, data: str) -> None:
        """Write data to subprocess stdin."""
        if self._process is None or self._process.stdin is None or self._closed:
            raise RuntimeError("Transport not connected or closed")

        self._process.stdin.write(data.encode("utf-8"))
        await self._process.stdin.drain()

    async def read_messages(self) -> AsyncIterator[dict[str, Any]]:
        """Read JSON messages from subprocess stdout."""
        if self._process is None or self._process.stdout is None:
            raise RuntimeError("Transport not connected")

        stdout = self._process.stdout
        while True:
            try:
                line = await asyncio.wait_for(stdout.readline(), timeout=60.0)
            except asyncio.TimeoutError:
                # Check if process is still alive
                if self._process.returncode is not None:
                    break
                continue
            except asyncio.CancelledError:
                break

            if not line:
                break

            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue

            try:
                yield json.loads(line_str)
            except json.JSONDecodeError:
                logger.debug(f"Non-JSON line from subprocess: {line_str[:100]}")

    async def close(self) -> None:
        """Close the transport and terminate the subprocess."""
        if self._closed:
            return

        self._closed = True

        if self._process is not None:
            try:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self._process.kill()
                    await self._process.wait()
            except Exception:
                pass
            self._process = None

    def is_ready(self) -> bool:
        """Check if transport is ready."""
        return (
            not self._closed
            and self._process is not None
            and self._process.returncode is None
        )

    async def end_input(self) -> None:
        """Close stdin to signal end of input."""
        if self._process is not None and self._process.stdin is not None:
            try:
                self._process.stdin.close()
                await self._process.stdin.wait_closed()
            except Exception:
                pass


async def create_asyncio_transport(
    cmd: list[str],
    cwd: str | None,
    env: dict[str, str],
) -> AsyncioSubprocessTransport:
    """Create a Windows-compatible subprocess transport using asyncio.create_subprocess_shell."""
    transport = AsyncioSubprocessTransport(cmd, cwd, env)
    await transport.connect()
    return transport


if __name__ == "__main__":
    # Test the transport
    async def test():
        transport = AsyncioSubprocessTransport(
            ["cmd.exe", "/c", "echo hello && echo {\"hello\":\"world\"}"],
            cwd=None,
            env={},
        )
        await transport.connect()
        async for msg in transport.read_messages():
            print(f"Received: {msg}")
        await transport.close()

    asyncio.run(test())