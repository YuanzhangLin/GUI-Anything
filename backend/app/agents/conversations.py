"""Authenticated local-to-upstream session binding and single-writer streaming."""
import asyncio
import json
import sqlite3
from contextlib import closing
from pathlib import Path
import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app.agents.opencode import OpenCodeConnection, stream_reply

_active = set()
_tasks = {}


def connection_db(path):
    connection = sqlite3.connect(path)
    connection.execute('CREATE TABLE IF NOT EXISTS agent_sessions (local_id TEXT PRIMARY KEY, owner TEXT NOT NULL, app_id TEXT NOT NULL, directory TEXT NOT NULL, remote_id TEXT NOT NULL)')
    connection.execute('CREATE TABLE IF NOT EXISTS conversation_events (seq INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
    connection.execute('CREATE INDEX IF NOT EXISTS conversation_events_session ON conversation_events(session_id, seq)')
    connection.commit()
    return connection


def binding(path, session_id, owner):
    with closing(connection_db(path)) as connection:
        row = connection.execute('SELECT owner,app_id,directory,remote_id FROM agent_sessions WHERE local_id=?',(session_id,)).fetchone()
    if row and row[0] != owner: raise HTTPException(403,'Session belongs to another user')
    return row


def record_event(path, session_id, event):
    with closing(connection_db(path)) as connection:
        cursor = connection.execute('INSERT INTO conversation_events(session_id,payload) VALUES (?,?)', (session_id, json.dumps(event, ensure_ascii=False)))
        connection.commit()
        return {**event, 'seq': cursor.lastrowid}


def read_events(path, session_id, owner, after=0):
    if not binding(path, session_id, owner): raise HTTPException(404, 'No OpenCode session')
    with closing(connection_db(path)) as connection:
        rows = connection.execute('SELECT seq,payload FROM conversation_events WHERE session_id=? AND seq>? ORDER BY seq LIMIT 500', (session_id,after)).fetchall()
    return {'events': [{**json.loads(payload), 'seq': seq} for seq,payload in rows],
            'running': session_id in _active, 'has_more': len(rows) == 500,
            'recovery_required': session_id not in _active and unfinished_turn(path,session_id) is not None}


def unfinished_turn(path, session_id):
    with closing(connection_db(path)) as connection:
        rows = connection.execute('SELECT seq,payload FROM conversation_events WHERE session_id=? ORDER BY seq', (session_id,)).fetchall()
    start = None
    parts = {}
    for seq,payload in rows:
        event = json.loads(payload)
        if event['kind'] == 'turn_started':
            start = seq
            parts = {}
        elif event['kind'] == 'turn_finished': start = None
        elif start is not None and event['kind'] == 'text_snapshot': parts[event['part_id']] = event['text']
        elif start is not None and event['kind'] == 'text_delta': parts[event['part_id']] = parts.get(event['part_id'],'') + event['text']
    return (start, '\n\n'.join(parts.values())) if start is not None else None


async def recover_interrupted(path, session_id, row):
    pending = unfinished_turn(path,session_id)
    if not pending: return False
    try:
        await OpenCodeConnection().abort(directory=row[2],session_id=row[3])
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 404:
            raise HTTPException(503,'无法确认遗留执行已停止，请恢复 OpenCode 服务后重试') from exc
    except httpx.HTTPError as exc:
        raise HTTPException(503,'无法确认遗留执行已停止，请恢复 OpenCode 服务后重试') from exc
    from app.agents.device_tools import finish_bound_task
    finish_bound_task(path,session_id,row[0])
    message = '后端曾中断；已停止遗留执行。以下保留中断前收到的内容，可发送新消息继续。'
    with closing(connection_db(path)) as connection:
        connection.execute('INSERT INTO messages(session_id,role,content) VALUES (?,?,?)',(session_id,'assistant',pending[1]+'\n\n'+message))
        for event in [{'kind':'interrupted','message':message},{'kind':'turn_finished'}]:
            connection.execute('INSERT INTO conversation_events(session_id,payload) VALUES (?,?)',(session_id,json.dumps(event,ensure_ascii=False)))
        connection.commit()
    return True


async def stop(path, session_id, owner):
    row = binding(path,session_id,owner)
    if not row: raise HTTPException(404,'No OpenCode session')
    if session_id not in _active:
        _active.add(session_id)
        try: await recover_interrupted(path,session_id,row)
        finally: _active.discard(session_id)
    else:
        await OpenCodeConnection().abort(directory=row[2],session_id=row[3])
    return {'status':'stop_requested'}


async def chat(path, request, owner, directory):
    if request.username != owner: raise HTTPException(403,'Session belongs to another user')
    if request.session_id in _active: raise HTTPException(409,'Conversation is already running')
    if not Path(directory).is_dir(): raise HTTPException(409,'Project source is unavailable')
    if request.model:
        from app.agents.settings import catalog
        providers = (await catalog())['providers']
        provider = next((p for p in providers if p['id'] == request.model.providerID), None)
        if not provider or request.model.modelID not in {m['id'] for m in provider['models']}:
            raise HTTPException(400, '所选模型不在服务提供的模型列表中')
        if not provider['connected']:
            raise HTTPException(409, '所选供应商尚未连接，请先配置认证')
    if request.session_id in _active: raise HTTPException(409, 'Conversation is already running')
    _active.add(request.session_id)
    upstream = OpenCodeConnection()
    device_run = None
    try:
        with closing(connection_db(path)) as connection:
            existing = connection.execute('SELECT username,app_id FROM sessions WHERE id=?',(request.session_id,)).fetchone()
            if existing and existing != (owner, request.app_id): raise HTTPException(403,'Conversation owner or project does not match')
        row = binding(path,request.session_id,owner)
        if row and (row[1] != request.app_id or row[2] != directory): raise HTTPException(409,'Create a new conversation for this project')
        if not row:
            remote = await upstream.create(directory=directory,title=request.message[:80])
            with closing(connection_db(path)) as connection:
                connection.execute('INSERT INTO agent_sessions VALUES (?,?,?,?,?)',(request.session_id,owner,request.app_id,directory,remote))
                connection.commit()
        else:
            await recover_interrupted(path,request.session_id,row)
            remote = row[3]
        from app.agents.device_tools import prepare_task
        device_run = prepare_task(path, request.session_id, owner, request.app_id, getattr(request,'device_task',None))
        with closing(connection_db(path)) as connection:
            connection.execute('INSERT OR IGNORE INTO sessions(id,title,username,app_id) VALUES (?,?,?,?)',(request.session_id,request.message[:30],owner,request.app_id))
            connection.execute('INSERT INTO messages(session_id,role,content) VALUES (?,?,?)',(request.session_id,'user',request.message))
            connection.commit()
    except BaseException as exc:
        _active.discard(request.session_id)
        if device_run:
            from app.agents.device_tools import finish_task
            finish_task(device_run)
        if isinstance(exc,ValueError): raise HTTPException(409,str(exc)) from exc
        if isinstance(exc,httpx.HTTPError): raise HTTPException(503,'OpenCode 服务不可用，请启动或检查服务连接。') from exc
        raise

    start = record_event(path, request.session_id, {'kind': 'turn_started', 'run_id': device_run['id'] if device_run else None})

    async def produce():
        parts = {}
        failure = ''
        try:
            screenshot=getattr(request,'device_screenshot',None)
            attachments=[{'type':'file','mime':'image/png','filename':'current-device.png','url':screenshot}] if screenshot else None
            async for event in stream_reply(upstream,directory=directory,session_id=remote,text=request.message + ("\n\nA device task is bound to this turn. Use gui_device to observe before acting. Target: " + json.dumps(device_run['target'],ensure_ascii=False) + ". Use independent baseline/after/assertions tools for verification; do not claim a pass from narration." if device_run else "\n\nNo device task is bound to this turn; do not operate a device."),model=request.model.model_dump() if request.model else None,attachments=attachments):
                if event['kind'] == 'text_snapshot': parts[event['part_id']] = event['text']
                elif event['kind'] == 'text_delta': parts[event['part_id']] = parts.get(event['part_id'],'') + event['text']
                elif event['kind'] == 'error': failure = event['message']
                event = record_event(path, request.session_id, event)

        except asyncio.CancelledError:
            failure = '连接已中断，已请求停止。'
            record_event(path,request.session_id,{'kind':'interrupted','message':failure})
            raise
        except (httpx.HTTPError, RuntimeError, ValueError):
            failure = 'OpenCode 连接中断或超过五分钟时限，请检查模型和网络后重试。'
            event = record_event(path, request.session_id, {'kind':'error','message':failure})

        except Exception:
            failure = '执行发生内部错误，已结束本轮；请检查服务日志。'
            record_event(path,request.session_id,{'kind':'error','message':failure})
        finally:
            try:
                from app.agents.device_tools import finish_task
                finish_task(device_run)
                content = '\n\n'.join(parts.values())
                if failure: content += '\n\n'+failure
                with closing(connection_db(path)) as connection:
                    connection.execute('INSERT INTO messages(session_id,role,content) VALUES (?,?,?)',(request.session_id,'assistant',content))
                    connection.execute('INSERT INTO conversation_events(session_id,payload) VALUES (?,?)',(request.session_id,json.dumps({'kind':'turn_finished'})))
                    connection.commit()
            finally:
                _active.discard(request.session_id)
                _tasks.pop(request.session_id, None)

    task = asyncio.create_task(produce(), name='conversation-' + request.session_id)
    _tasks[request.session_id] = task

    async def events():
        after = start['seq'] - 1
        while True:
            page = read_events(path,request.session_id,owner,after)
            for event in page['events']:
                after = event['seq']
                yield json.dumps(event,ensure_ascii=False)+'\n'
                if event['kind'] == 'turn_finished': return
            if not page['running'] and not page['has_more']: return
            if not page['has_more']: await asyncio.sleep(.15)

    return StreamingResponse(events(),media_type='application/x-ndjson',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
