import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.engine.uimapgenerate.fast import generate_fast_map
from app.services.apk_import import import_apk_file
from app.services.code_manager import CodeManager


class ApkImportTests(unittest.TestCase):
    def test_jadx_output_becomes_an_apk_sourced_fast_map(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            root = Path(directory)
            apk = root / "sample.apk"
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("AndroidManifest.xml", b"binary-manifest-placeholder")
                archive.writestr("classes.dex", b"dex-placeholder")

            def fake_jadx(command, **_kwargs):
                output = Path(command[command.index("--output-dir") + 1])
                resources = output / "resources"
                sources = output / "sources" / "example" / "app"
                resources.mkdir(parents=True)
                sources.mkdir(parents=True)
                (resources / "AndroidManifest.xml").write_text(
                    '<manifest package="example.app" xmlns:android="http://schemas.android.com/apk/res/android">'
                    '<application><activity android:name=".HomeActivity"/><activity android:name=".DetailActivity"/>'
                    '</application></manifest>', encoding="utf-8")
                (sources / "HomeActivity.java").write_text(
                    'package example.app;\nclass HomeActivity { void open() { startActivity(new Intent(this, DetailActivity.class)); } }',
                    encoding="utf-8")
                (sources / "DetailActivity.java").write_text('package example.app; class DetailActivity {}', encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("app.services.apk_import.subprocess.run", side_effect=fake_jadx):
                project = import_apk_file("sample", apk, root / "repos")
            self.assertEqual(CodeManager(repos_root=str(root / "repos")).check_status("sample"), "ready")
            with patch("app.engine.uimapgenerate.fast.CodeManager") as manager:
                manager.return_value.get_repo_path.return_value = str(project)
                graph = generate_fast_map("sample")
            self.assertEqual(graph["source"], "apk_decompiled")
            self.assertEqual(len(graph["transitions"]), 1)
            self.assertEqual(graph["transitions"][0]["verification"], "decompiled_rule")


if __name__ == "__main__":
    unittest.main()
