"""Derive conclusions only from current, independent evidence."""
def summarize(run, events):
    action_seq = max((e["seq"] for e in events if e["kind"] == "action"), default=0)
    coverage_event = next((e for e in reversed(events) if e["kind"] == "coverage" and "verdict" in e["payload"]), None)
    assertion_event = next((e for e in reversed(events) if e["kind"] == "assertions"), None)
    coverage = coverage_event["payload"]["verdict"] if coverage_event else None
    assertions = assertion_event["payload"]["results"] if assertion_event else []
    coverage_status = coverage["status"] if coverage else "not_checked"
    if coverage_event and coverage_event["seq"] < action_seq:
        coverage_status = "stale"
    statuses = []
    for index, condition in enumerate(run["conditions"]):
        if condition["kind"] == "coverage":
            status = coverage_status
        else:
            result = next((a for a in assertions if a["condition"] == index), None)
            status = result["status"] if result else "not_checked"
            if result and assertion_event["seq"] < action_seq: status = "stale"
        statuses.append({"condition": index, "kind": condition["kind"], "status": status})
    def combined(kind):
        values = [v["status"] for v in statuses if v["kind"] == kind]
        if not values: return "not_checked"
        for status in ["stale", "error", "not_checked", "failed"]:
            if status in values: return status
        return "passed" if all(v == "passed" for v in values) else "not_checked"
    return {"results": {"coverage": coverage_status, "business": combined("business"), "ui": combined("ui")},
            "condition_results": statuses, "coverage_verdict": coverage, "assertions": assertions}
