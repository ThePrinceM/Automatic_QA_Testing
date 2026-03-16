"""
Test Runner — executes generated Pytest test files programmatically 
with result capture and CI/CD-compatible exit codes.
"""

import subprocess
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

import config

logger = logging.getLogger(__name__)


# ── Pydantic Models ────────────────────────────────────────────

class SingleTestResult(BaseModel):
    """Result of a single test execution."""
    node_id: str = ""
    test_name: str = ""
    outcome: str = ""  # "passed", "failed", "error", "skipped"
    duration: float = 0.0
    error_message: str = ""
    traceback: str = ""


class TestResults(BaseModel):
    """Aggregated results from a Pytest run."""
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration: float = 0.0
    exit_code: int = 0
    test_dir: str = ""
    executed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    results: list[SingleTestResult] = Field(default_factory=list)
    stdout: str = ""
    
    @property
    def pass_rate(self) -> float:
        """Calculate pass rate as a percentage."""
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100
    
    @property
    def has_failures(self) -> bool:
        """Check if there were any failures or errors."""
        return self.failed > 0 or self.errors > 0


# ── Runner Functions ──────────────────────────────────────────

def run_tests(
    test_dir: Optional[str | Path] = None,
    extra_args: Optional[list[str]] = None,
) -> TestResults:
    """
    Run Pytest on the specified directory and capture results.
    
    Args:
        test_dir: Directory containing test files. Defaults to generated_tests/.
        extra_args: Additional Pytest CLI arguments.
        
    Returns:
        TestResults with pass/fail counts, durations, and details.
    """
    test_path = Path(test_dir) if test_dir else config.GENERATED_TESTS_DIR
    
    if not test_path.exists():
        logger.error(f"Test directory not found: {test_path}")
        return TestResults(test_dir=str(test_path), exit_code=1)
    
    # Collect test files
    test_files = list(test_path.glob("test_*.py"))
    if not test_files:
        logger.warning(f"No test files found in: {test_path}")
        return TestResults(test_dir=str(test_path))
    
    logger.info(f"Found {len(test_files)} test file(s) in {test_path}")
    
    # Build Pytest command
    json_report = test_path / ".test_results.json"
    cmd = [
        sys.executable, "-m", "pytest",
        str(test_path),
        "-v",
        "--tb=short",
        f"--json-report-file={json_report}" if _has_json_report() else "",
    ]
    
    # Add config args (skip HTML if not installed)
    for arg in config.PYTEST_ARGS:
        if "--html" in arg or "--self-contained-html" in arg:
            if _has_pytest_html():
                cmd.append(arg)
        else:
            cmd.append(arg)
    
    if extra_args:
        cmd.extend(extra_args)
    
    # Remove empty strings
    cmd = [c for c in cmd if c]
    
    logger.info(f"Running: {' '.join(cmd)}")
    
    # Execute Pytest
    start_time = datetime.now()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=str(config.BASE_DIR),
        )
        duration = (datetime.now() - start_time).total_seconds()
        
        stdout = proc.stdout
        stderr = proc.stderr
        
        logger.debug(f"Pytest stdout:\n{stdout}")
        if stderr:
            logger.debug(f"Pytest stderr:\n{stderr}")
        
        # Parse results from output
        results = _parse_pytest_output(stdout, str(test_path))
        results.exit_code = proc.returncode
        results.duration = duration
        results.stdout = stdout
        
        return results
        
    except subprocess.TimeoutExpired:
        logger.error("Pytest execution timed out after 300s")
        return TestResults(
            test_dir=str(test_path),
            exit_code=2,
            duration=300.0,
        )
    except Exception as e:
        logger.error(f"Failed to run Pytest: {e}")
        return TestResults(
            test_dir=str(test_path),
            exit_code=1,
        )


def _parse_pytest_output(output: str, test_dir: str) -> TestResults:
    """Parse Pytest verbose output to extract results."""
    results = TestResults(test_dir=test_dir)
    individual = []
    
    for line in output.split("\n"):
        line_stripped = line.strip()
        
        # Parse individual test results (verbose format)
        if " PASSED" in line_stripped or " FAILED" in line_stripped or \
           " ERROR" in line_stripped or " SKIPPED" in line_stripped:
            
            result = SingleTestResult()
            
            if " PASSED" in line_stripped:
                result.outcome = "passed"
                result.test_name = line_stripped.split(" PASSED")[0].strip()
            elif " FAILED" in line_stripped:
                result.outcome = "failed"
                result.test_name = line_stripped.split(" FAILED")[0].strip()
            elif " ERROR" in line_stripped:
                result.outcome = "error"
                result.test_name = line_stripped.split(" ERROR")[0].strip()
            elif " SKIPPED" in line_stripped:
                result.outcome = "skipped"
                result.test_name = line_stripped.split(" SKIPPED")[0].strip()
            
            result.node_id = result.test_name
            individual.append(result)
        
        # Parse summary line (e.g., "5 passed, 2 failed in 1.23s")
        if "passed" in line_stripped or "failed" in line_stripped:
            if "in " in line_stripped and "s" in line_stripped.split("in ")[-1]:
                _parse_summary_line(line_stripped, results)
    
    results.results = individual
    if results.total == 0:
        results.total = len(individual)
        results.passed = sum(1 for r in individual if r.outcome == "passed")
        results.failed = sum(1 for r in individual if r.outcome == "failed")
        results.errors = sum(1 for r in individual if r.outcome == "error")
        results.skipped = sum(1 for r in individual if r.outcome == "skipped")
    
    return results


def _parse_summary_line(line: str, results: TestResults):
    """Parse the Pytest summary line for counts."""
    import re
    
    passed = re.search(r"(\d+) passed", line)
    failed = re.search(r"(\d+) failed", line)
    errors = re.search(r"(\d+) error", line)
    skipped = re.search(r"(\d+) skipped", line)
    duration = re.search(r"in ([\d.]+)s", line)
    
    if passed:
        results.passed = int(passed.group(1))
    if failed:
        results.failed = int(failed.group(1))
    if errors:
        results.errors = int(errors.group(1))
    if skipped:
        results.skipped = int(skipped.group(1))
    if duration:
        results.duration = float(duration.group(1))
    
    results.total = results.passed + results.failed + results.errors + results.skipped


def _has_pytest_html() -> bool:
    """Check if pytest-html is installed."""
    try:
        import pytest_html  # noqa: F401
        return True
    except ImportError:
        return False


def _has_json_report() -> bool:
    """Check if pytest-json-report is installed."""
    try:
        import pytest_jsonreport  # noqa: F401
        return True
    except ImportError:
        return False
