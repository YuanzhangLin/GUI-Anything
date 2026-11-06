import unittest
from unittest.mock import patch
from app.environment import diagnose

class EnvironmentDiagnosticsTests(unittest.TestCase):
    @patch('app.environment.shutil.disk_usage')
    @patch('app.environment.run',return_value=(False,'unavailable'))
    @patch('app.environment.discover_adb',return_value=None)
    @patch('app.environment.executable_path',return_value=None)
    def test_missing_tools_are_actionable(self,_open,_adb,_run,disk):
        disk.return_value=type('Usage',(),{'free':20*1024**3})()
        report=diagnose();by_id={x['id']:x for x in report['items']}
        self.assertEqual(report['schema_version'],1);self.assertEqual(report['status'],'needs_setup')
        self.assertEqual(by_id['opencode']['status'],'missing');self.assertTrue(by_id['adb']['fix'])

if __name__=='__main__':unittest.main()
