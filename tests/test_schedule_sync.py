"""The schedule lives in two places; this test is how a forker learns they drifted."""

from pathlib import Path

from xtpages.config import config_crons, load, workflow_crons

ROOT = Path(__file__).resolve().parents[1]


def test_workflow_and_config_agree():
    workflow = ROOT / ".github" / "workflows" / "build.yml"
    assert workflow.exists(), "build.yml is missing"
    assert sorted(workflow_crons(workflow)) == sorted(config_crons(load(ROOT / "config.yaml")))
