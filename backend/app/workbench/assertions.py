"""Independent assertions; no model-written success flags or arbitrary SQL."""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid
import time
from app.navigation.device import AdbDevice
from app.paths import validate_app_id
from app.workbench.runtime import lock

def database_snapshot(device, package, name, output):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*",package) or not re.fullmatch(r"[A-Za-z0-9_.-]+",name):
        raise ValueError("Invalid database identity")
    base=f"/data/data/{package}/databases/{name}"
    def read():
        result={}
        for suffix in ["","-wal","-journal"]:
            remote=base+suffix
            exists=device._run("shell","test","-f",remote) if suffix=="" else None
            if suffix:
                try: device._run("shell","test","-f",remote)
                except RuntimeError: continue
            result[suffix]=device._run("exec-out","cat",remote)
        return result
    first,second=read(),read()
    if first!=second: raise ValueError("Database changed during snapshot; pause app activity and retry")
    output.mkdir()
    for suffix,data in second.items(): (output/("snapshot.db"+suffix)).write_bytes(data)
    return output/"snapshot.db",{suffix:hashlib.sha256(data).hexdigest() for suffix,data in second.items()}

def evaluate(run,runtime):
    with lock(run["id"]),lock("device:"+str(run.get("device_serial"))):
        if not run.get("device_serial"): raise ValueError("Select a device first")
        device=AdbDevice(run["device_serial"])
        results=[]
        for index,condition in enumerate(run["conditions"]):
            if condition["kind"]=="coverage": continue
            result={"condition":index,"kind":condition["kind"],"status":"not_checked","description":condition["description"]}
            try:
                if condition["kind"]=="ui" and condition.get("selector"):
                    selector=condition["selector"]
                    if set(selector)-{"resource_id","text","description"}: raise ValueError("Unsupported assertion selector")
                    observation,payload=runtime.observe(run,device)
                    matches=[n for n in observation.nodes if n.get("enabled") and all(n.get(k)==v for k,v in selector.items())]
                    result.update({"actual_count":len(matches),"expected_count":condition["expected_count"],"observation":payload,
                                   "status":"passed" if len(matches)==condition["expected_count"] else "failed"})
                elif condition["kind"]=="business" and condition.get("check") and condition.get("expected_rows") is not None:
                    check=run.get("assertion_definitions",{}).get(condition["check"])
                    if not check: raise ValueError("No frozen operator-configured database check")
                    output=runtime.root/run["id"]/uuid.uuid4().hex
                    database,hashes=database_snapshot(device,check["package"],check["database"],output)
                    connection=sqlite3.connect(database.resolve().as_uri()+"?mode=ro",uri=True)
                    try:
                        connection.row_factory=sqlite3.Row
                        deadline=time.monotonic()+15
                        connection.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
                        allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_RECURSIVE}
                        connection.set_authorizer(lambda action,*args:sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
                        rows=[dict(r) for r in connection.execute(check["query"],condition.get("parameters",[])).fetchmany(1001)]
                        if len(rows)>1000:raise ValueError("Business check returned more than 1000 rows")
                    finally:connection.close()
                    result.update({"actual_rows":rows,"expected_rows":condition["expected_rows"],"snapshot_hashes":hashes,
                                   "status":"passed" if rows==condition["expected_rows"] else "failed"})
                else: result["reason"]="Condition has no executable assertion configured"
            except Exception as exc: result.update({"status":"error","reason":str(exc)})
            results.append(result)
        runtime.event(run["id"],"assertions",{"results":results})
        return results
