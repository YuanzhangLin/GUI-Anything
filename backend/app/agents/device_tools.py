"""Provider-neutral, session-bound Android tools for trusted Agent adapters."""
import hmac
import os
import sqlite3
from contextlib import closing
from typing import Literal
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict
from app.workbench.api import store, runtime, source, guarded
from app.workbench.runtime import Action

router=APIRouter(prefix='/api/agent-tools',tags=['agent-tools'])

class ToolCall(BaseModel):
    model_config=ConfigDict(extra='forbid')
    session_id: str
    operation: Literal['observe','act','baseline','after','assertions','status']
    action: Action | None = None


def bound_run(db_path, remote_session):
    from app.agents.conversations import connection_db, _active
    with closing(connection_db(db_path)) as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS conversation_runs (local_id TEXT PRIMARY KEY,run_id TEXT NOT NULL)')
        row=connection.execute('SELECT a.local_id,a.owner,r.run_id FROM agent_sessions a JOIN conversation_runs r ON a.local_id=r.local_id WHERE a.remote_id=?',(remote_session,)).fetchone()
    if not row: raise ValueError('No device task bound to this conversation')
    if row[0] not in _active: raise ValueError('Conversation is not actively executing')
    run=store().read(row[2],row[1])
    if runtime().state(run['id'])['status'] != 'running': raise ValueError('Device task is not running')
    return run


def execute_tool(db_path, call):
    run=bound_run(db_path,call.session_id)
    rt=runtime()
    import time
    state=rt.state(run['id'])
    if state.get('started') and time.time()-state['started']>=run['time_budget_seconds']:
        raise ValueError('Device task time budget exhausted')
    if call.operation=='status': return rt.state(run['id'])
    project=source(run['app_id'])
    if not store().check_source(run,project)['matches']: raise ValueError('Source version changed')
    if call.operation=='observe':
        try:
            return rt.observe(run)[1]
        except (RuntimeError, ValueError) as exc:
            rt.block(run['id'], exc)
            raise
    if call.operation=='act':
        if not call.action: raise ValueError('Action is required')
        return rt.step(run,call.action,lambda:store().check_source(run,project)['matches'])
    if call.operation in {'baseline','after'}:
        from app.workbench.coverage import Coverage
        return Coverage(rt,project).collect(run,call.operation)
    from app.workbench.assertions import evaluate
    return evaluate(run,rt)


@router.post('')
def call_tool(call: ToolCall, x_gui_agent_token: str | None = Header(default=None)):
    secret=os.getenv('GUI_AGENT_BRIDGE_TOKEN')
    if not secret or not x_gui_agent_token or not hmac.compare_digest(secret,x_gui_agent_token):
        raise HTTPException(401,'Agent adapter authentication required')
    from app.main import DB_PATH
    return guarded(lambda:execute_tool(DB_PATH,call))

def prepare_task(db_path, local_id, owner, app_id, request):
    from app.agents.conversations import connection_db
    from app.workbench.runtime import devices
    with closing(connection_db(db_path)) as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS conversation_runs (local_id TEXT PRIMARY KEY,run_id TEXT NOT NULL)')
        connection.execute('DELETE FROM conversation_runs WHERE local_id=?',(local_id,))
        connection.commit()
    if request is None: return None
    if not os.getenv('GUI_AGENT_BRIDGE_TOKEN'):
        raise ValueError('Device tool bridge is not configured on this backend')
    if not any(d['serial']==request.device_serial and d['state']=='device' for d in devices()['devices']):
        raise ValueError('Selected device is not connected')
    run=store().create(app_id,owner,source(app_id),request)
    runtime().control(run,'start')
    try:
        with closing(connection_db(db_path)) as connection:
            connection.execute('INSERT INTO conversation_runs VALUES (?,?)',(local_id,run['id']))
            connection.commit()
    except BaseException:
        runtime().control(run,'stop')
        raise
    return run


def finish_task(run):
    if run and runtime().state(run['id'])['status']!='stopped':
        runtime().control(run,'stop')


def finish_bound_task(db_path, local_id, owner):
    from app.agents.conversations import connection_db
    with closing(connection_db(db_path)) as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS conversation_runs (local_id TEXT PRIMARY KEY,run_id TEXT NOT NULL)')
        row=connection.execute('SELECT run_id FROM conversation_runs WHERE local_id=?',(local_id,)).fetchone()
    if row: finish_task(store().read(row[0],owner))
