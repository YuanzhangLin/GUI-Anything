"""Synchronous topology-builder adapter backed by the managed OpenCode service."""
from __future__ import annotations

import asyncio
import httpx

from app.agents.opencode import OpenCodeConnection, _stream_reply
from app.paths import BACKEND_ROOT


class OpenCodeLLMClient:
    def __init__(self, model: dict[str, str]):
        self.model = dict(model)

    async def _call(self, prompt: str, system_prompt: str) -> str:
        connection = OpenCodeConnection()
        directory = str(BACKEND_ROOT)
        deny_all = [{'permission': '*', 'pattern': '*', 'action': 'deny'}]
        session_id = await connection.create(
            directory=directory,
            title='GUI-Anything Full Map analysis',
            permissions=deny_all,
        )
        parts: dict[str, str] = {}
        try:
            text = f"System instructions:\n{system_prompt}\n\nAnalysis input:\n{prompt}"
            async for event in _stream_reply(
                connection,
                directory=directory,
                session_id=session_id,
                text=text,
                model=self.model,
                permissions=deny_all,
            ):
                if event['kind'] == 'text_snapshot':
                    parts[event['part_id']] = event.get('text', '')
                elif event['kind'] == 'text_delta':
                    parts[event['part_id']] = parts.get(event['part_id'], '') + event.get('text', '')
                elif event['kind'] == 'error':
                    raise RuntimeError(event['message'])
            result = '\n'.join(parts.values()).strip()
            if not result:
                raise RuntimeError('OpenCode model returned no text for Full Map analysis')
            return result
        finally:
            try:
                async with connection.client(directory) as client:
                    await client.delete(f'/session/{session_id}')
            except httpx.HTTPError:
                pass

    def call_chat(self, prompt, system_prompt='You are a helpful assistant.', json_mode=False):
        if json_mode:
            system_prompt += '\nReturn one valid JSON object only, without markdown fences.'
        return asyncio.run(self._call(prompt, system_prompt))
