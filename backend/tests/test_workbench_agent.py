import asyncio
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app.workbench.agent import Decision, drive
from app.workbench.runtime import Runtime

class AgentTests(unittest.TestCase):
    def test_invalid_action_protocol(self):
        with self.assertRaises(ValueError): Decision(status="act",reason="x")
        with self.assertRaises(ValueError): Decision.model_validate_json('{"status":"act","reason":"x","action":{"kind":"shell","reason":"x"}}')
        with self.assertRaises(ValueError): Decision(status="verify",reason="x")
        with self.assertRaises(ValueError): Decision(status="done",reason="x",verification="after")

    def test_verification_dispatch_uses_independent_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Runtime(Path(tmp));run={"id":"c"*32,"device_serial":"fake","agent":"opencode","app_id":"example","action_budget":2,"time_budget_seconds":60,"conditions":[]}
            runtime.control(run,"start")
            answers=iter(['{"status":"verify","reason":"Before target","verification":"baseline"}', '{"status":"verify","reason":"Check data","verification":"assertions"}', '{"status":"done","reason":"Review independent results"}'])
            async def ask(prompt,app): return next(answers)
            with patch.object(runtime,"observe",return_value=(None,{})), patch("app.workbench.coverage.Coverage") as coverage, patch("app.workbench.assertions.evaluate") as assertions:
                asyncio.run(drive(run,runtime,None,ask))
                coverage.return_value.collect.assert_called_once_with(run,"baseline")
                assertions.assert_called_once_with(run,runtime)
            self.assertEqual(runtime.state(run["id"])["actions"],0)

    def test_done_requires_independent_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Runtime(Path(tmp));run={"id":"a"*32,"device_serial":"fake","agent":"opencode","app_id":"example","action_budget":2,"time_budget_seconds":60,"conditions":[]}
            runtime.control(run,"start")
            async def ask(prompt,app): return '{"status":"done","reason":"UI work finished","plan":[]}'
            with patch.object(runtime,"observe",return_value=(None,{"activity":"example.Main","nodes":[]})):
                asyncio.run(drive(run,runtime,None,ask))
            self.assertEqual(runtime.state(run["id"])["status"],"paused")
            self.assertEqual(runtime.events(run["id"])[-1]["kind"],"verification_required")

    def test_exhausted_action_budget_still_allows_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Runtime(Path(tmp));run={"id":"d"*32,"device_serial":"fake","agent":"opencode","app_id":"example","action_budget":1,"time_budget_seconds":60,"conditions":[]}
            runtime.control(run,"start")
            with closing(runtime.connect()) as connection:
                connection.execute("UPDATE states SET actions=1 WHERE id=?",(run["id"],));connection.commit()
            answers=iter(['{"status":"verify","reason":"Check final state","verification":"assertions"}', '{"status":"done","reason":"Finished verification"}'])
            async def ask(prompt,app): return next(answers)
            with patch.object(runtime,"observe",return_value=(None,{})), patch("app.workbench.assertions.evaluate") as assertions:
                asyncio.run(drive(run,runtime,None,ask))
                assertions.assert_called_once_with(run,runtime)
            self.assertEqual(runtime.state(run["id"])["actions"],1)

    def test_stop_during_model_call_discards_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Runtime(Path(tmp));run={"id":"e"*32,"device_serial":"fake","agent":"opencode","app_id":"example","action_budget":1,"time_budget_seconds":60,"conditions":[]}
            runtime.control(run,"start")
            async def ask(prompt,app):
                runtime.control(run,"stop")
                return '{"status":"verify","reason":"Collect","verification":"baseline"}'
            with patch.object(runtime,"observe",return_value=(None,{})), patch("app.workbench.coverage.Coverage") as coverage:
                asyncio.run(drive(run,runtime,None,ask));coverage.assert_not_called()

    def test_stop_during_model_call_discards_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Runtime(Path(tmp));run={"id":"b"*32,"device_serial":"fake","agent":"opencode","app_id":"example","action_budget":2,"time_budget_seconds":60,"conditions":[]}
            runtime.control(run,"start")
            async def ask(prompt,app):
                runtime.control(run,"stop")
                return '{"status":"act","reason":"tap","action":{"kind":"key","key":4,"reason":"back"}}'
            with patch.object(runtime,"observe",return_value=(None,{})),patch.object(runtime,"step") as step:
                asyncio.run(drive(run,runtime,None,ask));step.assert_not_called()
            self.assertEqual(runtime.state(run["id"])["actions"],0)

    def test_pause_resume_during_model_call_discards_old_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Runtime(Path(tmp));run={"id":"f"*32,"device_serial":"fake","agent":"opencode","app_id":"example","action_budget":2,"time_budget_seconds":60,"conditions":[]}
            runtime.control(run,"start")
            calls=0
            async def ask(prompt,app):
                nonlocal calls
                calls+=1
                if calls==1:
                    runtime.control(run,"pause");runtime.control(run,"resume")
                    return '{"status":"act","reason":"Old observation","action":{"kind":"key","key":4,"reason":"back"}}'
                return '{"status":"blocked","reason":"Need a new plan"}'
            with patch.object(runtime,"observe",return_value=(None,{})),patch.object(runtime,"step") as step:
                asyncio.run(drive(run,runtime,None,ask));step.assert_not_called()
            self.assertEqual(calls,2)
            self.assertTrue(any(e["kind"]=="agent_decision_discarded" for e in runtime.events(run["id"])))

    def test_stop_cancels_pending_model_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Runtime(Path(tmp));run={"id":"1"*32,"device_serial":"fake","agent":"opencode","app_id":"example","action_budget":2,"time_budget_seconds":60,"conditions":[]}
            runtime.control(run,"start")
            cancelled=[]
            async def ask(prompt,app):
                runtime.control(run,"stop")
                try: await asyncio.Event().wait()
                finally: cancelled.append(True)
            with patch.object(runtime,"observe",return_value=(None,{})),patch.object(runtime,"step") as step:
                asyncio.run(asyncio.wait_for(drive(run,runtime,None,ask),timeout=2))
                step.assert_not_called()
            self.assertEqual(cancelled,[True])
            self.assertEqual(runtime.state(run["id"])["status"],"stopped")
            self.assertTrue(any(e["kind"]=="agent_request_cancelled" for e in runtime.events(run["id"])))

if __name__=="__main__":unittest.main()
