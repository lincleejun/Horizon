"""AI client that shells out to a locally logged-in Claude Code CLI."""

import asyncio
import os
import tempfile
from typing import Optional

from ..models import AIConfig
from .client import AIClient

CLAUDE_BIN = os.environ.get("HORIZON_CLAUDE_BIN", "claude")
TIMEOUT_SEC = 300


class ClaudeCLIClient(AIClient):
    """Run each completion as a one-shot `claude -p` call.

    Uses the CLI's own login, so no API key is needed. Prompts carry scraped,
    untrusted text, so the call runs with every tool disabled and without user
    settings, hooks, or MCP servers; that also keeps startup near two seconds.
    Temperature and max_tokens are not exposed by the CLI and are ignored.
    """

    def __init__(self, config: AIConfig):
        self.model = config.model

    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
        process = await asyncio.create_subprocess_exec(
            CLAUDE_BIN, "-p",
            "--model", self.model,
            "--tools", "",
            "--setting-sources", "",
            "--strict-mcp-config",
            "--system-prompt", system,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=tempfile.gettempdir(),
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(user.encode()), TIMEOUT_SEC
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError(f"claude CLI timed out after {TIMEOUT_SEC}s")
        text = stdout.decode().strip()
        if process.returncode != 0 or not text:
            detail = (stderr.decode().strip() or text)[:500]
            raise RuntimeError(f"claude CLI failed (exit {process.returncode}): {detail}")
        return text
