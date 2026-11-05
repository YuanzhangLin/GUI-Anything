import tempfile
import unittest
from pathlib import Path
from fastapi import HTTPException
from app.agents.conversations import connection_db,record_event,read_events

class ConversationJournalTests(unittest.TestCase):
    def test_owner_isolation_and_cursor(self):
        with tempfile.TemporaryDirectory() as root:
            db=str(Path(root)/'events.db')
            c=connection_db(db)
            c.execute('INSERT INTO agent_sessions VALUES (?,?,?,?,?)',('local','alice','app',root,'remote'))
            c.commit();c.close()
            first=record_event(db,'local',{'kind':'tool','tool':'read','state':'running'})
            last=record_event(db,'local',{'kind':'done'})
            rows=read_events(db,'local','alice',first['seq'])['events']
            self.assertEqual(rows,[last])
            with self.assertRaises(HTTPException) as error: read_events(db,'local','bob')
            self.assertEqual(error.exception.status_code,403)
            with self.assertRaises(HTTPException): read_events(db,'missing','alice')
