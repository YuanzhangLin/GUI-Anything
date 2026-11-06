"""Conservative AVD inventory and lifecycle for processes started by this service."""
import os, shutil, subprocess, threading, time
import re
from pathlib import Path
from app.environment import diagnose
from app.local_services import discover_adb

_lock=threading.RLock();_managed={}

def emulator_path():
    report=diagnose();entry=next(x for x in report['items'] if x['id']=='emulator')
    return entry.get('path')

def _tool(name):
    report=diagnose();manager=next((x.get('path') for x in report['items'] if x['id']=='sdkmanager'),None)
    if not manager:return None
    suffix='.bat' if os.name=='nt' else ''
    candidate=Path(manager).parent/(name+suffix)
    return str(candidate) if candidate.is_file() else shutil.which(name)

def system_images():
    manager=_tool('sdkmanager')
    if not manager:return {'available':False,'images':[],'reason':'SDK Manager is unavailable'}
    result=subprocess.run([manager,'--list'],capture_output=True,timeout=90)
    if result.returncode:raise RuntimeError(result.stderr.decode('utf-8','replace') or 'SDK Manager list failed')
    images=[];section=''
    for line in result.stdout.decode('utf-8','replace').splitlines():
        if line.strip() in {'Installed packages:','Available Packages:'}:section=line.strip()
        match=re.match(r'\s*(system-images;android-(\d+);([^;]+);([^\s|]+))\s*\|',line)
        if match:
            existing=next((x for x in images if x['id']==match.group(1)),None)
            if existing:existing['installed']=existing['installed'] or section=='Installed packages:'
            else:images.append({'id':match.group(1),'api':match.group(2),'tag':match.group(3),'abi':match.group(4),'installed':section=='Installed packages:'})
    return {'available':True,'images':images}

def create(name,image,device='pixel',install=False):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',name):raise ValueError('Invalid AVD name')
    if not re.fullmatch(r'system-images;android-\d+;[A-Za-z0-9_.-]+;[A-Za-z0-9_.-]+',image):raise ValueError('Invalid system image')
    if any(x['name']==name for x in inventory()['avds']):raise ValueError('AVD name already exists')
    images=system_images()['images'];selected=next((x for x in images if x['id']==image),None)
    if not selected:raise ValueError('System image is not offered by this SDK')
    manager=_tool('sdkmanager');avdmanager=_tool('avdmanager')
    if not avdmanager:raise ValueError('AVD Manager is unavailable')
    if not selected['installed']:
        if not install:raise ValueError('System image is not installed')
        result=subprocess.run([manager,image],input=b'y\n',capture_output=True,timeout=1800)
        if result.returncode:raise RuntimeError(result.stderr.decode('utf-8','replace') or 'System image installation failed')
    result=subprocess.run([avdmanager,'create','avd','--name',name,'--package',image,'--device',device],input=b'no\n',capture_output=True,timeout=90)
    if result.returncode:raise RuntimeError(result.stderr.decode('utf-8','replace') or result.stdout.decode('utf-8','replace'))
    return next(x for x in inventory()['avds'] if x['name']==name)

def erase(name):
    current=inventory();avd=next((x for x in current['avds'] if x['name']==name),None)
    if not avd:raise ValueError('Unknown AVD')
    if avd['status']=='running':raise ValueError('Close the AVD before clearing its data')
    directory=(_avd_root()/(name+'.avd')).resolve()
    if directory.parent!=_avd_root().resolve() or not directory.is_dir():raise ValueError('AVD data directory is unavailable')
    for filename in ['userdata-qemu.img','userdata-qemu.img.qcow2','cache.img','cache.img.qcow2','encryptionkey.img']:
        (directory/filename).unlink(missing_ok=True)
    snapshots=directory/'snapshots'
    if snapshots.is_dir():shutil.rmtree(snapshots)
    return {'name':name,'status':'data_cleared'}

def delete(name):
    current=inventory();avd=next((x for x in current['avds'] if x['name']==name),None)
    if not avd:raise ValueError('Unknown AVD')
    if avd['status']=='running':raise ValueError('Close the AVD before deleting it')
    manager=_tool('avdmanager')
    if not manager:raise ValueError('AVD Manager is unavailable')
    result=subprocess.run([manager,'delete','avd','--name',name],capture_output=True,timeout=30)
    if result.returncode:raise RuntimeError(result.stderr.decode('utf-8','replace') or 'AVD deletion failed')
    return {'name':name,'status':'deleted'}

def _avd_root():
    return Path(os.getenv('ANDROID_AVD_HOME') or (Path(os.getenv('ANDROID_USER_HOME'))/'avd' if os.getenv('ANDROID_USER_HOME') else Path.home()/'.android'/'avd'))

def _config(name):
    path=_avd_root()/(name+'.avd')/'config.ini';data={}
    if path.is_file():
        for line in path.read_text(encoding='utf-8',errors='replace').splitlines():
            if '=' in line:
                key,value=line.split('=',1);data[key.strip()]=value.strip()
    return data

def _devices(adb):
    if not adb:return []
    result=subprocess.run([adb,'devices','-l'],capture_output=True,timeout=10)
    found=[]
    for line in result.stdout.decode().splitlines()[1:]:
        parts=line.split()
        if len(parts)>=2:found.append({'serial':parts[0],'state':parts[1],'details':' '.join(parts[2:])})
    return found

def _avd_name(adb,serial):
    try:
        result=subprocess.run([adb,'-s',serial,'emu','avd','name'],capture_output=True,timeout=5)
        lines=[x.strip() for x in result.stdout.decode('utf-8','replace').splitlines() if x.strip() and x.strip()!='OK']
        return lines[0] if result.returncode==0 and lines else None
    except (OSError,subprocess.SubprocessError):return None

def _process_usage(pid):
    try:
        if os.name=='nt':
            command=['powershell','-NoProfile','-Command',f"$p=Get-Process -Id {int(pid)} -ErrorAction Stop; [pscustomobject]@{{memory_mb=[math]::Round($p.WorkingSet64/1MB,1);cpu_seconds=[math]::Round($p.CPU,1)}} | ConvertTo-Json -Compress"]
            result=subprocess.run(command,capture_output=True,timeout=5)
            if result.returncode==0:
                import json
                return json.loads(result.stdout.decode('utf-8','replace'))
        else:
            result=subprocess.run(['ps','-o','rss=,time=','-p',str(pid)],capture_output=True,timeout=5)
            parts=result.stdout.decode().split()
            if result.returncode==0 and len(parts)>=2:return {'memory_mb':round(int(parts[0])/1024,1),'cpu_time':parts[1]}
    except (OSError,ValueError,subprocess.SubprocessError):pass
    return None

def inventory():
    emulator=emulator_path();adb=discover_adb();names=[]
    if emulator:
        result=subprocess.run([emulator,'-list-avds'],capture_output=True,timeout=10)
        if result.returncode==0:names=[x.strip() for x in result.stdout.decode().splitlines() if x.strip()]
    running={}
    for device in _devices(adb):
        if device['serial'].startswith('emulator-'):
            name=_avd_name(adb,device['serial'])
            if name:running[name]={**device,'avd_name':name}
    with _lock:
        for name,record in list(_managed.items()):
            if record['process'].poll() is not None:_managed.pop(name,None)
        managed={name:{'pid':record['process'].pid,'started_at':record['started_at']} for name,record in _managed.items()}
    avds=[]
    for name in names:
        config=_config(name);image=config.get('image.sysdir.1','')
        api=next((part[8:] for part in image.replace('\\','/').split('/') if part.startswith('android-')),None)
        record=managed.get(name);elapsed=time.time()-record['started_at'] if record else None
        status='running' if name in running else ('startup_timeout' if record and elapsed>=120 else 'starting' if record else 'stopped')
        avds.append({'name':name,'api':api,'image':image or None,'status':status,
                     'serial':running.get(name,{}).get('serial'),'state':running.get(name,{}).get('state'),'managed':bool(record),
                     'source':'gui-anything' if record else ('external' if name in running else None),
                     'pid':record['pid'] if record else None,'started_at':record['started_at'] if record else None,
                     'uptime_seconds':round(elapsed) if elapsed is not None else None,
                     'resources':_process_usage(record['pid']) if record else None})
    devices=[]
    for device in _devices(adb):
        name=next((n for n,value in running.items() if value['serial']==device['serial']),None)
        devices.append({**device,'avd_name':name,'source':'gui-anything' if name in managed else 'external'})
    return {'emulator_available':bool(emulator),'adb_available':bool(adb),'avds':avds,'devices':devices}

def start(name):
    current=inventory();avd=next((x for x in current['avds'] if x['name']==name),None)
    if not avd:raise ValueError('Unknown AVD')
    if avd['status']=='running':return avd
    executable=emulator_path()
    with _lock:
        process=subprocess.Popen([executable,'-avd',name,'-no-snapshot-save'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        _managed[name]={'process':process,'started_at':time.time()}
    return {'name':name,'status':'starting','managed':True,'pid':process.pid}

def stop(name):
    current=inventory();avd=next((x for x in current['avds'] if x['name']==name),None)
    if not avd or avd['status']=='stopped':raise ValueError('AVD is not running')
    with _lock:
        if name not in _managed:raise ValueError('Refusing to stop an emulator not started by GUI-Anything')
        if avd['status'] in {'starting','startup_timeout'}:
            process=_managed.pop(name)['process'];process.terminate()
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:process.kill();process.wait()
            return {'name':name,'status':'stopped'}
    adb=discover_adb()
    if not avd.get('serial') or not adb:raise ValueError('Managed emulator serial is unavailable')
    result=subprocess.run([adb,'-s',avd['serial'],'emu','kill'],capture_output=True,timeout=10)
    if result.returncode:raise RuntimeError(result.stderr.decode('utf-8','replace') or 'Emulator shutdown failed')
    return {'name':name,'status':'stopping'}
