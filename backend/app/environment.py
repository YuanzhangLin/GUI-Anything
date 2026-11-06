"""Machine-readable local prerequisite diagnostics."""
import os, platform, re, shutil, subprocess
from pathlib import Path
from app.core.opencode_agent import executable_path
from app.local_services import discover_adb

def run(command):
    try:
        result=subprocess.run(command,capture_output=True,timeout=8)
        return result.returncode==0,(result.stdout+result.stderr).decode('utf-8','replace').strip()
    except (OSError,subprocess.SubprocessError) as exc:return False,str(exc)

def item(id,label,status,detail,fix='',**extra):
    return {'id':id,'label':label,'status':status,'detail':detail,'fix':fix or None,**extra}

def diagnose():
    system=platform.system();opencode=executable_path();adb=discover_adb()
    configured=os.getenv('ANDROID_SDK_ROOT') or os.getenv('ANDROID_HOME')
    sdk=Path(configured) if configured and Path(configured).is_dir() else (Path(adb).resolve().parent.parent if adb and Path(adb).resolve().parent.name=='platform-tools' else None)
    suffix='.exe' if system=='Windows' else ''
    emulator=shutil.which('emulator') or (str(sdk/'emulator'/('emulator'+suffix)) if sdk else None)
    emulator=emulator if emulator and Path(emulator).is_file() else None
    manager=shutil.which('sdkmanager') or (str(sdk/'cmdline-tools'/'latest'/'bin'/('sdkmanager.bat' if system=='Windows' else 'sdkmanager')) if sdk else None)
    manager=manager if manager and Path(manager).is_file() else None
    ok,version=run([opencode,'--version']) if opencode else (False,'')
    items=[item('opencode','OpenCode','ready' if ok else 'missing',version.splitlines()[0] if ok else '未找到可执行文件','安装兼容的 OpenCode，或使用后续提供的受管理版本。',path=opencode)]
    ok,version=run([adb,'version']) if adb else (False,'')
    items += [item('adb','Android Debug Bridge','ready' if ok else 'missing',version.splitlines()[0] if ok else '未找到 ADB','安装 Android SDK Platform-Tools，或设置 ANDROID_SDK_ROOT。',path=adb),
      item('android_sdk','Android SDK','ready' if sdk else 'missing',str(sdk) if sdk else '未识别 SDK 根目录','安装 Android SDK，并设置 ANDROID_SDK_ROOT。',path=str(sdk) if sdk else None),
      item('emulator','Android Emulator','ready' if emulator else 'missing',emulator or '未找到 Emulator','使用 SDK Manager 安装 Android Emulator。',path=emulator),
      item('sdkmanager','SDK Manager','ready' if manager else 'warning',manager or '无法自动安装系统镜像','安装 Android SDK Command-line Tools (latest)。',path=manager)]
    avds=[]
    if emulator:
        ok,output=run([emulator,'-list-avds']);avds=[x.strip() for x in output.splitlines() if x.strip()] if ok else []
    items.append(item('avd','Android Virtual Devices','ready' if avds else 'warning',f'发现 {len(avds)} 个 AVD' if avds else '没有可启动的 AVD','创建 AVD，或等待后续向导自动创建。',avds=avds))
    devices=[]
    if adb:
        ok,output=run([adb,'devices','-l']);devices=[x.split()[0] for x in output.splitlines()[1:] if len(x.split())>1 and x.split()[1]=='device'] if ok else []
    items.append(item('devices','已连接设备','ready' if devices else 'warning',f'{len(devices)} 台设备在线' if devices else '当前没有在线设备','启动 AVD 或连接 Android 设备。',devices=devices))
    free=round(shutil.disk_usage(Path.home()).free/1024**3,1)
    items.append(item('disk','磁盘空间','ready' if free>=12 else 'warning',f'剩余 {free} GiB','建议至少保留 12 GiB。',free_gib=free))
    memory=None
    if system=='Windows':
        ok,output=run(['powershell','-NoProfile','-Command','(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory']);match=re.search(r'\d+',output)
        if ok and match:memory=round(int(match.group())/1024**3,1)
    items.append(item('memory','物理内存','ready' if memory and memory>=8 else 'warning',f'{memory} GiB' if memory else '无法读取','运行 Emulator 建议至少 8 GiB。',total_gib=memory))
    virtual='unknown'
    if system=='Windows':
        ok,output=run(['powershell','-NoProfile','-Command','(Get-CimInstance Win32_Processor | Select-Object -First 1).VirtualizationFirmwareEnabled'])
        if ok and output.lower() in {'true','false'}:virtual='enabled' if output.lower()=='true' else 'disabled'
    items.append(item('virtualization','硬件虚拟化','ready' if virtual=='enabled' else 'warning','已启用' if virtual=='enabled' else '未确认启用','在 BIOS/UEFI 启用 VT-x 或 AMD-V。',value=virtual))
    required={'opencode','adb','android_sdk','emulator'}
    return {'schema_version':1,'platform':{'system':system,'release':platform.release(),'machine':platform.machine()},'status':'ready' if all(x['status']=='ready' for x in items if x['id'] in required) else 'needs_setup','items':items}
