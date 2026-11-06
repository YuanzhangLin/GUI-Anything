"""Conservative AVD inventory and lifecycle for processes started by this service."""
import os, shutil, subprocess, threading, time
from pathlib import Path
from app.environment import diagnose
from app.local_services import discover_adb

_lock=threading.RLock();_managed={}

def emulator_path():
    report=diagnose();entry=next(x for x in report['items'] if x['id']=='emulator')
    return entry.get('path')

def _config(name):
    root=Path(os.getenv('ANDROID_AVD_HOME') or (Path(os.getenv('ANDROID_USER_HOME'))/'avd' if os.getenv('ANDROID_USER_HOME') else Path.home()/'.android'/'avd'))
    path=root/(name+'.avd')/'config.ini';data={}
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
        managed=set(_managed)
    avds=[]
    for name in names:
        config=_config(name);image=config.get('image.sysdir.1','')
        api=next((part[8:] for part in image.replace('\\','/').split('/') if part.startswith('android-')),None)
        avds.append({'name':name,'api':api,'image':image or None,'status':'running' if name in running else 'stopped',
                     'serial':running.get(name,{}).get('serial'),'state':running.get(name,{}).get('state'),'managed':name in managed})
    return {'emulator_available':bool(emulator),'adb_available':bool(adb),'avds':avds,'devices':_devices(adb)}

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
    if not avd or avd['status']!='running':raise ValueError('AVD is not running')
    with _lock:
        if name not in _managed:raise ValueError('Refusing to stop an emulator not started by GUI-Anything')
    adb=discover_adb()
    if not avd.get('serial') or not adb:raise ValueError('Managed emulator serial is unavailable')
    result=subprocess.run([adb,'-s',avd['serial'],'emu','kill'],capture_output=True,timeout=10)
    if result.returncode:raise RuntimeError(result.stderr.decode('utf-8','replace') or 'Emulator shutdown failed')
    return {'name':name,'status':'stopping'}
