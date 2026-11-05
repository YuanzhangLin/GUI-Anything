import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from app.core import opencode_agent, external_agent


class ProcessCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_external_prompt_file_preserves_large_request(self):
        with tempfile.TemporaryDirectory() as repo:
            process=Mock(returncode=0)
            process.communicate=AsyncMock(return_value=(b'answer',b''))
            message='evidence '*20000
            paths=[]
            async def start(*command,**kwargs):
                self.assertEqual(command[1],'--input')
                path=Path(command[2]);paths.append(path)
                self.assertEqual(path.read_text(encoding='utf-8'),message)
                return process
            with patch.object(external_agent.shutil,'which',return_value='agent'),patch.object(external_agent.CodeManager,'get_repo_path',return_value=repo),patch.object(external_agent.asyncio,'create_subprocess_exec',side_effect=start),patch.dict('os.environ',{'GUI_AGENT_EXECUTABLE':'agent','GUI_AGENT_ARGS':'["--input", "{prompt_file}"]'}):
                self.assertEqual(await external_agent.ask(message,'example'),'answer')
            self.assertFalse(paths[0].exists())

    async def test_large_opencode_request_uses_cleaned_up_attachment(self):
        with tempfile.TemporaryDirectory() as repo:
            process=Mock(returncode=0)
            process.communicate=AsyncMock(return_value=(b'{"status":"done"}',b''))
            paths=[]
            message="target evidence "*10000
            async def start(*command,**kwargs):
                self.assertLess(sum(len(arg) for arg in command),8000)
                path=Path(next(arg for arg in command if arg.endswith('request.txt')))
                self.assertIn(message,path.read_text(encoding='utf-8'))
                self.assertIn('--',command)
                paths.append(path)
                return process
            with patch.object(opencode_agent,"executable_path",return_value="opencode"),patch.object(opencode_agent.CodeManager,"get_repo_path",return_value=repo),patch.object(opencode_agent.asyncio,"create_subprocess_exec",side_effect=start):
                self.assertEqual(await opencode_agent.ask(message,"example"),'{"status":"done"}')
            self.assertFalse(paths[0].exists())

    async def test_run_timeout_cancellation_reaps_both_adapters(self):
        for module in [opencode_agent, external_agent]:
            with self.subTest(adapter=module.__name__), tempfile.TemporaryDirectory() as repo:
                process=Mock(returncode=None)
                process.communicate=AsyncMock(side_effect=[asyncio.CancelledError(),(b"",b"")])
                with patch.object(module.asyncio,"create_subprocess_exec",AsyncMock(return_value=process)), patch.object(module.CodeManager,"get_repo_path",return_value=repo), patch.object(module.shutil,"which",return_value="agent"), patch.dict("os.environ",{"GUI_AGENT_EXECUTABLE":"agent"}):
                    with self.assertRaises(asyncio.CancelledError):
                        await module.ask("test prompt","example")
                process.kill.assert_called_once()
                self.assertEqual(process.communicate.await_count,2)
