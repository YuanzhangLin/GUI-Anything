import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.engine.uimapgenerate.fast import generate_fast_map
from app.paths import validate_app_id


class FastMapTests(unittest.TestCase):
    def test_launcher_alias_marks_target_without_creating_a_fake_page(self):
        for enabled in ("true", "false"):
            with self.subTest(enabled=enabled), tempfile.TemporaryDirectory() as directory:
                main = Path(directory) / "src" / "main"
                main.mkdir(parents=True)
                (main / "AndroidManifest.xml").write_text(
                    '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="example">'
                    '<application><activity android:name=".Start"/>'
                    f'<activity-alias android:name=".Launcher" android:targetActivity=".Start" android:enabled="{enabled}">'
                    '<intent-filter><action android:name="android.intent.action.MAIN"/>'
                    '<category android:name="android.intent.category.LAUNCHER"/></intent-filter>'
                    '</activity-alias></application></manifest>', encoding="utf-8")
                graph = generate_fast_map("fixture", repo_path=directory)
                self.assertEqual(len(graph["screens"]), 1)
                page = graph["screens"][0]
                self.assertEqual(page["id"], "example.Start")
                self.assertEqual(page["entry"], enabled == "true")
                if enabled == "true":
                    self.assertEqual(page["entry_aliases"], ["example.Launcher"])

    def test_decompiled_intent_casts_and_qualified_names(self):
        for constructor in ("Intent(this, (Class<?>) DetailActivity.class)",
                            "android.content.Intent(this, (java.lang.Class<?>) example.DetailActivity.class)"):
            for statement in (f"startActivity(new {constructor});",
                              f"android.content.Intent next = new {constructor}; startActivity(next);"):
                with self.subTest(statement=statement), tempfile.TemporaryDirectory() as directory:
                    repo = Path(directory)
                    main = repo / "src" / "main"
                    main.mkdir(parents=True)
                    (main / "AndroidManifest.xml").write_text(
                        '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="example">'
                        '<application><activity android:name=".HomeActivity"/>'
                        '<activity android:name=".DetailActivity"/></application></manifest>', encoding="utf-8")
                    (main / "HomeActivity.java").write_text(
                        'package example; class HomeActivity { void open() { ' + statement +
                        ' } void unused() { android.content.Intent unused = new ' + constructor + '; } }',
                        encoding="utf-8")
                    with patch("app.engine.uimapgenerate.fast.CodeManager") as manager:
                        manager.return_value.get_repo_path.return_value = str(repo)
                        graph = generate_fast_map("fixture")
                    self.assertEqual(len(graph["transitions"]), 1)
                    self.assertEqual(graph["transitions"][0]["to"], "example.DetailActivity")

    def test_app_id_cannot_escape_repository_root(self):
        with self.assertRaises(ValueError):
            validate_app_id("../private")

    def test_manifest_pages_and_launched_intents_only(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            repo = Path(directory)
            source_set = repo / "app" / "src" / "main"
            java = source_set / "java"
            java.mkdir(parents=True)
            (source_set / "AndroidManifest.xml").write_text(
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application>'
                '<activity android:name=".HomeActivity" android:label="@string/home_title"><intent-filter>'
                '<action android:name="android.intent.action.MAIN"/>'
                '<category android:name="android.intent.category.LAUNCHER"/>'
                '</intent-filter></activity><activity android:name=".DetailActivity"/>'
                '</application></manifest>', encoding="utf-8")
            (java / "HomeActivity.java").write_text(
                'package example.app;\nclass HomeActivity extends Activity {\n'
                'void open() { setContentView(R.layout.home); startActivity(new Intent(this, DetailActivity.class)); }\n'
                'void unused() { Intent preview = new Intent(this, DetailActivity.class); }\n}',
                encoding="utf-8")
            (java / "DetailActivity.java").write_text(
                'package example.app;\nclass DetailActivity extends Activity {}', encoding="utf-8")
            values = source_set / "res" / "values"
            values.mkdir(parents=True)
            (values / "strings.xml").write_text('<resources><string name="home_title">Home</string><string name="open_detail">Open detail</string></resources>', encoding="utf-8")
            layout = source_set / "res" / "layout"
            layout.mkdir()
            (layout / "home.xml").write_text(
                '<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android">'
                '<Button android:id="@+id/open_detail" android:text="@string/open_detail"/>'
                '<TextView android:id="@+id/status" android:text="Ready"/>'
                '</LinearLayout>', encoding="utf-8")
            with patch("app.engine.uimapgenerate.fast.CodeManager") as manager:
                manager.return_value.get_repo_path.return_value = str(repo)
                graph = generate_fast_map("fixture")

        self.assertEqual(len(graph["screens"]), 2)
        self.assertEqual(len(graph["transitions"]), 1)
        self.assertTrue(next(s for s in graph["screens"] if s["title"] == "Home")["entry"])
        self.assertEqual(graph["transitions"][0]["to"], "example.app.DetailActivity")
        self.assertEqual(graph["transitions"][0]["evidence"][0]["line"], 3)
        home = next(s for s in graph["screens"] if s["title"] == "Home")
        self.assertEqual({element["id"]: element["kind"] for element in home["elements"]},
                         {"open_detail": "layout_control", "status": "display_element"})
        self.assertEqual(next(e for e in home["elements"] if e["id"] == "open_detail")["label"], "Open detail")

    def test_navigation_xml_links_fragment_pages_to_host_activity(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            repo = Path(directory)
            main = repo / "app" / "src" / "main"
            navigation = main / "res" / "navigation"
            layout = main / "res" / "layout"
            navigation.mkdir(parents=True)
            layout.mkdir(parents=True)
            (main / "AndroidManifest.xml").write_text(
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application>'
                '<activity android:name="example.HomeActivity"/></application></manifest>', encoding="utf-8")
            java = main / "java"
            java.mkdir()
            (java / "HomeActivity.java").write_text(
                'package example; class HomeActivity { void create() { setContentView(R.layout.main); } }', encoding="utf-8")
            (layout / "main.xml").write_text('<FragmentContainerView app:navGraph="@navigation/main_nav"/>', encoding="utf-8")
            (navigation / "main_nav.xml").write_text(
                '<navigation xmlns:android="http://schemas.android.com/apk/res/android" '
                'xmlns:app="http://schemas.android.com/apk/res-auto" app:startDestination="@id/home">'
                '<fragment android:id="@+id/home" android:name="example.HomeFragment">'
                '<action android:id="@+id/open_detail" app:destination="@id/detail"/></fragment>'
                '<fragment android:id="@+id/detail" android:name="example.DetailFragment"/>'
                '</navigation>', encoding="utf-8")
            with patch("app.engine.uimapgenerate.fast.CodeManager") as manager:
                manager.return_value.get_repo_path.return_value = str(repo)
                graph = generate_fast_map("fixture")
        self.assertEqual(len(graph["screens"]), 3)
        self.assertEqual({(edge["from"], edge["to"]) for edge in graph["transitions"]}, {
            ("example.HomeActivity", "example.HomeFragment"),
            ("example.HomeFragment", "example.DetailFragment"),
        })
        self.assertEqual({(item["parent"], item["child"], item["kind"]) for item in graph["containments"]}, {
            ("example.HomeActivity", "example.HomeFragment", "navigation_host"),
            ("example.HomeActivity", "example.DetailFragment", "navigation_host"),
        })

    def test_viewpager_tab_is_both_hosted_and_navigable(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            repo = Path(directory)
            main = repo / "app" / "src" / "main"
            java = main / "java"
            values = main / "res" / "values"
            java.mkdir(parents=True)
            values.mkdir(parents=True)
            (main / "AndroidManifest.xml").write_text(
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application>'
                '<activity android:name="example.HomeActivity"/></application></manifest>', encoding="utf-8")
            (java / "HomeActivity.java").write_text(
                'package example; class HomeActivity { void tabs() { '
                'adapter.addFragment(new NoteFragment(), getResources().getString(R.string.note_title)); } }', encoding="utf-8")
            (java / "NoteFragment.java").write_text('package example; class NoteFragment {}', encoding="utf-8")
            (values / "strings.xml").write_text('<resources><string name="note_title">Notes</string></resources>', encoding="utf-8")
            with patch("app.engine.uimapgenerate.fast.CodeManager") as manager:
                manager.return_value.get_repo_path.return_value = str(repo)
                graph = generate_fast_map("fixture")
        self.assertEqual(graph["containments"][0]["kind"], "tab_host")
        self.assertEqual(graph["containments"][0]["child"], "example.NoteFragment")
        self.assertEqual(graph["transitions"][0]["to"], "example.NoteFragment")

    def test_imported_target_and_intent_variable_are_a_real_path(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            repo = Path(directory)
            main = repo / "app" / "src" / "main"
            java = main / "java"
            java.mkdir(parents=True)
            (main / "AndroidManifest.xml").write_text(
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application>'
                '<activity android:name="example.home.HomeActivity"/>'
                '<activity android:name="example.detail.DetailActivity"/>'
                '</application></manifest>', encoding="utf-8")
            (java / "HomeActivity.java").write_text(
                'package example.home;\nimport example.detail.DetailActivity;\n'
                'class HomeActivity { void open() { Intent next = new Intent(this, DetailActivity.class);\n'
                'startActivity(next); } }', encoding="utf-8")
            (java / "DetailActivity.java").write_text(
                'package example.detail;\nclass DetailActivity {}', encoding="utf-8")
            with patch("app.engine.uimapgenerate.fast.CodeManager") as manager:
                manager.return_value.get_repo_path.return_value = str(repo)
                graph = generate_fast_map("fixture")
        self.assertEqual([(edge["from"], edge["to"]) for edge in graph["transitions"]],
                         [("example.home.HomeActivity", "example.detail.DetailActivity")])


if __name__ == "__main__":
    unittest.main()
