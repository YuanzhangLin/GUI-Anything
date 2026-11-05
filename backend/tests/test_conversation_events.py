import unittest
from app.agents.opencode import EventNormalizer
class ConversationEventTests(unittest.TestCase):
    def test_session_and_role_isolation(self):
        n=EventNormalizer('s')
        self.assertIsNone(n.accept({'type':'session.idle','properties':{'sessionID':'other'}}))
        self.assertIsNone(n.accept({'type':'message.part.updated','properties':{'sessionID':'s','part':{'messageID':'user','type':'text','id':'p','text':'input'}}}))
        n.accept({'type':'message.updated','properties':{'sessionID':'s','info':{'id':'a','role':'assistant'}}})
        self.assertEqual(n.accept({'type':'message.part.delta','properties':{'sessionID':'s','messageID':'a','field':'text','partID':'p','delta':'hello'}})['text'],'hello')
        self.assertEqual(n.accept({'type':'session.idle','properties':{'sessionID':'s'}})['kind'],'done')
