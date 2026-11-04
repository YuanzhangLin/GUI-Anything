import tempfile
import unittest
from pathlib import Path

from app.engine.uimapgenerate.fast import generate_fast_map


class ListenerTests(unittest.TestCase):
    def make_map(self, *, decompiled=False, callback="this.owner.open();", receiver="Home",
                 duplicate=False, wrong_id=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / "src" / "main"
            main.mkdir(parents=True)
            (main / "AndroidManifest.xml").write_text(
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="example">'
                '<application><activity android:name=".Home"/><activity android:name=".Detail"/>'
                '</application></manifest>', encoding="utf-8")
            lookup = "((Button) a(example.ids.open_button))" if decompiled else "findViewById(R.id.open_button)"
            binding = lookup + ".setOnClickListener(new OpenListener(this));"
            (main / "Home.java").write_text(
                'package example; public class Home extends Activity {\n'
                'public void setup() { ' + binding + (binding if duplicate else '') + ' }\n'
                'private final void open() { startActivity(new Intent(this, Detail.class)); }\n'
                'public View a(int id) { return findViewById(id); }\n'
                'public void a(String unrelated) {}\n}', encoding="utf-8")
            (main / "OpenListener.java").write_text(
                'package example; class OpenListener implements View.OnClickListener {\n'
                f'final {receiver} owner;\n'
                f'OpenListener({receiver} activity) {{ this.owner = activity; }}\n'
                f'public final void onClick(View v) {{ {callback} }}\n}}', encoding="utf-8")
            if decompiled:
                values = main / "res" / "values"
                values.mkdir(parents=True)
                (values / "public.xml").write_text(
                    '<resources><public type="id" name="open_button" id="0x7f010001"/></resources>', encoding="utf-8")
                (main / "ids.java").write_text(
                    'package example; class ids { public static final int open_button = ' +
                    ('0x7f010002' if wrong_id else '0x7f010001') + '; }', encoding="utf-8")
            return generate_fast_map("test", repo_path=root)

    def test_external_listener_resolves_with_source_evidence(self):
        for decompiled in (False, True):
            with self.subTest(decompiled=decompiled):
                graph = self.make_map(decompiled=decompiled)
                self.assertEqual(len(graph["transitions"]), 1)
                edge = graph["transitions"][0]
                self.assertEqual(edge["trigger_id"], "open_button")
                self.assertEqual(edge["trigger"]["status"], "resolved")
                self.assertIn("listener_delegate", {e["method"] for e in edge["evidence"]})
                self.assertTrue(all(e["line"] > 0 for e in edge["evidence"]))

    def test_ambiguous_or_unproved_delegates_stay_unknown(self):
        cases = [dict(callback="if (ready) this.owner.open();"),
                 dict(callback="other.open();"), dict(receiver="Other"),
                 dict(duplicate=True), dict(decompiled=True, wrong_id=True),
                 dict(callback='String misleading = "this.owner.open();";'),
                 dict(callback="/* this.owner.open(); */")]
        for options in cases:
            with self.subTest(options=options):
                edge = self.make_map(**options)["transitions"][0]
                self.assertEqual(edge["trigger"]["status"], "unknown")
                self.assertIsNone(edge["trigger_id"])


if __name__ == "__main__":
    unittest.main()
