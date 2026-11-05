"""Safe model catalog and administrator-only local credential configuration."""
import asyncio
from urllib.parse import quote
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, SecretStr, Field
from app.core.auth import current_user, require_admin
from app.agents.opencode import OpenCodeConnection, _stream_reply
from app.paths import BACKEND_ROOT

router=APIRouter(prefix='/api/conversation-settings',tags=['conversation-settings'])

async def catalog():
    try:
        async with OpenCodeConnection().client() as client:
            r=await client.get('/provider');r.raise_for_status();data=r.json()
        connected=set(data.get('connected',[]))
        return {'providers':[{'id':p['id'],'name':p.get('name',p['id']),
            'connected':p['id'] in connected,
            'models':[{'id':m['id'],'name':m.get('name',m['id'])} for m in p.get('models',{}).values()]} for p in data.get('all',[])]}
    except httpx.HTTPError as exc:
        raise HTTPException(503,'OpenCode 服务不可用，请启动服务。') from exc

@router.get('')
async def read_settings(user: str=Depends(current_user)):
    return await catalog()

class Credentials(BaseModel):
    provider: str=Field(min_length=1,max_length=200,pattern=r'^[A-Za-z0-9_.-]+$')
    api_key: SecretStr

class ModelTest(BaseModel):
    provider: str=Field(min_length=1,max_length=200,pattern=r'^[A-Za-z0-9_.-]+$')
    model: str=Field(min_length=1,max_length=500)

@router.put('/credentials')
async def save_credentials(request: Credentials, user: str=Depends(require_admin)):
    key=request.api_key.get_secret_value().strip()
    if not key or len(key)>16000: raise HTTPException(400,'API key 不能为空或过长')
    if request.provider not in {p['id'] for p in (await catalog())['providers']}:
        raise HTTPException(400,'未知模型供应商')
    try:
        async with OpenCodeConnection().client() as client:
            r=await client.put('/auth/'+quote(request.provider,safe=''),json={'type':'api','key':key})
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(503,'保存认证失败，请检查 OpenCode 服务。') from exc
    return {'saved':True,'note':'认证已保存到本机 OpenCode；尚未验证模型调用。'}

@router.post('/test')
async def test_model(request: ModelTest, user: str=Depends(require_admin)):
    providers={p['id']:p for p in (await catalog())['providers']}
    provider=providers.get(request.provider)
    if not provider or request.model not in {m['id'] for m in provider['models']}:
        raise HTTPException(400,'未知模型')
    if not provider['connected']:
        raise HTTPException(400,'请先保存该供应商的认证')
    connection=OpenCodeConnection()
    directory=str(BACKEND_ROOT)
    deny_all=[{'permission':'*','pattern':'*','action':'deny'}]
    session_id=None
    try:
        session_id=await connection.create(directory=directory,title='GUI-Anything connection test',permissions=deny_all)
        parts=[]
        async with asyncio.timeout(75):
            async for event in _stream_reply(connection,directory=directory,session_id=session_id,
                    text='Reply with exactly GUI_CONNECTION_OK. Do not use any tools.',
                    model={'providerID':request.provider,'modelID':request.model},permissions=deny_all):
                if event['kind'] in {'text_delta','text_snapshot'}: parts.append(event.get('text',''))
                if event['kind']=='error': raise RuntimeError(event['message'])
        if 'GUI_CONNECTION_OK' not in ''.join(parts):
            raise RuntimeError('模型已响应，但未通过固定回复校验')
    except TimeoutError as exc:
        raise HTTPException(504,'模型连接测试超时') from exc
    except (httpx.HTTPError,RuntimeError) as exc:
        raise HTTPException(503,f'模型连接测试失败：{exc}') from exc
    finally:
        if session_id:
            try:
                async with connection.client(directory) as client:
                    await client.delete(f'/session/{session_id}')
            except httpx.HTTPError:
                pass
    return {'ok':True,'note':'模型连接测试通过，可以在对话中使用。'}
