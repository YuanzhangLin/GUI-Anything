import unittest
import time
from unittest.mock import Mock,patch
from app import avd_manager as avd

class AvdManagerTests(unittest.TestCase):
    def tearDown(self):avd._managed.clear()
    @patch('app.avd_manager._devices',return_value=[])
    @patch('app.avd_manager.emulator_path',return_value='emulator')
    @patch('app.avd_manager.discover_adb',return_value='adb')
    @patch('app.avd_manager.subprocess.run')
    def test_inventory_separates_config_from_running_devices(self,run,_adb,_emulator,_devices):
        run.return_value=Mock(returncode=0,stdout=b'Pixel_API_35\n',stderr=b'')
        with patch('app.avd_manager._config',return_value={'image.sysdir.1':'system-images/android-35/google_apis/x86_64/'}):
            result=avd.inventory()
        self.assertEqual(result['avds'][0]['api'],'35');self.assertEqual(result['avds'][0]['status'],'stopped')

    @patch('app.avd_manager.inventory',return_value={'avds':[{'name':'External','status':'running','serial':'emulator-5554'}]})
    def test_never_stops_external_emulator(self,_inventory):
        with self.assertRaisesRegex(ValueError,'not started'):avd.stop('External')

    @patch('app.avd_manager._process_usage',return_value={'memory_mb':128.0})
    @patch('app.avd_manager._devices',return_value=[])
    @patch('app.avd_manager.emulator_path',return_value='emulator')
    @patch('app.avd_manager.discover_adb',return_value='adb')
    @patch('app.avd_manager.subprocess.run')
    def test_live_managed_process_is_starting_not_stopped(self,run,_adb,_emulator,_devices,_usage):
        run.return_value=Mock(returncode=0,stdout=b'Pixel\n',stderr=b'')
        process=Mock(pid=42);process.poll.return_value=None
        avd._managed['Pixel']={'process':process,'started_at':time.time()}
        with patch('app.avd_manager._config',return_value={}):result=avd.inventory()['avds'][0]
        self.assertEqual(result['status'],'starting');self.assertEqual(result['resources']['memory_mb'],128.0)

    @patch('app.avd_manager.inventory',return_value={'avds':[{'name':'Pixel','status':'starting','managed':True}]})
    def test_starting_emulator_can_be_cancelled(self,_inventory):
        process=Mock();process.wait.return_value=0
        avd._managed['Pixel']={'process':process,'started_at':time.time()}
        self.assertEqual(avd.stop('Pixel')['status'],'stopped')
        process.terminate.assert_called_once()

if __name__=='__main__':unittest.main()
