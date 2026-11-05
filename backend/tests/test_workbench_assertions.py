from pathlib import Path
import tempfile
import sqlite3
from contextlib import closing
import unittest
from unittest.mock import patch
from app.workbench.assertions import evaluate
from app.workbench.runtime import Runtime

class AssertionTests(unittest.TestCase):
    def test_database_result_and_write_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);database=root/"fixture.db"
            with closing(sqlite3.connect(database)) as c:
                c.execute("CREATE TABLE notes(content TEXT)");c.execute("INSERT INTO notes VALUES('merged')");c.commit()
            runtime=Runtime(root/"runs")
            run={"id":"a"*32,"device_serial":"fake","conditions":[{"kind":"business","description":"One merged note","check":"notes","parameters":[],"expected_rows":[{"total":1}]}],"assertion_definitions":{"notes":{"package":"example","database":"app.db","query":"SELECT count(*) AS total FROM notes"}}}
            with patch("app.workbench.assertions.AdbDevice"),patch("app.workbench.assertions.database_snapshot",return_value=(database,{})):
                self.assertEqual(evaluate(run,runtime)[0]["status"],"passed")
                run["assertion_definitions"]["notes"]["query"]="DELETE FROM notes"
                self.assertEqual(evaluate(run,runtime)[0]["status"],"error")
            with closing(sqlite3.connect(database)) as c:self.assertEqual(c.execute("SELECT count(*) FROM notes").fetchone()[0],1)

    def test_unconfigured_description_cannot_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime=Runtime(Path(tmp));run={"id":"b"*32,"device_serial":"fake","conditions":[{"kind":"business","description":"Works"}]}
            with patch("app.workbench.assertions.AdbDevice"):
                self.assertEqual(evaluate(run,runtime)[0]["status"],"not_checked")

if __name__=="__main__":unittest.main()
