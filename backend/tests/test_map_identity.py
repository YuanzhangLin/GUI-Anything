import asyncio
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app import main


class MapIdentityTests(unittest.TestCase):
    def test_generated_map_has_stable_id_and_source_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "app_list.yml").write_text("apps: []\n", encoding="utf-8")
            db = str(root / "catalog.db")
            task_id = "a" * 32
            with patch.object(main, "DB_PATH", db), patch.object(main, "DATA_DIR", str(root)), \
                 patch.object(main, "_source_revision", return_value="git:abc123"), \
                 patch("app.engine.uimapgenerate.fast.generate_fast_map", return_value={"schema_version":2,"screens":[],"transitions":[]}):
                main.init_db()
                main._db_execute(
                    "INSERT INTO map_tasks (id,app_id,status,progress,message,result_path,created_at) VALUES (?,?,?,?,?,?,?)",
                    (task_id,"sample","queued",0,"Queued.","",datetime.now(timezone.utc).isoformat()),
                )
                asyncio.run(main._run_map_task(task_id,"sample","fast"))
                result = json.loads((root / "sample.json").read_text(encoding="utf-8"))
                self.assertEqual(result["id"],task_id)
                self.assertEqual(result["source_revision"],"git:abc123")
                with closing(sqlite3.connect(db)) as connection:
                    row=connection.execute("SELECT id,app_id,source_revision,mode FROM maps").fetchone()
                self.assertEqual(row,(task_id,"sample","git:abc123","fast"))


if __name__ == "__main__":
    unittest.main()
