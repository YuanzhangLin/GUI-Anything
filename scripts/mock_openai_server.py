"""Deterministic loopback OpenAI-compatible model for clean-machine CI acceptance."""
from __future__ import annotations

import json
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()


@app.get('/health')
def health():
    return {'ok': True}


def _needs_skill(messages: list[dict]) -> bool:
    return not any(message.get('role') == 'tool' for message in messages)


def _message(needs_skill: bool) -> tuple[dict, str]:
    if needs_skill:
        return ({
            'role': 'assistant',
            'content': None,
            'tool_calls': [{
                'id': 'clean_machine_skill_call',
                'type': 'function',
                'function': {'name': 'skill', 'arguments': json.dumps({'name': 'gui-anything'})},
            }],
        }, 'tool_calls')
    return ({'role': 'assistant', 'content': 'CLEAN_MACHINE_OK'}, 'stop')


@app.post('/v1/chat/completions')
async def chat(request: Request):
    payload = await request.json()
    model = payload.get('model', 'acceptance-model')
    message, finish_reason = _message(_needs_skill(payload.get('messages') or []))
    request_id = 'chatcmpl-' + uuid.uuid4().hex
    created = int(time.time())
    if not payload.get('stream'):
        return JSONResponse({
            'id': request_id,
            'object': 'chat.completion',
            'created': created,
            'model': model,
            'choices': [{'index': 0, 'message': message, 'finish_reason': finish_reason}],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
        })

    async def events():
        delta = {'role': 'assistant'}
        if message.get('tool_calls'):
            call = message['tool_calls'][0]
            delta['tool_calls'] = [{
                'index': 0, 'id': call['id'], 'type': 'function', 'function': call['function'],
            }]
        else:
            delta['content'] = message['content']
        first = {
            'id': request_id, 'object': 'chat.completion.chunk', 'created': created, 'model': model,
            'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}],
        }
        last = {
            'id': request_id, 'object': 'chat.completion.chunk', 'created': created, 'model': model,
            'choices': [{'index': 0, 'delta': {}, 'finish_reason': finish_reason}],
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
        }
        yield 'data: ' + json.dumps(first) + '\n\n'
        yield 'data: ' + json.dumps(last) + '\n\n'
        yield 'data: [DONE]\n\n'

    return StreamingResponse(events(), media_type='text/event-stream')
