"""Authenticated local workbench API, separate from the public demo."""
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from typing import Literal
from app.workbench.runtime import Runtime, Action, devices
from app.core.auth import current_user
from app.paths import DATA_DIR, validate_app_id
from app.services.code_manager import CodeManager
from app.workbench.store import RunRequest, RunStore, Source

router = APIRouter(prefix="/api/workbench", tags=["workbench"])

def source(app_id):
    return Source(Path(CodeManager().get_repo_path(validate_app_id(app_id))))

def store():
    return RunStore(Path(DATA_DIR)/"runs")

def guarded(fn):
    try:
        return fn()
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (ValueError, UnicodeError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc

@router.get("/projects/{app_id}/files")
def files(app_id: str, user: str = Depends(current_user)):
    return guarded(lambda: source(app_id).tree())

@router.get("/projects/{app_id}/source")
def read_source(app_id: str, path: str, user: str = Depends(current_user)):
    return guarded(lambda: source(app_id).read(path))

@router.post("/projects/{app_id}/runs", status_code=201)
def create_run(app_id: str, request: RunRequest, user: str = Depends(current_user)):
    def create():
        import json
        project_source=source(app_id)
        map_path=Path(DATA_DIR)/(validate_app_id(app_id)+".json")
        graph=json.loads(map_path.read_text(encoding="utf-8")) if map_path.is_file() and map_path.stat().st_size<10_000_000 else None
        return store().create(app_id,user,project_source,request,graph)
    return guarded(create)

@router.get("/projects/{app_id}/runs")
def list_runs(app_id: str, user: str = Depends(current_user)):
    return guarded(lambda: store().list(validate_app_id(app_id), user))

@router.get("/runs/{run_id}")
def read_run(run_id: str, user: str = Depends(current_user)):
    def read():
        repo = store()
        run = repo.read(run_id, user)
        events=runtime().events(run_id)
        from app.workbench.results import summarize
        conclusions=summarize(run,events)
        try: source_check=repo.check_source(run,source(run["app_id"]))
        except FileNotFoundError: source_check={"matches":False,"reason":"Project source no longer available"}
        return {**run, **runtime().state(run_id), **conclusions, "source_check":source_check}
    return guarded(read)


def runtime():
    return Runtime(Path(DATA_DIR)/"runs")

@router.get("/devices")
def list_devices(user: str = Depends(current_user)):
    return guarded(devices)

@router.get("/runs/{run_id}/events")
def run_events(run_id: str, after: int = 0, user: str = Depends(current_user)):
    def read():
        store().read(run_id,user)
        return runtime().events(run_id,after)
    return guarded(read)

@router.post("/runs/{run_id}/control/{command}")
def control_run(run_id: str, command: Literal["start","pause","resume","stop"], user: str = Depends(current_user)):
    def control():
        run=store().read(run_id,user)
        if command in {"start","resume"} and not store().check_source(run,source(run["app_id"]))["matches"]:
            raise ValueError("Source version changed")
        return runtime().control(run,command)
    return guarded(control)

@router.post("/runs/{run_id}/observe")
def observe_run(run_id: str, user: str = Depends(current_user)):
    return guarded(lambda: runtime().observe(store().read(run_id,user))[1])

@router.post("/runs/{run_id}/actions")
def action_run(run_id: str, action: Action, user: str = Depends(current_user)):
    def execute():
        run=store().read(run_id,user)
        return runtime().step(run,action,lambda: store().check_source(run,source(run["app_id"]))["matches"])
    return guarded(execute)

@router.get("/runs/{run_id}/assets/{name}")
def asset(run_id: str, name: str, user: str = Depends(current_user)):
    def read():
        store().read(run_id,user)
        import re
        if not re.fullmatch(r"[a-f0-9]{32}\.(xml|png)",name): raise ValueError("Invalid asset name")
        path=Path(DATA_DIR)/"runs"/run_id/name
        if not path.is_file(): raise FileNotFoundError("Asset not found")
        return FileResponse(path,media_type="image/png" if name.endswith(".png") else "application/xml")
    return guarded(read)


@router.post("/runs/{run_id}/coverage/{label}")
def collect_coverage(run_id: str, label: Literal["baseline","after"], user: str = Depends(current_user)):
    from app.workbench.coverage import Coverage
    def collect():
        run=store().read(run_id,user)
        return Coverage(runtime(),source(run["app_id"])).collect(run,label)
    return guarded(collect)


@router.post("/runs/{run_id}/agent")
def start_agent(run_id: str, user: str = Depends(current_user)):
    from app.workbench.agent import launch
    def start():
        run=store().read(run_id,user)
        if not store().check_source(run,source(run["app_id"]))["matches"]: raise ValueError("Source version changed")
        return launch(run,runtime(),source(run["app_id"]))
    return guarded(start)


@router.post("/runs/{run_id}/assertions")
def verify_assertions(run_id: str, user: str = Depends(current_user)):
    from app.workbench.assertions import evaluate
    return guarded(lambda:evaluate(store().read(run_id,user),runtime()))


@router.get("/agents")
def agents(user: str = Depends(current_user)):
    from app.workbench.agent import available
    return [{"id":name,"available":available(name),"note":"Executable availability only; model credentials are checked when invoked"} for name in ["opencode","external"]]


@router.get("/devices/{serial}/preview")
def device_preview(serial: str, user: str = Depends(current_user)):
    def read():
        import base64
        from app.navigation.device import AdbDevice
        from app.navigation.observation import parse_activity
        if not any(d["serial"] == serial and d["state"] == "device" for d in devices()["devices"]):
            raise ValueError("Device is not connected")
        device = AdbDevice(serial)
        with __import__("app.workbench.runtime", fromlist=["lock"]).lock("device:" + serial):
            activity = parse_activity(device._run("shell", "dumpsys", "activity", "activities").decode("utf-8", "replace"))
            picture = device._run("exec-out", "screencap", "-p")
        return {"activity": activity, "screenshot": base64.b64encode(picture).decode("ascii")}
    return guarded(read)
