def detect_anomalies(logs):
    issues = []
    for l in logs:
        if "error" in l.lower():
            issues.append(l)
    return issues


def auto_fix_stub(issue):
    return f"Flagged for fix: {issue}"
