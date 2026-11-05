import unittest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app
from app.core.auth import current_user, require_admin, is_admin
from app.agents import settings

class ModelSettingsTests(unittest.TestCase):
    def tearDown(self): app.dependency_overrides.clear()

    def test_local_mode_needs_no_token_and_is_admin(self):
        self.assertEqual(current_user(None), 'local')
        self.assertTrue(is_admin('local'))

    def test_normal_user_cannot_change_shared_credentials(self):
        app.dependency_overrides[current_user]=lambda:'ordinary-user'
        with patch('app.core.auth.is_admin',return_value=False), TestClient(app) as client:
            r=client.put('/api/conversation-settings/credentials',json={'provider':'test','api_key':'never-return'})
        self.assertEqual(r.status_code,403)
        self.assertNotIn('never-return',r.text)

    def test_saved_secret_is_not_returned(self):
        app.dependency_overrides[require_admin]=lambda:'admin'
        fake=AsyncMock()
        fake.__aenter__.return_value=fake
        from unittest.mock import Mock
        fake.put.return_value=Mock()
        with patch.object(settings,'catalog',AsyncMock(return_value={'providers':[{'id':'test'}]})),patch.object(settings.OpenCodeConnection,'client',return_value=fake):
            with TestClient(app) as client:
                r=client.put('/api/conversation-settings/credentials',json={'provider':'test','api_key':'never-return'})
        self.assertEqual(r.status_code,200)
        self.assertNotIn('never-return',r.text)
        self.assertEqual(fake.put.call_args.kwargs['json'],{'type':'api','key':'never-return'})

    def test_catalog_only_exposes_allowlisted_fields(self):
        fake=AsyncMock();fake.__aenter__.return_value=fake
        from unittest.mock import Mock
        fake.get.return_value=Mock(json=lambda:{'connected':['test'],'all':[{'id':'test','name':'Test','key':'hidden','models':{'m':{'id':'m','name':'Model','apiKey':'hidden'}}}]})
        import asyncio
        with patch.object(settings.OpenCodeConnection,'client',return_value=fake): result=asyncio.run(settings.catalog())
        self.assertNotIn('hidden',str(result))
        self.assertTrue(result['providers'][0]['connected'])

    def test_model_connection_test_uses_isolated_session(self):
        app.dependency_overrides[require_admin]=lambda:'admin'
        from unittest.mock import Mock
        connection=Mock()
        connection.create=AsyncMock(return_value='temporary-session')
        fake_client=AsyncMock();fake_client.__aenter__.return_value=fake_client
        connection.client.return_value=fake_client
        async def events(*args,**kwargs):
            yield {'kind':'text_snapshot','text':'GUI_CONNECTION_OK'}
            yield {'kind':'done'}
        providers={'providers':[{'id':'test','connected':True,'models':[{'id':'m','name':'Model'}]}]}
        with patch.object(settings,'catalog',AsyncMock(return_value=providers)), \
             patch.object(settings,'OpenCodeConnection',return_value=connection), \
             patch.object(settings,'_stream_reply',side_effect=events):
            with TestClient(app) as client:
                response=client.post('/api/conversation-settings/test',json={'provider':'test','model':'m'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(connection.create.call_args.kwargs['permissions'],[{'permission':'*','pattern':'*','action':'deny'}])
        fake_client.delete.assert_awaited_once_with('/session/temporary-session')
