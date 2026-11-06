import asyncio
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app import main


class ProjectCatalogTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
