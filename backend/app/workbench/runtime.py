"""Budgeted execution and replay state shared by HTTP and local Agent tools."""
from __future__ import annotations
import base64
from contextlib import closing
from datetime import datetime, timezone
import json
import re
from pathlib import Path
import sqlite3
import subprocess
import threading
import time
import uuid
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.navigation.device import AdbDevice
from app.navigation.observation import locate_trigger
from app.local_services import discover_adb

_locks: dict[str, threading.RLock] = {}
_guard = threading.Lock()
SESSION_ID = uuid.uuid4().hex

def lock(key):
    with _guard:
        return _locks.setdefault(key, threading.RLock())

def devices():
    executable = discover_adb()
    if not executable:
        return {"available": False, "devices": [], "reason": "ADB not configured; set GUI_ADB_PATH or PATH"}
    result = subprocess.run([executable, "devices", "-l"], capture_output=True, timeout=15)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", "replace"))
    found = []
    for line in result.stdout.decode().splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            found.append({"serial": parts[0], "state": parts[1], "details": " ".join(parts[2:])})
    return {"available": True, "devices": found}

class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["tap", "long_press", "key", "text", "scroll", "launch"]
    selector: dict[str, str] | None = None
    key: Literal[4, 66, 82] | None = None
    text: str | None = Field(default=None, max_length=2000)
    component: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_.]*/[A-Za-z_.][A-Za-z0-9_.$]*$")
    direction: Literal["up","down"] = "down"
    within: str | None = None
    reason: str = Field(min_length=1, max_length=2000)
    evidence: list[dict] = Field(default_factory=list)
    edge_id: str | None = None

class Runtime:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.db = root / "runtime.db"
        with closing(self.connect()) as c:
            c.executescript("""CREATE TABLE IF NOT EXISTS states (
              id TEXT PRIMARY KEY, status TEXT NOT NULL, started REAL, actions INTEGER NOT NULL DEFAULT 0);
              CREATE TABLE IF NOT EXISTS events (
              seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, at REAL, kind TEXT, payload TEXT);
              CREATE TABLE IF NOT EXISTS leases (serial TEXT PRIMARY KEY, run_id TEXT UNIQUE);""")
            columns={r[1] for r in c.execute("PRAGMA table_info(states)")}
            if "session_id" not in columns:c.execute("ALTER TABLE states ADD COLUMN session_id TEXT")
            c.commit()

    def connect(self):
        return sqlite3.connect(self.db, timeout=15)

    def event(self, run_id, kind, payload):
        with closing(self.connect()) as c:
            cursor=c.execute("INSERT INTO events(run_id,at,kind,payload) VALUES(?,?,?,?)", (run_id,time.time(),kind,json.dumps(payload)))
            c.commit()
            return cursor.lastrowid

    def state(self, run_id):
        with closing(self.connect()) as c:
            row = c.execute("SELECT status,started,actions,session_id FROM states WHERE id=?",(run_id,)).fetchone()
            if row and row[0]=="running" and row[3]!=SESSION_ID:
                c.execute("UPDATE states SET status='paused' WHERE id=?",(run_id,))
                c.execute("INSERT INTO events(run_id,at,kind,payload) VALUES(?,?,?,?)",(run_id,time.time(),"recovery",json.dumps({"reason":"Backend restarted; explicit resume required"})))
                c.commit();row=("paused",*row[1:])
        return dict(zip(["status","started","actions"],row[:3])) if row else {"status":"draft","started":None,"actions":0}

    def events(self, run_id, after=0):
        with closing(self.connect()) as c:
            rows=c.execute("SELECT seq,at,kind,payload FROM events WHERE run_id=? AND seq>? ORDER BY seq",(run_id,after)).fetchall()
        return [{"seq":r[0],"at":r[1],"kind":r[2],"payload":json.loads(r[3])} for r in rows]

    def block(self, run_id, reason):
        """Record an execution failure without discarding completed evidence."""
        with lock(run_id), closing(self.connect()) as c:
            c.execute("INSERT OR IGNORE INTO states(id,status) VALUES(?, 'draft')", (run_id,))
            status = c.execute("SELECT status FROM states WHERE id=?", (run_id,)).fetchone()[0]
            if status not in {"stopped", "blocked"}:
                c.execute("UPDATE states SET status='blocked' WHERE id=?", (run_id,))
                c.commit()
                self.event(run_id, "blocked", {"reason": str(reason)})
        return self.state(run_id)

    def control(self, run, command):
        self.state(run["id"])
        with lock(run["id"]), closing(self.connect()) as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("INSERT OR IGNORE INTO states(id,status) VALUES(?, 'draft')",(run["id"],))
            status,started,actions=c.execute("SELECT status,started,actions FROM states WHERE id=?",(run["id"],)).fetchone()
            transitions={"start":({"draft"},"running"),"pause":({"running"},"paused"),"resume":({"paused"},"running"),"stop":({"draft","running","paused","blocked"},"stopped")}
            allowed,new=transitions[command]
            if status not in allowed: raise ValueError(f"Cannot {command} a {status} Run")
            if new=="running":
                if not run.get("device_serial"): raise ValueError("Select a device before creating this Run")
                if started and time.time()-started >= run["time_budget_seconds"]: raise ValueError("Time budget exhausted")
                occupied=c.execute("SELECT run_id FROM leases WHERE serial=?",(run["device_serial"],)).fetchone()
                if occupied and occupied[0]!=run["id"]: raise ValueError("Device reserved by another Run; stop that Run first")
                c.execute("INSERT OR IGNORE INTO leases VALUES(?,?)",(run["device_serial"],run["id"]))
            if new=="stopped": c.execute("DELETE FROM leases WHERE run_id=?",(run["id"],))
            c.execute("UPDATE states SET status=?,started=?,session_id=? WHERE id=?",(new,started or (time.time() if new=="running" else None),SESSION_ID,run["id"]))
            c.commit()
        self.event(run["id"],"control",{"command":command,"status":new})
        return self.state(run["id"])

    def observe(self, run, device=None):
        if not run.get("device_serial"): raise ValueError("Run has no selected device")
        with lock("device:"+run["device_serial"]):
            observation=(device or AdbDevice(run["device_serial"])).observe()
            import uuid
            stem=uuid.uuid4().hex
            directory=self.root/run["id"]
            directory.mkdir(exist_ok=True)
            (directory/(stem+".xml")).write_text(observation.hierarchy,encoding="utf-8")
            if observation.screenshot: (directory/(stem+".png")).write_bytes(observation.screenshot)
            payload={"activity":observation.activity,"nodes":observation.nodes,"hierarchy":stem+".xml",
                     "screenshot":stem+".png" if observation.screenshot else None}
            self.event(run["id"],"observation",payload)
            return observation,payload

    def step(self, run, action: Action, check_source, device=None):
        with lock(run["id"]), lock("device:"+str(run.get("device_serial"))):
            state=self.state(run["id"])
            if state["status"]!="running": raise ValueError("Run is not running")
            if state["actions"]>=run["action_budget"] or time.time()-state["started"]>=run["time_budget_seconds"]:
                raise ValueError("Run action/time budget exhausted")
            if not check_source(): raise ValueError("Source version changed; execution refused")
            try:
                device=device or AdbDevice(run["device_serial"])
                before,before_payload=self.observe(run,device)
                target=None
                nodes=before.nodes
                if action.within:
                    scopes=[i for i,n in enumerate(nodes) if n["resource_id"]==action.within]
                    if len(scopes)!=1: raise ValueError("Scope must identify one container")
                    def inside(index):
                        seen=set()
                        while isinstance(index,int) and 0<=index<len(nodes) and index not in seen:
                            if index==scopes[0]: return True
                            seen.add(index);index=nodes[index].get("parent_index")
                        return False
                    nodes=[{**n,"enabled":n.get("enabled",True) and inside(i)} for i,n in enumerate(nodes)]
                if action.kind=="launch":
                    if not action.component: raise ValueError("Launch requires a package/activity component")
                elif action.kind=="text":
                    if not action.text or not re.fullmatch(r"[A-Za-z0-9_ .-]+",action.text): raise ValueError("Text input currently supports ASCII letters, numbers, spaces, underscore, dot and hyphen")
                    focused=[n for n in nodes if n.get("focused") and n.get("enabled") and "EditText" in n.get("class","")]
                    if len(focused)!=1: raise ValueError("Text requires a unique focused editor")
                    target=focused[0]
                elif action.kind=="scroll":
                    if not action.selector or set(action.selector)-{"resource_id","text","description"}: raise ValueError("Scroll requires an exact container selector")
                    found=[n for n in nodes if n.get("scrollable") and n.get("enabled") and all(n.get(k)==v for k,v in action.selector.items())]
                    if len(found)!=1: raise ValueError("Scroll container absent or ambiguous")
                    target=found[0]
                    x1,y1,x2,y2=target["bounds"]
                    if x2<=x1 or y2<=y1: raise ValueError("Scroll container is invisible")
                elif action.kind=="key":
                    if action.key is None or action.selector: raise ValueError("Key action requires one supported key")
                else:
                    if not action.selector or action.key: raise ValueError("Pointer action requires a unique selector")
                    edge={"trigger":{"status":"resolved","event":"menu_select" if action.selector.get("target")=="list_item" else action.kind.replace("tap","click"),"selector":action.selector}}
                    target=locate_trigger(edge,nodes)
                    if target is None: raise ValueError("Control absent, disabled or ambiguous; no action sent")
                # Count BEFORE dispatch; an uncertain ADB response must not allow a free retry.
                with closing(self.connect()) as c:
                    c.execute("UPDATE states SET actions=actions+1 WHERE id=?",(run["id"],));c.commit()
                action_seq=self.event(run["id"],"action",{**action.model_dump(),"target":target,"before":before_payload})
                if action.kind=="launch": device._run("shell","am","start","-n",action.component)
                elif action.kind=="text": device._run("shell","input","text",action.text.replace(" ","%s"))
                elif action.kind=="scroll":
                    x=(x1+x2)//2;top=y1+(y2-y1)//4;bottom=y1+3*(y2-y1)//4
                    begin,finish=(bottom,top) if action.direction=="down" else (top,bottom)
                    device._run("shell","input","swipe",str(x),str(begin),str(x),str(finish),"400")
                elif action.kind=="key": device._run("shell","input","keyevent",str(action.key))
                elif action.kind=="long_press": device.long_press(*target["center"])
                else: device.tap(*target["center"])
                after,payload=self.observe(run,device)
                self.event(run["id"],"action_completed",{"action_seq":action_seq,"after":payload})
                return {"state":self.state(run["id"]),"observation":payload}
            except ValueError as exc:
                # Stale or ambiguous selectors are recoverable. Preserve the
                # rejection and let the agent observe again instead of ending
                # the whole device task after one grounding mistake.
                self.event(run["id"], "action_rejected", {"reason": str(exc), "action": action.model_dump()})
                raise
            except RuntimeError as exc:
                if "SecurityException" in str(exc) or "Permission Denial" in str(exc):
                    self.event(run["id"], "action_rejected", {"reason": str(exc), "action": action.model_dump()})
                    raise
                self.block(run["id"], exc)
                raise
