"""JaCoCo collection with APK identity, class matching, and separate line verdicts."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
from app.navigation.device import AdbDevice
from app.workbench.runtime import lock
from app.paths import validate_app_id

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def compare_reports(before: Path, after: Path, package: str, filename: str, start: int, end: int):
    def read(path):
        root=ET.parse(path).getroot()
        source=root.find(f"package[@name='{package}']/sourcefile[@name='{filename}']")
        if source is None: raise ValueError("Target source absent from JaCoCo report")
        return {int(line.get("nr")):dict(line.attrib) for line in source.findall("line") if start<=int(line.get("nr"))<=end}
    baseline,final=read(before),read(after)
    if not final or set(baseline)!=set(final): raise ValueError("Target has no executable lines or coverage reports disagree")
    rows=[{"line":line,"before":baseline[line],"after":final[line],
           "newly_hit":int(baseline[line]["ci"])==0 and int(final[line]["ci"])>0,
           "new_branches":max(0,int(final[line]["cb"])-int(baseline[line]["cb"]))} for line in sorted(final)]
    return {"status":"passed" if all(row["newly_hit"] for row in rows) else "failed",
            "criterion":"Every executable selected line was uncovered at baseline and covered after execution",
            "lines":rows,"business_status":"not_checked"}

class Coverage:
    def __init__(self, runtime, source):
        self.runtime,self.source=runtime,source

    def config(self, app_id):
        directory=os.getenv("GUI_COVERAGE_CONFIG_DIR")
        if not directory: raise ValueError("Coverage is not configured: set GUI_COVERAGE_CONFIG_DIR")
        path=Path(directory)/(validate_app_id(app_id)+".json")
        config=json.loads(path.read_text(encoding="utf-8"))
        base=Path(os.getenv("GUI_COVERAGE_ROOT",str(path.parent))).resolve()
        for field in ["apk","class_files","source_files"]:
            config[field]=str((base/config[field]).resolve())
        config["java"]=os.getenv("GUI_JAVA_PATH","java")
        config["cli"]=os.getenv("GUI_JACOCO_CLI","")
        if not config["cli"]: raise ValueError("Set GUI_JACOCO_CLI to the matching JaCoCo CLI jar")
        for field in ["package","coverage_receiver"]:
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.$]*",config[field]): raise ValueError("Invalid coverage component configuration")
        return config

    def collect(self, run, label):
        if label not in {"baseline","after"}: raise ValueError("Unknown coverage phase")
        with lock(run["id"]),lock("device:"+str(run.get("device_serial"))):
            if not run.get("device_serial"): raise ValueError("Select a device first")
            state=self.runtime.state(run["id"])
            if state["status"] not in {"running","paused"}: raise ValueError("Start the Run before collecting coverage")
            config=self.config(run["app_id"])
            target=run["target"]
            current=self.source.read(target["path"])
            if current["file_sha256"]!=target["file_sha256"] or current["revision"]["commit"]!=target["revision"]["commit"]:
                raise ValueError("Target source changed")
            package=re.search(r"\bpackage\s+([\w.]+)\s*;",current["text"])
            if not package: raise ValueError("Java package not found for coverage target")
            package=package.group(1).replace(".","/")
            filename=Path(target["path"]).name
            matching_source=Path(config["source_files"])/package/filename
            if digest(matching_source)!=target["file_sha256"]: raise ValueError("Report source differs from frozen target")
            directory=self.runtime.root/run["id"]/"coverage"
            directory.mkdir(parents=True,exist_ok=True)
            if label=="after" and not (directory/"baseline/result.json").exists(): raise ValueError("Valid baseline required first")
            output=directory/label
            if output.exists(): raise ValueError("Coverage phase already attempted; evidence cannot be overwritten")
            device=AdbDevice(run["device_serial"])
            apk_path=device._run("shell","pm","path",config["package"]).decode().strip().splitlines()
            if len(apk_path)!=1 or not apk_path[0].startswith("package:"): raise ValueError("Expected one installed base APK")
            installed=hashlib.sha256(device._run("exec-out","cat",apk_path[0][8:])).hexdigest()
            if installed!=digest(Path(config["apk"])): raise ValueError("Installed APK differs from configured instrumented APK")
            output.mkdir()
            self.runtime.event(run["id"],"coverage_started",{"label":label,"resets_probes":True})
            try:
                remote=f"/data/data/{config['package']}/files/coverage.ec"
                device._run("shell","rm","-f",remote)
                broadcast=device._run("shell","am","broadcast","-n",config["package"]+"/"+config["coverage_receiver"],"-a","edu.gatech.m3.emma.COLLECT_COVERAGE").decode()
                device._run("pull",remote,str(output/"coverage.ec"))
                if not (output/"coverage.ec").stat().st_size: raise ValueError("Empty coverage dump")
                report=subprocess.run([config["java"],"-jar",config["cli"],"report",str(output/"coverage.ec"),"--classfiles",config["class_files"],"--sourcefiles",config["source_files"],"--xml",str(output/"report.xml")],capture_output=True,timeout=90)
                log=(report.stdout+report.stderr).decode("utf-8","replace")
                (output/"report.log").write_text(log,encoding="utf-8")
                if report.returncode or "does not match" in log or "do not match" in log: raise ValueError("JaCoCo failed or APK/classes do not match; inspect coverage report log")
                result={"label":label,"apk_sha256":installed,"ec_sha256":digest(output/"coverage.ec"),"broadcast":broadcast,"source_sha256":target["file_sha256"]}
                if label=="after":
                    before=json.loads((directory/"baseline/result.json").read_text())
                    if before["apk_sha256"]!=installed: raise ValueError("APK changed since baseline")
                    result["verdict"]=compare_reports(directory/"baseline/report.xml",output/"report.xml",package,filename,target["start_line"],target["end_line"])
                else:
                    compare_reports(output/"report.xml",output/"report.xml",package,filename,target["start_line"],target["end_line"])
                (output/"result.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
                self.runtime.event(run["id"],"coverage",result)
                return result
            except Exception as exc:
                self.runtime.event(run["id"],"coverage_error",{"label":label,"reason":str(exc)})
                raise
