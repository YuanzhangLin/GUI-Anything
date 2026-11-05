import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from app.main import app
from app.agents.device_tools import bound_run, execute_tool, ToolCall
from app.agents.conversations import connection_db

class DeviceBridgeTests(unittest.TestCase):
    def test_missing_and_wrong_service_token_rejected(self):
        with patch.dict(os.environ,{'GUI_AGENT_BRIDGE_TOKEN':'test-secret'}),TestClient(app) as client:
            for headers in [{},{'X-GUI-Agent-Token':'wrong'}]:
                r=client.post('/api/agent-tools',headers=headers,json={'session_id':'unknown','operation':'observe'})
                self.assertEqual(r.status_code,401)
                self.assertNotIn('test-secret',r.text)

    def test_unknown_or_inactive_session_cannot_operate(self):
        with tempfile.TemporaryDirectory() as root:
            db=str(Path(root)/'test.db')
            with self.assertRaises(ValueError): bound_run(db,'unknown')
            c=connection_db(db)
            c.execute('INSERT INTO agent_sessions VALUES (?,?,?,?,?)',('local','owner','app',root,'remote'))
            c.execute('INSERT INTO conversation_runs VALUES (?,?)',('local','run'))
            c.commit();c.close()
            with self.assertRaisesRegex(ValueError,'not actively'): bound_run(db,'remote')

    def test_observation_failure_blocks_run_and_preserves_reason(self):
        run = {'id': 'a' * 32, 'app_id': 'app', 'time_budget_seconds': 60}
        fake_runtime = Mock()
        fake_runtime.state.return_value = {'status': 'running', 'started': None}
        fake_runtime.observe.side_effect = RuntimeError('ADB device disconnected')
        with patch('app.agents.device_tools.bound_run', return_value=run), \
             patch('app.agents.device_tools.runtime', return_value=fake_runtime), \
             patch('app.agents.device_tools.source') as project, \
             patch('app.agents.device_tools.store') as run_store:
            run_store.return_value.check_source.return_value = {'matches': True}
            with self.assertRaisesRegex(RuntimeError, 'disconnected'):
                execute_tool('ignored.db', ToolCall(session_id='remote', operation='observe'))
        fake_runtime.block.assert_called_once()
        self.assertEqual(fake_runtime.block.call_args.args[0], run['id'])
        self.assertIn('disconnected', str(fake_runtime.block.call_args.args[1]))
