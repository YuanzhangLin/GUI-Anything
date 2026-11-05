import unittest
from app.workbench.results import summarize

class ResultTests(unittest.TestCase):
    def test_new_action_invalidates_previous_evidence(self):
        run={"conditions":[{"kind":"coverage"},{"kind":"business"}]}
        events=[{"seq":1,"kind":"coverage","payload":{"verdict":{"status":"passed"}}},
                {"seq":2,"kind":"assertions","payload":{"results":[{"condition":1,"kind":"business","status":"passed"}]}}]
        self.assertEqual(summarize(run,events)["results"]["business"],"passed")
        events.append({"seq":3,"kind":"action","payload":{}})
        result=summarize(run,events)
        self.assertEqual(result["results"]["business"],"stale")
        self.assertEqual(result["results"]["coverage"],"stale")

    def test_partial_business_checks_never_pass(self):
        run={"conditions":[{"kind":"business"},{"kind":"business"}]}
        events=[{"seq":1,"kind":"assertions","payload":{"results":[{"condition":0,"kind":"business","status":"passed"}]}}]
        self.assertEqual(summarize(run,events)["results"]["business"],"not_checked")
