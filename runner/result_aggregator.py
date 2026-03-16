"""
Result Aggregator — collects, summarizes, and formats test results 
into human-readable and machine-parseable reports.
"""

import json
import logging
from pathlib import Path
from datetime import datetime

from pydantic import BaseModel, Field

from runner.test_runner import TestResults

logger = logging.getLogger(__name__)


# ── Report Models ─────────────────────────────────────────────

class TestSummary(BaseModel):
    """High-level test execution summary."""
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    pass_rate: float = 0.0
    total_duration: float = 0.0
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    # Failure details
    failed_tests: list[str] = Field(default_factory=list)
    error_tests: list[str] = Field(default_factory=list)


# ── Aggregation Functions ─────────────────────────────────────

def aggregate_results(results: TestResults) -> TestSummary:
    """
    Aggregate raw test results into a structured summary.
    
    Args:
        results: TestResults from the test runner.
        
    Returns:
        TestSummary with pass rates, failure lists, and timing.
    """
    failed_tests = [r.test_name for r in results.results if r.outcome == "failed"]
    error_tests = [r.test_name for r in results.results if r.outcome == "error"]
    
    summary = TestSummary(
        total_tests=results.total,
        passed=results.passed,
        failed=results.failed,
        errors=results.errors,
        skipped=results.skipped,
        pass_rate=results.pass_rate,
        total_duration=results.duration,
        failed_tests=failed_tests,
        error_tests=error_tests,
    )
    
    logger.info(
        f"Results: {summary.passed}/{summary.total_tests} passed "
        f"({summary.pass_rate:.1f}%) in {summary.total_duration:.2f}s"
    )
    
    return summary


def format_summary_text(summary: TestSummary) -> str:
    """Format a TestSummary as a rich text report for console output."""
    
    # Status indicator
    if summary.pass_rate == 100:
        status = "✅ ALL TESTS PASSED"
    elif summary.pass_rate >= 80:
        status = "⚠️  SOME TESTS FAILED"
    else:
        status = "❌ SIGNIFICANT FAILURES"
    
    lines = [
        "",
        "╔" + "═" * 68 + "╗",
        "║" + "  TEST EXECUTION SUMMARY".center(68) + "║",
        "╠" + "═" * 68 + "╣",
        "║" + f"  Status:     {status}".ljust(68) + "║",
        "║" + f"  Total:      {summary.total_tests} tests".ljust(68) + "║",
        "║" + f"  Passed:     {summary.passed}".ljust(68) + "║",
        "║" + f"  Failed:     {summary.failed}".ljust(68) + "║",
        "║" + f"  Errors:     {summary.errors}".ljust(68) + "║",
        "║" + f"  Skipped:    {summary.skipped}".ljust(68) + "║",
        "║" + f"  Pass Rate:  {summary.pass_rate:.1f}%".ljust(68) + "║",
        "║" + f"  Duration:   {summary.total_duration:.2f}s".ljust(68) + "║",
        "╠" + "═" * 68 + "╣",
    ]
    
    if summary.failed_tests:
        lines.append("║" + "  FAILED TESTS:".ljust(68) + "║")
        for t in summary.failed_tests:
            display = t if len(t) <= 62 else t[:59] + "..."
            lines.append("║" + f"    ✗ {display}".ljust(68) + "║")
    
    if summary.error_tests:
        lines.append("║" + "  ERROR TESTS:".ljust(68) + "║")
        for t in summary.error_tests:
            display = t if len(t) <= 62 else t[:59] + "..."
            lines.append("║" + f"    ⚡ {display}".ljust(68) + "║")
    
    if not summary.failed_tests and not summary.error_tests:
        lines.append("║" + "  No failures detected.".ljust(68) + "║")
    
    lines.append("╚" + "═" * 68 + "╝")
    lines.append("")
    
    return "\n".join(lines)


def save_summary_json(summary: TestSummary, output_path: Path | None = None) -> Path:
    """Save the summary as a JSON file."""
    import config
    
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = config.LOGS_DIR / f"summary_{timestamp}.json"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        summary.model_dump_json(indent=2),
        encoding="utf-8",
    )
    logger.info(f"Summary saved to: {output_path}")
    return output_path
