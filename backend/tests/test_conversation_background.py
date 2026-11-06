import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
from app.agents import conversations as c


class DeviceContextTests(unittest.TestCase):
    def test_each_turn_refreshes_inventory_and_selected_serial(self):
        inventory = {'available': True, 'devices': [
            {'serial': 'emulator-5554', 'state': 'device'},
            {'serial': 'emulator-5556', 'state': 'device'},
        ]}
        with patch('app.workbench.runtime.devices', return_value=inventory), \
             patch('app.navigation.device.AdbDevice._run', return_value=b'mResumedActivity: first.Main'):
            first = c.fresh_device_context('emulator-5554')
            second = c.fresh_device_context('emulator-5556')

        self.assertEqual(first['count'], 2)
        self.assertEqual(first['selected_serial'], 'emulator-5554')
        self.assertEqual(second['selected_serial'], 'emulator-5556')
        self.assertEqual([item['serial'] for item in second['devices']], ['emulator-5554', 'emulator-5556'])

class BackgroundConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_disconnect_does_not_cancel_or_resend(self):
        with tempfile.TemporaryDirectory() as root:
            db=str(Path(root)/'chat.db')
            conn=c.connection_db(db)
            conn.execute('CREATE TABLE sessions(id TEXT PRIMARY KEY,title TEXT,username TEXT,app_id TEXT)')
            conn.execute('CREATE TABLE messages(session_id TEXT,role TEXT,content TEXT)')
            conn.commit();conn.close()
            request=SimpleNamespace(username='alice',session_id='one',app_id='app',model=None,message='hello',device_screenshot='data:image/png;base64,AA==',selected_device_serial='emulator-5554')
            gate=asyncio.Event();calls=[];attachments=[]
            async def fake_stream(*args,**kwargs):
                calls.append(kwargs['text'])
                attachments.append(kwargs['attachments'])
                yield {'kind':'text_delta','part_id':'p','text':'first'}
                await gate.wait()
                yield {'kind':'text_delta','part_id':'p','text':' second'}
                yield {'kind':'done'}
            context={'available':True,'count':2,'devices':[{'serial':'emulator-5554','state':'device','type':'emulator'},{'serial':'phone','state':'device','type':'physical'}],'selected_serial':'emulator-5554','selected_state':'device','activity':'example.Main','observed_at':'now'}
            with patch.object(c.OpenCodeConnection,'create',AsyncMock(return_value='remote')),patch.object(c,'stream_reply',fake_stream),patch.object(c,'fresh_device_context',return_value=context):
                response=await c.chat(db,request,'alice',root)
                task=c._tasks['one']
                await asyncio.sleep(0)
                # Close the browser consumer while the actual generation waits.
                await response.body_iterator.__anext__()
                await response.body_iterator.aclose()
                self.assertFalse(task.done())
                self.assertTrue(c.read_events(db,'one','alice')['running'])
                with self.assertRaises(Exception): await c.chat(db,request,'alice',root)
                gate.set();await task
            self.assertEqual(len(calls),1)
            self.assertTrue(calls[0].startswith('hello'))
            self.assertIn('"count": 2',calls[0]);self.assertIn('"selected_serial": "emulator-5554"',calls[0])
            self.assertEqual(attachments[0][0]['mime'],'image/png')
            self.assertEqual(attachments[0][0]['url'],'data:image/png;base64,AA==')
            events=c.read_events(db,'one','alice')
            self.assertFalse(events['running'])
            self.assertEqual(events['events'][-1]['kind'],'turn_finished')
            conn=c.connection_db(db)
            self.assertEqual(conn.execute("SELECT content FROM messages WHERE role='assistant'").fetchone()[0],'first second')
            conn.close()
