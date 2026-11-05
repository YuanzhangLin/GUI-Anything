from pathlib import Path
import tempfile
import unittest
from app.workbench.coverage import compare_reports

class CoverageTests(unittest.TestCase):
    def test_zero_to_hit_and_business_independence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            xml='<report><package name="example"><sourcefile name="Main.java"><line nr="2" mi="{mi}" ci="{ci}" mb="1" cb="1"/></sourcefile></package></report>'
            (root/"before.xml").write_text(xml.format(mi=4,ci=0))
            (root/"after.xml").write_text(xml.format(mi=0,ci=4))
            result=compare_reports(root/"before.xml",root/"after.xml","example","Main.java",1,3)
            self.assertEqual(result["status"],"passed")
            self.assertEqual(result["business_status"],"not_checked")
            self.assertEqual(result["lines"][0]["new_branches"],0)
            result=compare_reports(root/"after.xml",root/"after.xml","example","Main.java",1,3)
            self.assertEqual(result["status"],"failed")
            with self.assertRaises(ValueError): compare_reports(root/"before.xml",root/"after.xml","example","Main.java",4,5)

if __name__=="__main__":unittest.main()
