import unittest

from app.local_services import HICODE_PROVIDER


class LocalServicePresetTests(unittest.TestCase):
    def test_hicode_preset_has_endpoint_and_no_secret(self):
        self.assertEqual(HICODE_PROVIDER['options']['baseURL'],'https://api-cn.hi-code.cc/v1')
        self.assertEqual(HICODE_PROVIDER['npm'],'@ai-sdk/openai')
        self.assertIn('gpt-5.6-sol',HICODE_PROVIDER['models'])
        self.assertNotIn('apiKey',HICODE_PROVIDER['options'])


if __name__=='__main__': unittest.main()
