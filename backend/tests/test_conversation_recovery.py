import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,AsyncMock
import httpx
from fastapi import HTTPException
from app.agents import conversations as c

class RecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_recovery_preserves_text_and_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as root:
            db=str(Path(root)/'test.db');conn=c.connection_db(db)
            conn.execute('CREATE TABLE messages(session_id TEXT, role TEXT, content TEXT)');conn.commit();conn.close()
            c.record_event(db,'s',{'kind':'turn_started'})
            c.record_event(db,'s',{'kind':'text_delta','part_id':'p','text':'partial'})
            row=('alice','app',root,'remote')
            with patch.object(c.OpenCodeConnection,'abort',AsyncMock()) as abort:
                self.assertTrue(await c.recover_interrupted(db,'s',row))
                self.assertFalse(await c.recover_interrupted(db,'s',row))
                abort.assert_awaited_once()
            self.assertIsNone(c.unfinished_turn(db,'s'))
            conn=c.connection_db(db)
            rows=conn.execute('SELECT content FROM messages').fetchall();conn.close()
            self.assertEqual(len(rows),1);self.assertIn('partial',rows[0][0])

    async def test_unreachable_upstream_keeps_recovery_pending(self):
        with tempfile.TemporaryDirectory() as root:
            db=str(Path(root)/'test.db')
            c.record_event(db,'s',{'kind':'turn_started'})
            with patch.object(c.OpenCodeConnection,'abort',AsyncMock(side_effect=httpx.ConnectError('offline'))):
                with self.assertRaises(HTTPException) as failure:
                    await c.recover_interrupted(db,'s',('alice','app',root,'remote'))
            self.assertEqual(failure.exception.status_code,503)
            self.assertIsNotNone(c.unfinished_turn(db,'s'))
