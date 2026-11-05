"""OpenCode server connection, independent of UI and device execution."""
import os
import httpx
from app.agents.contracts import Capabilities

class OpenCodeConnection:
    capabilities = Capabilities(persistent_sessions=True, streaming_text=True,
                                tool_events=True, cancellation=True, model_selection=True)

    def __init__(self, base_url=None):
        self.base_url = base_url or os.getenv('GUI_OPENCODE_URL', 'http://127.0.0.1:4096')

    def client(self, directory=None):
        password = os.getenv('OPENCODE_SERVER_PASSWORD')
        auth = (os.getenv('OPENCODE_SERVER_USERNAME', 'opencode'), password) if password else None
        return httpx.AsyncClient(base_url=self.base_url, auth=auth,
            params={'directory': directory} if directory else None,
            timeout=30, trust_env=False)

    async def health(self):
        async with self.client() as client:
            response = await client.get('/global/health')
            response.raise_for_status()
            return response.json()

    @staticmethod
    def permissions():
        rules = [{'permission': '*', 'pattern': '*', 'action': 'deny'}]
        rules += [{'permission': name, 'pattern': '*', 'action': 'allow'}
                  for name in ['read', 'glob', 'grep', 'list', 'gui_device']]
        return rules

    async def create(self, *, directory, title, permissions=None):
        rules = self.permissions() if permissions is None else permissions
        async with self.client(directory) as client:
            response = await client.post('/session', json={'title': title, 'permission': rules})
            response.raise_for_status()
            return response.json()['id']

    async def abort(self, *, directory, session_id):
        async with self.client(directory) as client:
            response = await client.post(f'/session/{session_id}/abort')
            response.raise_for_status()

class EventNormalizer:
    def __init__(self, session_id):
        self.session_id = session_id
        self.assistants = set()

    def accept(self, event):
        kind, p = event.get('type'), event.get('properties', {})
        if p.get('sessionID') != self.session_id:
            return None
        if kind == 'message.updated':
            info = p.get('info', {})
            if info.get('role') == 'assistant': self.assistants.add(info['id'])
        if kind == 'message.part.updated':
            part = p['part']
            if part.get('messageID') not in self.assistants: return None
            if part['type'] == 'text': return {'kind':'text_snapshot','part_id':part['id'],'text':part.get('text','')}
            if part['type'] == 'tool': return {'kind':'tool','part_id':part['id'],'tool':part.get('tool'),'state':part.get('state',{}).get('status')}
        if kind == 'message.part.delta' and p.get('messageID') in self.assistants and p.get('field') == 'text':
            return {'kind':'text_delta','part_id':p['partID'],'text':p['delta']}
        if kind == 'session.error':
            error=p.get('error') or {}
            data=error.get('data') if isinstance(error,dict) else {}
            detail=(data or {}).get('message') or (error.get('message') if isinstance(error,dict) else None)
            if not isinstance(detail,str) or not detail.strip(): detail='OpenCode 执行失败，请检查模型配置与服务日志。'
            return {'kind':'error','message':detail[:1000]}
        if kind == 'session.idle': return {'kind':'done'}
        if kind == 'session.status': return {'kind':'status','status':p.get('status',{}).get('type')}


async def _stream_reply(connection, *, directory, session_id, text, model=None, permissions=None, attachments=None):
    import json
    import asyncio
    normalizer = EventNormalizer(session_id)
    completed = False
    try:
        async with connection.client(directory) as client:
            rules = connection.permissions() if permissions is None else permissions
            configured = await client.patch(f'/session/{session_id}', json={'permission':rules})
            configured.raise_for_status()
            async with client.stream('GET', '/event', timeout=httpx.Timeout(30, read=90)) as stream:
                stream.raise_for_status()
                # Subscribe before dispatch so the initial assistant metadata is retained.
                body = {'parts':[{'type':'text','text':text},*(attachments or [])]}
                if model: body['model'] = model
                response = await client.post(f'/session/{session_id}/prompt_async', json=body)
                response.raise_for_status()
                async for line in stream.aiter_lines():
                    if not line.startswith('data:'): continue
                    event = normalizer.accept(json.loads(line[5:]))
                    if event:
                        yield event
                        if event['kind'] in {'done','error'}:
                            completed = True
                            return
                raise RuntimeError('OpenCode disconnected before completion')
    finally:
        if not completed:
            try: await asyncio.shield(connection.abort(directory=directory,session_id=session_id))
            except httpx.HTTPError: pass


async def stream_reply(connection, *, directory, session_id, text, model=None, attachments=None):
    import asyncio
    try:
        async with asyncio.timeout(300):
            async for event in _stream_reply(connection, directory=directory,
                    session_id=session_id, text=text, model=model, attachments=attachments):
                yield event
    except TimeoutError as exc:
        raise RuntimeError('OpenCode generation exceeded the five-minute limit') from exc
