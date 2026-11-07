from pathlib import Path
import re


def test_audit_workflow_propagates_pytest_pipeline_failures():
    workflow = Path(".github/workflows/audit.yml").read_text(encoding="utf-8")
    match = re.search(
        r"(?ms)- name: Run Unit Tests\s+run:\s*\|\s*(.*?)(?=\n\s{6}- name:)",
        workflow,
    )
    assert match is not None, "Run Unit Tests step must remain present"
    commands = match.group(1)
    lines = [line.strip() for line in commands.splitlines() if line.strip()]
    assert lines and lines[0] == "set -o pipefail"
    assert any(re.search(r"pytest\s+tests/\s+-v\s*\|\s*tee\s+pytest\.log", line) for line in lines)
