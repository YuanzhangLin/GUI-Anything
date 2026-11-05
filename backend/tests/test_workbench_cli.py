import contextlib
import io
import os
import unittest
from unittest.mock import patch, MagicMock

from app.workbench_cli import main


class CliProtocolTests(unittest.TestCase):
    def test_verification_and_agent_routes(self):
        cases = [
            (["agents"], "GET", "/agents"),
            (["agent", "run1"], "POST", "/runs/run1/agent"),
            (["assertions", "run1"], "POST", "/runs/run1/assertions"),
            (["coverage", "run1", "baseline"], "POST", "/runs/run1/coverage/baseline"),
            (["coverage", "run1", "after"], "POST", "/runs/run1/coverage/after"),
            (["events", "run1", "--after", "42"], "GET", "/runs/run1/events?after=42"),
        ]
        for args, method, path in cases:
            with self.subTest(args=args), patch.dict(os.environ, {"GUI_WORKBENCH_TOKEN": "test-token"}), patch("app.workbench_cli.urlopen") as send, contextlib.redirect_stdout(io.StringIO()):
                response = MagicMock()
                response.read.return_value = b'{}'
                send.return_value.__enter__.return_value = response
                self.assertEqual(main(["--url", "http://localhost/api/workbench"] + args), 0)
                request = send.call_args.args[0]
                self.assertEqual(request.full_url, "http://localhost/api/workbench" + path)
                self.assertEqual(request.method, method)
                self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
