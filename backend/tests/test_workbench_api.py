import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core.auth import current_user
from app.workbench.api import router

class WorkbenchApiTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        (self.root/"repos/example").mkdir(parents=True)
        (self.root/"repos/example/Main.java").write_text("class Main {}")
        env=patch.dict("os.environ",{"REPOS_PATH":str(self.root/"repos")});env.start();self.addCleanup(env.stop)
        data=patch("app.workbench.api.DATA_DIR",str(self.root/"data"));data.start();self.addCleanup(data.stop)
        app=FastAPI();app.include_router(router);self.app=app;self.client=TestClient(app)

    def test_auth_create_reopen_and_stale_warning(self):
        self.assertEqual(self.client.get("/api/workbench/projects/example/files").status_code,401)
        self.app.dependency_overrides[current_user]=lambda:"alice"
        source=self.client.get("/api/workbench/projects/example/source",params={"path":"Main.java"}).json()
        response=self.client.post("/api/workbench/projects/example/runs",json={"goal":"Test Main","target":{"path":"Main.java","start_line":1,"end_line":1,"file_sha256":source["file_sha256"]},"conditions":[{"kind":"coverage","description":"New line coverage"}]})
        self.assertEqual(response.status_code,201,response.text)
        run_id=response.json()["id"]
        self.assertTrue(self.client.get(f"/api/workbench/runs/{run_id}").json()["source_check"]["matches"])
        (self.root/"repos/example/Main.java").write_text("class Changed {}")
        self.assertFalse(self.client.get(f"/api/workbench/runs/{run_id}").json()["source_check"]["matches"])
        self.assertEqual(self.client.post(f"/api/workbench/runs/{run_id}/control/start").status_code,409)
        self.app.dependency_overrides[current_user]=lambda:"bob"
        self.assertEqual(self.client.get(f"/api/workbench/runs/{run_id}").status_code,404)
        self.assertEqual(self.client.get(f"/api/workbench/runs/{run_id}/events").status_code,404)

    def test_source_escape_rejected(self):
        self.app.dependency_overrides[current_user]=lambda:"alice"
        r=self.client.get("/api/workbench/projects/example/source",params={"path":"../secret.java"})
        self.assertEqual(r.status_code,409)

    def test_map_snapshot_is_frozen_at_creation(self):
        self.app.dependency_overrides[current_user]=lambda:"alice"
        (self.root/"data").mkdir()
        graph={"schema_version":2,"screens":[{"id":"original"}],"transitions":[]}
        map_file=self.root/"data/example.json"
        map_file.write_text(json.dumps(graph))
        source=self.client.get("/api/workbench/projects/example/source",params={"path":"Main.java"}).json()
        response=self.client.post("/api/workbench/projects/example/runs",json={"goal":"Freeze evidence","target":{"path":"Main.java","start_line":1,"end_line":1,"file_sha256":source["file_sha256"]},"conditions":[{"kind":"coverage","description":"New coverage"}]})
        self.assertEqual(response.status_code,201,response.text)
        map_file.write_text(json.dumps({"screens":[],"transitions":[]}))
        reopened=self.client.get(f'/api/workbench/runs/{response.json()["id"]}').json()
        self.assertEqual(reopened["map_snapshot"],graph)

    def test_ui_condition_survives_reopen_without_claiming_success(self):
        self.app.dependency_overrides[current_user]=lambda:"alice"
        source=self.client.get("/api/workbench/projects/example/source",params={"path":"Main.java"}).json()
        condition={"kind":"ui","description":"Merged note visible","selector":{"resource_id":"example:id/title","text":"Merged"},"expected_count":1}
        response=self.client.post("/api/workbench/projects/example/runs",json={"goal":"Check merged note","target":{"path":"Main.java","start_line":1,"end_line":1,"file_sha256":source["file_sha256"]},"conditions":[condition]})
        self.assertEqual(response.status_code,201,response.text)
        saved=self.client.get(f'/api/workbench/runs/{response.json()["id"]}').json()
        self.assertEqual(saved["conditions"][0]["selector"],condition["selector"])
        self.assertEqual(saved["conditions"][0]["expected_count"],1)
        self.assertEqual(saved["results"]["ui"],"not_checked")

if __name__ == "__main__": unittest.main()
