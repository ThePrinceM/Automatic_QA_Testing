"""
Root Cause Analyzer — uses LLM to analyze test failures 
and produce structured root-cause reports with fix suggestions.
"""

import json
import logging
from datetime import datetime

from pydantic import BaseModel, Field

from core.llm_engine import invoke_chain_json
from templates.prompts import ROOT_CAUSE_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)


# ── Pydantic Models ────────────────────────────────────────────

class TestFailure(BaseModel):
    """A single test failure to be analyzed."""
    test_name: str
    error_message: str
    traceback: str = ""
    duration: float = 0.0


class FailureAnalysis(BaseModel):
    """Root-cause analysis for a single failure."""
    test_name: str
    error_type: str
    probable_cause: str
    severity: str = "medium"
    suggested_fix: str = ""
    related_component: str = ""


class RootCauseReport(BaseModel):
    """Complete root-cause analysis report."""
    summary: str
    total_failures: int
    failure_analyses: list[FailureAnalysis] = Field(default_factory=list)
    common_patterns: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    analyzed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ── Analysis Functions ─────────────────────────────────────────

def analyze_failures(failures: list[TestFailure]) -> RootCauseReport:
    """
    Analyze a list of test failures using LLM and produce a 
    root-cause analysis report.
    
    Args:
        failures: List of TestFailure objects with error details.
        
    Returns:
        RootCauseReport with probable causes, patterns, and recommendations.
    """
    if not failures:
        logger.info("No failures to analyze.")
        return RootCauseReport(
            summary="No test failures detected.",
            total_failures=0,
        )
    
    logger.info(f"Analyzing {len(failures)} test failures for root causes")
    
    # Serialize failures for the LLM
    failures_text = json.dumps(
        [f.model_dump() for f in failures],
        indent=2,
    )
    
    raw_report = invoke_chain_json(
        prompt=ROOT_CAUSE_ANALYSIS_PROMPT,
        variables={"failures": failures_text},
    )
    
    # Parse failure analyses
    analyses = []
    for a_data in raw_report.get("failure_analyses", []):
        try:
            analyses.append(FailureAnalysis(**a_data))
        except Exception as e:
            logger.warning(f"Skipping malformed analysis: {e}")
    
    report = RootCauseReport(
        summary=raw_report.get("summary", "Analysis complete"),
        total_failures=raw_report.get("total_failures", len(failures)),
        failure_analyses=analyses,
        common_patterns=raw_report.get("common_patterns", []),
        recommendations=raw_report.get("recommendations", []),
    )
    
    logger.info(f"Root cause report: {report.summary}")
    return report


def format_report_text(report: RootCauseReport) -> str:
    """Format a RootCauseReport as human-readable text."""
    lines = [
        "=" * 70,
        "  ROOT CAUSE ANALYSIS REPORT",
        "=" * 70,
        "",
        f"Summary:         {report.summary}",
        f"Total Failures:  {report.total_failures}",
        f"Analyzed At:     {report.analyzed_at}",
        "",
    ]
    
    if report.failure_analyses:
        lines.append("─" * 70)
        lines.append("  FAILURE DETAILS")
        lines.append("─" * 70)
        
        for i, fa in enumerate(report.failure_analyses, 1):
            lines.extend([
                "",
                f"  [{i}] {fa.test_name}",
                f"      Error Type:  {fa.error_type}",
                f"      Severity:    {fa.severity.upper()}",
                f"      Cause:       {fa.probable_cause}",
                f"      Fix:         {fa.suggested_fix}",
                f"      Component:   {fa.related_component}",
            ])
    
    if report.common_patterns:
        lines.extend(["", "─" * 70, "  COMMON PATTERNS", "─" * 70, ""])
        for pattern in report.common_patterns:
            lines.append(f"  • {pattern}")
    
    if report.recommendations:
        lines.extend(["", "─" * 70, "  RECOMMENDATIONS", "─" * 70, ""])
        for rec in report.recommendations:
            lines.append(f"  → {rec}")
    
    lines.extend(["", "=" * 70])
    return "\n".join(lines)
