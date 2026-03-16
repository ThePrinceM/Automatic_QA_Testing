"""
Test Case Generator — converts natural language requirements 
into structured test cases and executable Pytest files.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from core.llm_engine import invoke_chain, invoke_chain_json
from templates.prompts import TEST_CASE_GENERATION_PROMPT, PYTEST_CODE_GENERATION_PROMPT

logger = logging.getLogger(__name__)


# ── Pydantic Models ────────────────────────────────────────────

class TestCase(BaseModel):
    """Schema for a single generated test case."""
    test_id: str = Field(description="Unique test case ID, e.g. TC_001")
    test_name: str = Field(description="Snake_case function name")
    description: str = Field(description="What this test validates")
    category: str = Field(description="Test category")
    priority: str = Field(description="Priority level")
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    expected_result: str = Field(default="")
    tags: list[str] = Field(default_factory=list)


class TestSuite(BaseModel):
    """A collection of generated test cases."""
    requirement: str = Field(description="Original requirement text")
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    test_cases: list[TestCase] = Field(default_factory=list)
    total_count: int = Field(default=0)


# ── Generation Functions ──────────────────────────────────────

def generate_test_cases(requirement: str) -> TestSuite:
    """
    Generate structured test cases from a natural language requirement.
    
    Args:
        requirement: Natural language description of the feature/requirement.
        
    Returns:
        TestSuite containing the generated test cases.
    """
    logger.info(f"Generating test cases for requirement ({len(requirement)} chars)")
    
    # Invoke the LLM to generate test cases
    raw_cases = invoke_chain_json(
        prompt=TEST_CASE_GENERATION_PROMPT,
        variables={"requirement": requirement},
    )
    
    # Parse into Pydantic models
    if isinstance(raw_cases, dict) and "test_cases" in raw_cases:
        raw_cases = raw_cases["test_cases"]
    
    test_cases = []
    for i, tc_data in enumerate(raw_cases):
        try:
            tc = TestCase(**tc_data)
            test_cases.append(tc)
        except Exception as e:
            logger.warning(f"Skipping malformed test case {i}: {e}")
    
    suite = TestSuite(
        requirement=requirement,
        test_cases=test_cases,
        total_count=len(test_cases),
    )
    
    logger.info(f"Generated {suite.total_count} test cases")
    return suite


def generate_pytest_file(
    test_suite: TestSuite,
    output_path: Optional[Path] = None,
) -> Path:
    """
    Generate an executable Pytest file from a TestSuite.
    
    Uses the LLM to convert structured test cases into idiomatic 
    Pytest code with proper assertions, markers, and docstrings.
    
    Args:
        test_suite: The TestSuite to convert.
        output_path: Where to write the .py file. Auto-generated if not provided.
        
    Returns:
        Path to the generated Pytest file.
    """
    import config
    
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = config.GENERATED_TESTS_DIR / f"test_generated_{timestamp}.py"
    
    # Serialize test cases to JSON for the LLM prompt
    cases_json = json.dumps(
        [tc.model_dump() for tc in test_suite.test_cases],
        indent=2,
    )
    
    logger.info(f"Generating Pytest code for {test_suite.total_count} test cases")
    
    # Use LLM to generate Pytest code
    pytest_code = invoke_chain(
        prompt=PYTEST_CODE_GENERATION_PROMPT,
        variables={"test_cases_json": cases_json},
    )
    
    # Clean up any markdown fences
    cleaned = pytest_code.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    
    # Add header comment
    header = (
        f'"""\n'
        f"Auto-generated test cases by AI Test Framework\n"
        f"Generated: {datetime.now().isoformat()}\n"
        f"Requirement: {test_suite.requirement[:100]}...\n"
        f"Total tests: {test_suite.total_count}\n"
        f'"""\n\n'
    )
    
    final_code = header + cleaned
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(final_code, encoding="utf-8")
    
    logger.info(f"Pytest file written to: {output_path}")
    return output_path


def save_test_suite_json(test_suite: TestSuite, output_path: Optional[Path] = None) -> Path:
    """Save the structured test suite as a JSON file for records."""
    import config
    
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = config.GENERATED_TESTS_DIR / f"test_suite_{timestamp}.json"
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        test_suite.model_dump_json(indent=2),
        encoding="utf-8",
    )
    
    logger.info(f"Test suite JSON saved to: {output_path}")
    return output_path
