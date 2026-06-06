"""Custom subprocess transport for Windows that bypasses anyio's broken subprocess support."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import re
import shutil
from collections.abc import AsyncIterator
from pathlib import Path
from subprocess import PIPE, Process as SubprocessProcess
from typing import Any, Callable

from ..._errors import CLIConnectionError, CLINotFoundError

logger = logging.getLogger(__name__)

_DEFAULT_MAX_BUFFER_SIZE = 1024 * 1024  # 1MB buffer limit


def _find_bundled_cli() -> str | None:
    """Find bundled CLI binary if it exists."""
    cli_name = "claude.exe" if platform.system() == "Windows" else "claude"
    bundled_path = Path(__file__).parent.parent.parent / "_bundled" / cli_name
    if bundled_path.exists() and bundled_path.is_file():
        logger.info(f"Using bundled Claude Code CLI: {bundled_path}")
        return str(bundled_path)
    return None


def _find_system_cli() -> str:
    """Find Claude Code CLI binary."""
    # First try bundled
    if bundled := _find_bundled_cli():
        return bundled

    # Fall back to system-wide search
    if cli := shutil.which("claude"):
        return cli

    locations = [
        Path.home() / ".npm-global/bin/claude",
        Path("/usr/local/bin/claude"),
        Path.home() / ".local/bin/claude",
        Path.home() / "node_modules/.bin/claude",
        Path.home() / ".yarn/bin/claude",
        Path.home() / ".claude/local/claude",
    ]

    for path in locations:
        if path.exists() and path.is_file():
            return str(path)

    raise CLINotFoundError(
        "Claude Code not found. Install with:\n"
        "  npm install -g @anthropic-ai/claude-code\n"
        "\nIf already installed locally, try:\n"
        '  export PATH="$HOME/node_modules/.bin:$PATH"\n'
        "\nOr provide the path via ClaudeAgentOptions:\n"
        "  ClaudeAgentOptions(cli_path='/path/to/claude')"
    )


async def _read_stream(stream: asyncio.StreamReader) -> AsyncIterator[str]:
    """Read lines from an async stream."""
    while True:
        try:
            line = await stream.readline()
            if not line:
                break
            yield line.decode("utf-8", errors="replace")
        except Exception:
            break


class WindowsSubprocessTransport:
    """A subprocess transport that uses subprocess.Popen directly on Windows.

    This bypasses the broken anyio.open_process() on Windows Python 3.12 which
    raises NotImplementedError in ProactorEventLoop._make_subprocess_transport.
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

        self._process: SubprocessProcess | None = None
        self._stdin_writer: asyncio.StreamWriter | None = None
        self._stdout_reader: asyncio.StreamReader | None = None
        self._stderr_reader: asyncio.StreamReader | None = None
        self._ready = False
        self._closed = False

        # For reading stdout in async context
        self._stdout_queue: asyncio.Queue[str] | None = None
        self._stdout_task: asyncio.Task | None = None
        self._stderr_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Start the subprocess using subprocess.Popen."""
        if self._process is not None:
            return

        try:
            # Use asyncio subprocess directly with Popen-style creation
            # Create the process with stdin/stdout/stderr pipes
            self._process = await asyncio.create_subprocess_exec(
                *self._cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._cwd,
                env=self._env,
                creationflags=0x08000000 if platform.system() == "Windows" else 0,  # CREATE_NO_WINDOW
            )

            # Get the streams
            assert self._process.stdin is not None
            assert self._process.stdout is not None
            assert self._process.stderr is not None

            self._stdin_writer = self._process.stdin
            self._stdout_reader = self._process.stdout
            self._stderr_reader = self._process.stderr

            # Create queue for stdout reading
            self._stdout_queue = asyncio.Queue(maxsize=100)

            # Start reading stdout in background
            self._stdout_task = asyncio.create_task(self._read_stdout())
            self._stderr_task = asyncio.create_task(self._read_stderr())

            self._ready = True
            logger.info(f"Started Claude Code subprocess with PID: {self._process.pid}")

        except FileNotFoundError as e:
            raise CLIConnectionError(f"Claude Code not found at: {self._cmd[0]}") from e
        except Exception as e:
            raise CLIConnectionError(f"Failed to start Claude Code: {e}") from e

    async def _read_stdout(self) -> None:
        """Background task to read stdout and put lines in queue."""
        if self._stdout_reader is None or self._stdout_queue is None:
            return

        try:
            while True:
                line = await self._stdout_reader.readline()
                if not line:
                    break
                await self._stdout_queue.put(line.decode("utf-8", errors="replace"))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"stdout read error: {e}")

    async def _read_stderr(self) -> None:
        """Background task to read stderr (just discard)."""
        if self._stderr_reader is None:
            return

        try:
            while True:
                line = await self._stderr_reader.readline()
                if not line:
                    break
                # Discard stderr output but could log it in debug mode
                logger.debug(f"claude stderr: {line.decode('utf-8', errors='replace').strip()}")
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def write(self, data: str) -> None:
        """Write data to subprocess stdin."""
        if self._stdin_writer is None or self._closed:
            raise RuntimeError("Transport not connected or closed")

        try:
            self._stdin_writer.write(data.encode("utf-8"))
            await self._stdin_writer.drain()
        except BrokenPipeError:
            raise CLIConnectionError("Subprocess stdin closed unexpectedly")
        except Exception as e:
            raise CLIConnectionError(f"Failed to write to subprocess: {e}") from e

    def read_messages(self) -> AsyncIterator[dict[str, Any]]:
        """Read JSON messages from subprocess stdout."""
        if self._stdout_queue is None:
            raise RuntimeError("Transport not connected")

        async def _gen():
            while True:
                try:
                    line = await asyncio.wait_for(self._stdout_queue.get(), timeout=1.0)
                    if not line:
                        continue
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        logger.debug(f"Non-JSON line from claude: {line[:100]}")
                        continue
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"read_messages error: {e}")
                    break

        return _gen()

    async def close(self) -> None:
        """Close the transport and terminate the subprocess."""
        if self._closed:
            return

        self._closed = True
        self._ready = False

        # Cancel background tasks
        if self._stdout_task and not self._stdout_task.done():
            self._stdout_task.cancel()
            try:
                await self._stdout_task
            except asyncio.CancelledError:
                pass

        if self._stderr_task and not self._stderr_task.done():
            self._stderr_task.cancel()
            try:
                await self._stderr_task
            except asyncio.CancelledError:
                pass

        # Terminate the process
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
        return self._ready and self._process is not None and self._process.returncode is None

    async def end_input(self) -> None:
        """Close stdin to signal end of input."""
        if self._stdin_writer is not None:
            try:
                self._stdin_writer.close()
                await self._stdin_writer.wait_closed()
            except Exception:
                pass


async def create_windows_transport(
    cmd: list[str],
    cwd: str | None,
    env: dict[str, str],
) -> WindowsSubprocessTransport:
    """Create a Windows-compatible subprocess transport."""
    transport = WindowsSubprocessTransport(cmd, cwd, env)
    await transport.connect()
    return transport