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


@pytest.mark.unit
def test_report_payload_carries_categories_held_and_nonapplied_entries() -> None:
    """The web payload exposes held, a per-category breakdown, and the actionable
    (non-applied) entries with reasons — not just the four headline counts."""
    from chrooked_pokedex.web.targets import _report_payload

    report = ApplyReport()
    report.add(ReportEntry(status="applied", category="species", chrooked_id="goodra"))
    report.add(ReportEntry(status="applied", category="moves", chrooked_id="surf"))
    report.add(
        ReportEntry(
            status="partial", category="moves", chrooked_id="hyper_drill",
            reason="hex FunctionCode gap", partial_fields=("function_code",),
        )
    )
    report.add(
        ReportEntry(
            status="blocked", category="species", chrooked_id="lumineon",
            reason="not in target dex",
        )
    )
    report.add(
        ReportEntry(
            status="held", category="learnset", chrooked_id="gothita",
            reason="target-pinned",
        )
    )

    payload = _report_payload(report)

    assert payload["applied"] == 2
    assert payload["partial"] == 1
    assert payload["blocked"] == 1
    assert payload["held"] == 1

    assert payload["by_category"]["moves"] == {
        "applied": 1, "partial": 1, "blocked": 0, "held": 0,
    }
    assert payload["by_category"]["species"] == {
        "applied": 1, "partial": 0, "blocked": 1, "held": 0,
    }

    # Only the actionable (non-applied) entries are listed, with their reasons.
    listed = {e["chrooked_id"]: e for e in payload["entries"]}
    assert set(listed) == {"hyper_drill", "lumineon", "gothita"}
    assert listed["hyper_drill"]["status"] == "partial"
    assert listed["hyper_drill"]["category"] == "moves"
    assert listed["hyper_drill"]["partial_fields"] == ["function_code"]
    assert listed["lumineon"]["reason"] == "not in target dex"

    assert {
        "applied", "partial", "blocked", "created", "held",
        "data_only", "report_md", "by_category", "entries",
    } <= set(payload)
