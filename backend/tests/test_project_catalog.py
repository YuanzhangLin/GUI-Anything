import asyncio
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app import main


class ProjectCatalogTests(unittest.TestCase):
    def test_one_project_contains_two_apps_with_independent_conversations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app_list.yml").write_text("apps: []\n", encoding="utf-8")
            db = str(root / "catalog.db")
            with patch.object(main, "DB_PATH", db), patch.object(main, "DATA_DIR", str(root)):
                main.init_db()
                main._register_app("app-one", "shared-project", "App One", "source", "https://example.test/one.git", "Shared")
                main._register_app("app-two", "shared-project", "App Two", "source", "https://example.test/two.git")
                with closing(sqlite3.connect(db)) as connection:
                    connection.execute("INSERT INTO sessions(id,title,username,app_id,project_id) VALUES (?,?,?,?,?)", ("chat-one", "First", "local", "app-one", "shared-project"))
                    connection.execute("INSERT INTO sessions(id,title,username,app_id,project_id) VALUES (?,?,?,?,?)", ("chat-two", "Second", "local", "app-two", "shared-project"))
                    connection.commit()

                projects = asyncio.run(main.get_projects("local"))
                shared = next(project for project in projects if project["id"] == "shared-project")
                self.assertEqual({app["id"] for app in shared["apps"]}, {"app-one", "app-two"})
                with closing(sqlite3.connect(db)) as connection:
                    chats = connection.execute("SELECT id,app_id FROM sessions WHERE project_id=? ORDER BY id", ("shared-project",)).fetchall()
                self.assertEqual(chats, [("chat-one", "app-one"), ("chat-two", "app-two")])

    def test_legacy_app_becomes_stable_project_app_relationship(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app_list.yml").write_text(
                "apps:\n  - id: first-app\n    name: First App\n    repo_url: https://example.test/repo.git\n",
                encoding="utf-8",
            )
            db = str(root / "catalog.db")
            with patch.object(main, "DB_PATH", db), patch.object(main, "DATA_DIR", str(root)):
                main.init_db()
                projects = asyncio.run(main.get_projects("local"))
                self.assertEqual(projects[0]["id"], "first-app")
                self.assertEqual(projects[0]["apps"][0]["project_id"], "first-app")
                with closing(sqlite3.connect(db)) as connection:
                    connection.execute("INSERT INTO sessions(id,title,username,app_id) VALUES ('s','t','local','first-app')")
                    connection.commit()
                main.init_db()
                with closing(sqlite3.connect(db)) as connection:
                    self.assertEqual(connection.execute("SELECT project_id FROM sessions WHERE id='s'").fetchone()[0], "first-app")

    def test_app_cannot_be_resolved_under_another_project(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app_list.yml").write_text("apps:\n  - id: first-app\n    name: First App\n", encoding="utf-8")
            db = str(root / "catalog.db")
            with patch.object(main, "DB_PATH", db), patch.object(main, "DATA_DIR", str(root)):
                main.init_db()
                with self.assertRaisesRegex(Exception, "does not belong"):
                    main.resolve_project_id("first-app", "another-project")

    def test_source_import_can_create_project_and_queue_fast_map(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app_list.yml").write_text("apps: []\n", encoding="utf-8")
            db = str(root / "catalog.db")
            request = main.SourceImportRequest(
                app_id="sample-app", name="Sample", repo_url="https://example.test/sample.git",
                project_id="sample-project", project_name="Sample Project", new_project=True,
                map_mode="fast",
            )
            with patch.object(main, "DB_PATH", db), patch.object(main, "DATA_DIR", str(root)), \
                 patch.object(main.code_manager, "download_repo", return_value={"status":"success"}), \
                 patch.object(main, "_queue_map_task", return_value="task-id"):
                main.init_db()
                result = asyncio.run(main.import_source(request, "local"))
                self.assertEqual(result["project_id"], "sample-project")
                self.assertEqual(result["map_task_id"], "task-id")
                self.assertEqual(main.resolve_project_id("sample-app"), "sample-project")

    def test_full_import_requires_connected_model_and_passes_selection_to_task(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app_list.yml").write_text("apps: []\n", encoding="utf-8")
            db = str(root / "catalog.db")
            request = main.SourceImportRequest(
                app_id="full-app", name="Full", repo_url="https://example.test/full.git",
                map_mode="full", full_confirmed=True,
                model=main.ModelChoice(providerID="provider-a", modelID="model-a"),
            )
            catalog = {"providers":[{"id":"provider-a","connected":True,"models":[{"id":"model-a"}]}]}
            with patch.object(main, "DB_PATH", db), patch.object(main, "DATA_DIR", str(root)), \
                 patch.object(main.code_manager, "download_repo", return_value={"status":"success"}), \
                 patch("app.agents.settings.catalog", new=AsyncMock(return_value=catalog)), \
                 patch.object(main, "_queue_map_task", return_value="deep-task") as queue:
                main.init_db()
                result = asyncio.run(main.import_source(request, "local"))
                self.assertEqual(result["map_task_id"], "deep-task")
                queue.assert_called_once_with("full-app", "deep", {"providerID":"provider-a", "modelID":"model-a"})

    def test_full_model_rejects_provider_without_credentials(self):
        catalog = {"providers":[{"id":"provider-a","connected":False,"models":[{"id":"model-a"}]}]}
        with patch("app.agents.settings.catalog", new=AsyncMock(return_value=catalog)):
            with self.assertRaisesRegex(Exception, "Configure this model provider"):
                asyncio.run(main._validate_full_map_model(main.ModelChoice(providerID="provider-a", modelID="model-a")))


if __name__ == "__main__":
    unittest.main()
