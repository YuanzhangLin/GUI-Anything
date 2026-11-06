import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import opencode_install
from app.core import opencode_agent


class ManagedOpenCodeTests(unittest.TestCase):
    def test_managed_binary_is_fallback_without_overriding_existing_install(self):
        with patch.object(opencode_agent.shutil, "which", return_value="/usr/local/bin/opencode"), \
             patch("app.opencode_install.executable", return_value="/managed/opencode") as managed:
            self.assertEqual(opencode_agent.executable_path(), "/usr/local/bin/opencode")
            managed.assert_not_called()

    def test_existing_managed_install_is_reused_without_npm(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary = Path(temporary) / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
            binary.parent.mkdir(parents=True)
            binary.touch()
            with patch.object(opencode_install, "root", return_value=Path(temporary)), \
                 patch.object(opencode_install, "_version", return_value=opencode_install.VERSION), \
                 patch.object(opencode_install.shutil, "which") as which:
                result = opencode_install.install()
            self.assertTrue(result["reused"])
            self.assertEqual(result["path"], str(binary))
            which.assert_not_called()


if __name__ == "__main__":
    unittest.main()
