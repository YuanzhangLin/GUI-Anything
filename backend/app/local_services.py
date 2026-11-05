"""Start the local backend and OpenCode with a private shared device bridge."""
import os
import json
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path
from app.paths import BACKEND_ROOT, DATA_DIR
from app.core.opencode_agent import executable_path

HICODE_PROVIDER={
    'npm':'@ai-sdk/openai',
    'name':'Hi-Code（中国站）',
    'options':{'baseURL':'https://api-cn.hi-code.cc/v1'},
    'models':{
        'gpt-5.6-sol':{'name':'GPT-5.6 Sol（推荐）'},
        'gpt-5.6':{'name':'GPT-5.6'},
        'gpt-5.5':{'name':'GPT-5.5'},
        'gpt-5.4':{'name':'GPT-5.4'},
        'gpt-5.4-mini':{'name':'GPT-5.4 Mini'},
    },
}


def discover_adb():
    configured=os.getenv('GUI_ADB_PATH') or shutil.which('adb')
    if configured: return configured
    roots=[os.getenv('ANDROID_SDK_ROOT'),os.getenv('ANDROID_HOME'),
           str(Path.home()/'AppData'/'Local'/'Android'/'Sdk'),r'D:\Android\Sdk']
    for root in filter(None,roots):
        candidate=Path(root)/'platform-tools'/'adb.exe'
        if candidate.is_file(): return str(candidate)
    return None


def main():
    executable=executable_path()
    if not executable: raise SystemExit('OpenCode executable is not installed')
    config=Path(DATA_DIR)/'runs'/'.opencode-service'
    tools=config/'tools';tools.mkdir(parents=True,exist_ok=True)
    template=Path(BACKEND_ROOT).parent/'agent-tools'/'opencode'/'gui_device.ts'
    shutil.copyfile(template,tools/'gui_device.ts')
    env={**os.environ,'GUI_AGENT_BRIDGE_TOKEN':secrets.token_urlsafe(48),
         'OPENCODE_SERVER_PASSWORD':secrets.token_urlsafe(48),
         'OPENCODE_CONFIG_DIR':str(config),'GUI_AGENT_BRIDGE_URL':'http://127.0.0.1:8002',
         'GUI_OPENCODE_URL':'http://127.0.0.1:4096',
         'OPENCODE_CONFIG_CONTENT':json.dumps({
             'permission':{'edit':'deny','bash':'deny'},
             'autoupdate':False,
             'provider':{'hicode':HICODE_PROVIDER},
         })}
    adb=discover_adb()
    if adb: env['GUI_ADB_PATH']=adb
    children=[]
    try:
        for command in [[executable,'serve','--hostname','127.0.0.1','--port','4096'],
                        [sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8002']]:
            children.append(subprocess.Popen(command,cwd=BACKEND_ROOT,env=env))
        print('Local services started; credentials remain in process memory.',flush=True)
        import httpx
        for attempt in range(30):
            try:
                with httpx.Client(auth=('opencode',env['OPENCODE_SERVER_PASSWORD']),trust_env=False,timeout=15) as client:
                    result=client.get('http://127.0.0.1:4096/experimental/tool/ids',params={'directory':BACKEND_ROOT})
                    result.raise_for_status()
                    schema=client.get('http://127.0.0.1:4096/doc')
                    schema.raise_for_status()
                    (config/'api-schema.json').write_text(json.dumps(schema.json()),encoding='utf-8')
                    loaded='gui_device' in result.json()
                    print('OpenCode device tool registered: '+str(loaded),flush=True)
                    if not loaded: raise RuntimeError('OpenCode did not register the device tool')
                    break
            except httpx.ConnectError:
                time.sleep(1)
        else: raise RuntimeError('OpenCode startup health timeout')
        while all(child.poll() is None for child in children): time.sleep(1)
        raise SystemExit('A service exited; stopping the paired service.')
    finally:
        for child in children:
            if child.poll() is None: child.terminate()
        for child in children:
            try: child.wait(timeout=10)
            except subprocess.TimeoutExpired: child.kill();child.wait()

if __name__=='__main__': main()
