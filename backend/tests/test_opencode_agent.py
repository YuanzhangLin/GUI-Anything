import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core import opencode_agent


class OpenCodeAdapterTests(unittest.TestCase):
    def test_launches_in_project_and_attaches_skill(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            repo = Path(directory)
            class Process:
                returncode = 0

                async def communicate(self):
                    return b"Map analysis complete", b""

            launched = []

            async def launch(*args, **kwargs):
                request=Path(next(arg for arg in args if arg.endswith("request.txt")))
                self.assertIn("Explain the route",request.read_text(encoding="utf-8"))
                launched.append((args, kwargs))
                return Process()

            async def await_directly(coroutine, timeout):
                return await coroutine

            with patch.object(opencode_agent.shutil, "which", return_value="/usr/bin/opencode"), \
                 patch.object(opencode_agent.CodeManager, "get_repo_path", return_value=str(repo)), \
                 patch.object(opencode_agent.asyncio, "create_subprocess_exec", side_effect=launch), \
                 patch.object(opencode_agent.asyncio, "wait_for", side_effect=await_directly):
                operation = opencode_agent.ask("Explain the route", "activitydiary")
                with self.assertRaises(StopIteration) as completed:
                    operation.send(None)
                result = completed.exception.value
        self.assertEqual(result, "Map analysis complete")
        args, kwargs = launched[0]
        self.assertEqual(args[:3], ("/usr/bin/opencode", "run", "--dir"))
        self.assertEqual(args[3], str(repo))
        self.assertIn("--file", args)
        skill = Path(args[args.index("--file") + 1])
        self.assertTrue(skill.is_file())
        self.assertEqual(skill.name, "SKILL.md")
        self.assertIn("request.txt", args[-1])
        self.assertEqual(kwargs["env"]["OPENCODE_CONFIG_CONTENT"],
                         '{"permission": {"edit": "deny", "bash": "deny"}}')


if __name__ == "__main__":
    unittest.main()
