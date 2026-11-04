import tempfile
import unittest
from pathlib import Path

from app.engine.uimapgenerate.fast import generate_fast_map


class NavigationExtractionTests(unittest.TestCase):
    def graph(self, body, helper=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / "src" / "main"
            main.mkdir(parents=True)
            (main / "AndroidManifest.xml").write_text(
                '<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="example">'
                '<application><activity android:name=".Home"/><activity android:name=".Detail"/>'
                '<activity android:name=".Other"/></application></manifest>', encoding="utf-8")
            (main / "Home.java").write_text('package example; public class Home { ' + body + ' }', encoding="utf-8")
            if helper:
                (main / "Routes.java").write_text('package example; public class Routes { ' + helper + ' }', encoding="utf-8")
            return generate_fast_map("fixture", repo_path=root)

    def test_activity_for_result_direct_and_variable(self):
        for body in ('startActivityForResult(new Intent(this, (Class<?>) Detail.class), 42);',
                     'Intent next = new Intent(this, Detail.class); next.putExtra("key", 1); startActivityForResult(next, 42);'):
            with self.subTest(body=body):
                edges = self.graph('public void open() { ' + body + ' }')["transitions"]
                self.assertEqual([e["to"] for e in edges], ["example.Detail"])

    def test_set_class_requires_launch_and_latest_target(self):
        edges = self.graph('public void open() { Intent next = new Intent(); '
                           'next.setClass(this, Other.class); next.setClass(this, Detail.class); '
                           'startActivityForResult(next, 5); }')["transitions"]
        self.assertEqual([e["to"] for e in edges], ["example.Detail"])
        self.assertEqual(edges[0]["evidence"][0]["method"], "intent_set_class")
        self.assertEqual(self.graph('public void open() { Intent next = new Intent(); '
                                    'next.setClass(this, Detail.class); }')["transitions"], [])

    def test_dead_and_reassigned_intents_are_not_paths(self):
        cases = [
            'public void open() { Intent next = new Intent(this, Detail.class); next = other; startActivity(next); }',
            'public void unused() { Intent next = new Intent(this, Detail.class); } public void later() { startActivity(next); }',
            'public void open() { /* startActivity(new Intent(this, Detail.class)); */ }',
            'public void open() { String example = "startActivity(new Intent(this, Detail.class));"; }',
        ]
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(self.graph(body)["transitions"], [])

    def test_helper_with_cast_button_binding(self):
        body = ('public void setup() { Button launch = (Button) findViewById(R.id.launch); '
                'launch.setOnClickListener(new View.OnClickListener() { '
                'public void onClick(View v) { Routes.open(Home.this); } }); }')
        helper = 'public static void open(Activity a) { a.startActivity(new Intent(a, (Class<?>) Detail.class)); }'
        edges = self.graph(body, helper)["transitions"]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["trigger_id"], "launch")
        self.assertEqual({e["method"] for e in edges[0]["evidence"]},
                         {"navigation_helper_call", "navigation_helper_launch"})

    def test_conditional_or_overloaded_helper_is_not_inlined(self):
        for helper in (
                'public static void open(Activity a) { if (ready) a.startActivity(new Intent(a, Detail.class)); }',
                'public static void open(Activity a) { a.startActivity(new Intent(a, Detail.class)); } '
                'public static void open(String a) {}'):
            with self.subTest(helper=helper):
                self.assertEqual(self.graph('public void click() { Routes.open(this); }', helper)["transitions"], [])

    def test_listener_binding_does_not_escape_closed_callback(self):
        body = ('public void setup() { Button old = (Button) findViewById(R.id.wrong); '
                'old.setOnClickListener(new View.OnClickListener() { public void onClick(View v) { other(); } }); '
                'spinner.setOnItemSelectedListener(new Listener() { public void onItemSelected(View v) { '
                'startActivityForResult(new Intent(Home.this, Detail.class), 7); } }); }')
        edge = self.graph(body)["transitions"][0]
        self.assertIsNone(edge["trigger_id"])
        self.assertNotEqual(edge["trigger"]["status"], "resolved")

    def test_direct_view_binding_takes_precedence_over_previous_button(self):
        body = ('public void setup() { Button old = (Button) findViewById(R.id.wrong); '
                'old.setOnClickListener(new Listener() { public void onClick(View v) { other(); } }); '
                '((Button) findViewById(R.id.correct)).setOnClickListener(new Listener() { '
                'public void onClick(View v) { startActivity(new Intent(Home.this, Detail.class)); } }); }')
        self.assertEqual(self.graph(body)["transitions"][0]["trigger_id"], "correct")

    def test_reassigned_button_does_not_reuse_old_id(self):
        body = ('public void setup() { Button btn = findViewById(R.id.wrong); btn = other; '
                'btn.setOnClickListener(new Listener() { public void onClick(View v) { '
                'startActivity(new Intent(Home.this, Detail.class)); } }); }')
        self.assertIsNone(self.graph(body)["transitions"][0]["trigger_id"])

    def test_click_id_switch_and_default_branch(self):
        body = ('public void onClick(View view) { switch (view.getId()) { '
                'case R.id.open /* decompiled id */: startActivity(new Intent(this, Detail.class)); break; '
                'default: startActivity(new Intent(this, Other.class)); } }')
        edges = self.graph(body)["transitions"]
        self.assertEqual(edges[0]["trigger_id"], "open")
        self.assertIsNone(edges[1]["trigger_id"])

    def test_menu_default_does_not_inherit_previous_item(self):
        body = ('public boolean onOptionsItemSelected(MenuItem item) { switch (item.getItemId()) { '
                'case R.id.open: startActivity(new Intent(this, Detail.class)); return true; '
                'default: startActivity(new Intent(this, Other.class)); return true; } }')
        edges = self.graph(body)["transitions"]
        self.assertEqual(edges[0]["trigger_id"], "open")
        self.assertIsNone(edges[1]["trigger_id"])


if __name__ == "__main__":
    unittest.main()
