from kindle_service.planner import build_dry_run_summary


def test_build_dry_run_summary_returns_placeholder() -> None:
    assert build_dry_run_summary() == "Dry-run planning is not implemented yet."
