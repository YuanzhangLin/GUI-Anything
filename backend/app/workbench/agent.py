"""Structured Agent decisions, executed only through the budgeted runtime."""
import asyncio
import json
from pathlib import Path
import threading
import time
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator
from app.core import opencode_agent, external_agent
from app.paths import DATA_DIR
from app.workbench.runtime import Action, Runtime, lock

class Decision(BaseModel):
    model_config=ConfigDict(extra="forbid")
    status: Literal["act","verify","done","blocked"]
    reason: str = Field(min_length=1,max_length=4000)
    plan: list[str] = Field(default_factory=list,max_length=30)
    action: Action | None = None
    verification: Literal["baseline","after","assertions"] | None = None

    @model_validator(mode="after")
    def check_action(self):
        if (self.status=="act") != (self.action is not None): raise ValueError("Only act decisions must include an action")
        if (self.status=="verify") != (self.verification is not None): raise ValueError("Only verify decisions must name a verification tool")
        return self

_jobs={}
_guard=threading.Lock()

def available(provider):
    return opencode_agent.available() if provider=="opencode" else external_agent.available() if provider=="external" else False

def prompt(run, observation, recent):
    return """You are executing a GUI-Anything code-target Run. Read the target code and relevant project source.
Return ONLY one JSON object matching this protocol:
{"status":"act|verify|done|blocked","reason":"explanation","plan":["milestone"],"action":null,"verification":null}
For act, action must be {"kind":"tap|long_press|key","selector":{"resource_id":"exact id"},"reason":"grounding explanation","evidence":[{"file_path":"relative source","line":1}]}. Key actions use key 4,66,82 and no selector. Additional action kinds: text (text field; ASCII letters/numbers/spaces/underscore/dot/hyphen, requires focused editor), scroll (exact selector for scrollable container and direction up/down), launch (component package/activity). Use within with a unique container resource ID to disambiguate repeated toolbar selectors.
Selectors accept resource_id, text, description, and target (self,nearest_clickable_ancestor,list_item).
Never operate the device yourself or use raw shell/coordinates. The service executes one grounded action and sends a fresh observation.
Use status verify with verification baseline, after, or assertions to request independent server tools. Prepare fixtures, collect baseline BEFORE the target behavior, execute the target behavior, then collect after and assertions. Coverage phases are immutable: never repeat a phase already recorded. Read verification events; never manufacture a verdict. After collecting final coverage do not execute more actions: they invalidate the evidence and require a new Run. If verification fails, explain the evidence and return blocked.
Use the immutable task goal, source range and budgets. Do not treat reaching a page as task completion. done means your UI work is finished and independent coverage/business verification remains necessary. If the required operation is unsupported or no grounded route remains, return blocked. Do not invent observations or coverage. Include an ordered plan and cite source for ambiguous actions.
TASK:
"""+json.dumps(run,ensure_ascii=False)+"\nOBSERVATION:\n"+json.dumps(observation,ensure_ascii=False)+"\nRECENT EVENTS:\n"+json.dumps(recent,ensure_ascii=False)

async def ask_while_running(run, runtime, ask, message, control_seq):
    task=asyncio.create_task(ask(message,run["app_id"]))
    try:
        while True:
            done,_=await asyncio.wait({task},timeout=.25)
            if done: return task.result()
            changed=runtime.state(run["id"])["status"]!="running" or any(
                event["kind"]=="control" for event in runtime.events(run["id"],control_seq))
            if changed:
                runtime.event(run["id"],"agent_request_cancelled",{"reason":"Run paused, stopped or resumed while waiting for model"})
                return None
    finally:
        if not task.done(): task.cancel()
        await asyncio.gather(task,return_exceptions=True)


async def drive(run, runtime, source, ask):
    try:
        while True:
            state=runtime.state(run["id"])
            if state["status"]=="paused":
                if time.time()-state["started"]>=run["time_budget_seconds"]:
                    runtime.event(run["id"],"agent_error",{"reason":"Time budget exhausted while paused"});return
                await asyncio.sleep(.5);continue
            if state["status"]!="running":return
            remaining=run["time_budget_seconds"]-(time.time()-state["started"])
            if remaining<=0: raise ValueError("Run time budget exhausted")
            observation,payload=await asyncio.to_thread(runtime.observe,run)
            history=runtime.events(run["id"])
            control_seq=max((e["seq"] for e in history if e["kind"]=="control"),default=0)
            recent=history[-6:]
            from app.workbench.results import summarize
            context={**run,"current_results":summarize(run,history),"actions_used":state["actions"],
                     "coverage_phases":[e["payload"].get("label") for e in history if e["kind"]=="coverage_started"]}
            runtime.event(run["id"],"agent_thinking",{"provider":run["agent"]})
            raw=await asyncio.wait_for(ask_while_running(run,runtime,ask,prompt(context,payload,recent),control_seq),timeout=min(300,remaining))
            if raw is None: continue
            decision=Decision.model_validate_json(raw.strip())
            runtime.event(run["id"],"agent_decision",decision.model_dump())
            # Pause/stop may have arrived during the model call. Never dispatch the stale decision.
            if runtime.state(run["id"])["status"]!="running":continue
            if any(e["kind"]=="control" for e in runtime.events(run["id"],control_seq)):
                runtime.event(run["id"],"agent_decision_discarded",{"reason":"Run controls changed during model call; observe again"})
                continue
            if decision.status=="verify":
                def verify():
                    # Serialize against pause/stop and device actions, just like execution.
                    with lock(run["id"]), lock("device:"+str(run.get("device_serial"))):
                        if runtime.state(run["id"])["status"]!="running": return
                        if decision.verification=="assertions":
                            from app.workbench.assertions import evaluate
                            evaluate(run,runtime)
                        else:
                            from app.workbench.coverage import Coverage
                            Coverage(runtime,source).collect(run,decision.verification)
                await asyncio.to_thread(verify)
                continue
            if decision.status!="act":
                runtime.control(run,"pause")
                runtime.event(run["id"],"verification_required" if decision.status=="done" else "agent_blocked",{"reason":decision.reason})
                return
            def matches():
                current=source.read(run["target"]["path"])
                return current["file_sha256"]==run["target"]["file_sha256"] and current["revision"]["commit"]==run["target"]["revision"]["commit"]
            await asyncio.to_thread(runtime.step,run,decision.action,matches)
    except Exception as exc:
        runtime.event(run["id"],"agent_error",{"reason":str(exc) or type(exc).__name__})
        if runtime.state(run["id"])["status"]=="running":runtime.control(run,"pause")

def launch(run, runtime, source):
    if not available(run["agent"]):raise ValueError("Selected Agent is not installed/configured")
    with _guard:
        previous=_jobs.get(run["id"])
        if previous and previous.is_alive():raise ValueError("Agent already running for this Run")
        if runtime.state(run["id"])["status"]!="running":raise ValueError("Start or resume the Run before launching the Agent")
        ask=opencode_agent.ask if run["agent"]=="opencode" else external_agent.ask
        job=threading.Thread(target=lambda:asyncio.run(drive(run,runtime,source,ask)),daemon=True)
        _jobs[run["id"]]=job
        runtime.event(run["id"],"agent_started",{"provider":run["agent"]})
        job.start()
        return {"status":"started","provider":run["agent"]}
