import tempfile
import unittest
from pathlib import Path
from app.workbench.store import Source, RunStore, RunRequest

class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / "Main.java").write_text("class Main {\n void save() {}\n}\n")
        self.source = Source(self.repo)
        self.store = RunStore(self.root / "runs")

    def request(self):
        return RunRequest(goal="Exercise save", target={"path":"Main.java", "start_line":2,
            "end_line":2, "file_sha256":self.source.read("Main.java")["file_sha256"]},
            conditions=[{"kind":"coverage", "description":"Target line newly covered"}])

    def test_roundtrip_and_owner_isolation(self):
        run = self.store.create("app", "alice", self.source, self.request())
        loaded = self.store.read(run["id"], "alice")
        self.assertEqual(loaded["target"]["excerpt"], " void save() {}")
        self.assertTrue(self.store.check_source(loaded, self.source)["matches"])
        self.assertEqual(len(self.store.list("app", "alice")), 1)
        self.assertEqual(self.store.list("app", "bob"), [])
        with self.assertRaises(FileNotFoundError): self.store.read(run["id"], "bob")

    def test_stale_selection_and_reopened_target(self):
        request = self.request()
        run = self.store.create("app", "alice", self.source, request)
        (self.repo / "Main.java").write_text("class Changed {}")
        with self.assertRaisesRegex(ValueError, "Source changed"):
            self.store.create("app", "alice", self.source, request)
        self.assertFalse(self.store.check_source(run, self.source)["matches"])

    def test_paths_ranges_and_unknown_fields(self):
        for path in ["../secret.java", str(self.root / "secret.java"), ".git/config", "key.pem"]:
            with self.assertRaises(ValueError): self.source.read(path)
        request = self.request().model_copy(update={"target":self.request().target.model_copy(update={"end_line":99})})
        with self.assertRaises(ValueError): self.source.target(request.target)
        with self.assertRaises(ValueError): RunRequest(**{**self.request().model_dump(), "shell":"unsafe"})

    def test_tree_skips_build_and_secrets(self):
        (self.repo / "build").mkdir()
        (self.repo / "build/Generated.java").write_text("generated")
        (self.repo / ".env").write_text("private")
        self.assertEqual(self.source.tree()["files"], ["Main.java"])

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        from app.workbench.runtime import Runtime
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.runtime=Runtime(Path(self.tmp.name))
        self.run={"id":"a"*32,"device_serial":"test-device","action_budget":1,"time_budget_seconds":60}

    def device(self, fail=False):
        from app.navigation.device import Observation
        from app.navigation.observation import parse_hierarchy
        xml='<hierarchy><node resource-id="example:id/save" text="Save" clickable="true" enabled="true" bounds="[0,0][50,50]"/></hierarchy>'
        class Device:
            taps=0
            def observe(this):
                if fail: raise RuntimeError("Device disconnected")
                return Observation("example.Main",xml,parse_hierarchy(xml),b"png")
            def tap(this,x,y): this.taps+=1
        return Device()

    def action(self):
        from app.workbench.runtime import Action
        return Action(kind="tap",selector={"resource_id":"example:id/save"},reason="Save test record")

    def test_budget_pause_and_replay(self):
        runtime=self.runtime;runtime.control(self.run,"start");device=self.device()
        runtime.control(self.run,"pause")
        with self.assertRaises(ValueError): runtime.step(self.run,self.action(),lambda:True,device)
        runtime.control(self.run,"resume")
        runtime.step(self.run,self.action(),lambda:True,device)
        self.assertEqual(device.taps,1)
        with self.assertRaisesRegex(ValueError,"budget"): runtime.step(self.run,self.action(),lambda:True,device)
        events=runtime.events(self.run["id"])
        self.assertEqual(sum(e["kind"]=="observation" for e in events),2)
        action=next(e for e in events if e["kind"]=="action")
        completed=next(e for e in events if e["kind"]=="action_completed")
        self.assertEqual(completed["payload"]["action_seq"],action["seq"])
        self.assertEqual(completed["payload"]["after"], [e for e in events if e["kind"]=="observation"][-1]["payload"])
        self.assertEqual(runtime.state(self.run["id"])["actions"],1)
        runtime.control(self.run,"stop")

    def test_disconnect_and_stale_source_never_tap(self):
        runtime=self.runtime;runtime.control(self.run,"start")
        with self.assertRaisesRegex(ValueError,"Source version"):
            runtime.step(self.run,self.action(),lambda:False,self.device())
        with self.assertRaisesRegex(RuntimeError,"disconnected"):
            runtime.step(self.run,self.action(),lambda:True,self.device(True))
        self.assertEqual(runtime.state(self.run["id"])["status"],"blocked")
        self.assertEqual(runtime.state(self.run["id"])["actions"],0)
        self.assertEqual(runtime.events(self.run["id"])[-1]["kind"],"blocked")

    def test_invalid_selector_can_be_retried(self):
        runtime=self.runtime;runtime.control(self.run,"start")
        action=self.action();action.selector={"resource_id":"missing"}
        with self.assertRaisesRegex(ValueError,"absent"):
            runtime.step(self.run,action,lambda:True,self.device())
        self.assertEqual(runtime.state(self.run["id"])["status"],"running")
        self.assertEqual(runtime.events(self.run["id"])[-1]["kind"],"action_rejected")

    def test_missing_adb_blocks_run_and_preserves_reason(self):
        from unittest.mock import patch
        self.runtime.control(self.run,"start")
        with patch.dict("os.environ",{"GUI_ADB_PATH":"missing-adb"}), patch("app.navigation.device.subprocess.run",side_effect=FileNotFoundError("ADB removed")):
            with self.assertRaisesRegex(RuntimeError,"Cannot start ADB"):
                self.runtime.step(self.run,self.action(),lambda:True)
        self.assertEqual(self.runtime.state(self.run["id"])["status"],"blocked")
        self.assertEqual(self.runtime.state(self.run["id"])["actions"],0)
        event=self.runtime.events(self.run["id"])[-1]
        self.assertEqual(event["kind"],"blocked")
        self.assertIn("ADB removed",event["payload"]["reason"])

    def test_disconnect_after_dispatch_keeps_action_without_completion(self):
        runtime=self.runtime;runtime.control(self.run,"start");device=self.device()
        original=device.observe
        calls=0
        def observe():
            nonlocal calls
            calls+=1
            if calls==2: raise RuntimeError("Device disconnected after dispatch")
            return original()
        device.observe=observe
        with self.assertRaisesRegex(RuntimeError,"after dispatch"):
            runtime.step(self.run,self.action(),lambda:True,device)
        events=runtime.events(self.run["id"])
        self.assertEqual(device.taps,1)
        self.assertEqual(runtime.state(self.run["id"])["actions"],1)
        self.assertEqual(sum(e["kind"]=="action" for e in events),1)
        self.assertFalse(any(e["kind"]=="action_completed" for e in events))
        self.assertEqual(events[-1]["kind"],"blocked")

    def test_restart_requires_explicit_resume(self):
        from unittest.mock import patch
        self.runtime.control(self.run,"start")
        with patch("app.workbench.runtime.SESSION_ID","different-process"):
            self.assertEqual(self.runtime.state(self.run["id"])["status"],"paused")
            self.assertEqual(self.runtime.events(self.run["id"])[-1]["kind"],"recovery")
            self.assertEqual(self.runtime.control(self.run,"resume")["status"],"running")

    def test_device_exclusion_and_release(self):
        self.runtime.control(self.run,"start")
        other={**self.run,"id":"b"*32}
        with self.assertRaisesRegex(ValueError,"reserved"): self.runtime.control(other,"start")
        self.runtime.control(self.run,"stop")
        self.assertEqual(self.runtime.control(other,"start")["status"],"running")

if __name__ == "__main__": unittest.main()
