"""The Apply Report carries a fourth status, `held`, for target-pinned categories."""

from __future__ import annotations

import json

import pytest

from chrooked_pokedex.report.report import ApplyReport, ReportEntry


@pytest.mark.unit
def test_counts_include_held() -> None:
    report = ApplyReport()
    report.add(ReportEntry(status="applied", category="species", chrooked_id="goodra"))
    report.add(
        ReportEntry(
            status="held", category="learnset", chrooked_id="gothita",
            reason="target-pinned",
        )
    )
    counts = report.counts()
    assert counts == {"applied": 1, "partial": 0, "blocked": 0, "held": 1}


@pytest.mark.unit
def test_held_renders_in_markdown_and_json() -> None:
    report = ApplyReport()
    report.add(
        ReportEntry(
            status="held", category="abilities", chrooked_id="gothita",
            reason="target-pinned",
        )
    )
    md = report.to_markdown()
    assert "- held: 1" in md
    assert "| held | abilities | gothita |  | target-pinned |" in md

    payload = json.loads(report.to_json())
    assert payload["counts"]["held"] == 1
    assert payload["entries"][0]["status"] == "held"
