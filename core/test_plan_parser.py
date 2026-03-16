"""
Test Plan Parser — extracts structured test plans from 
feature specification documents using LLM.
"""

import json
import logging
from pathlib import Path
from datetime import datetime

from pydantic import BaseModel, Field

from core.llm_engine import invoke_chain_json
from templates.prompts import TEST_PLAN_PARSING_PROMPT

logger = logging.getLogger(__name__)


# ── Pydantic Models ────────────────────────────────────────────

class Feature(BaseModel):
    """A single feature extracted from the spec."""
    feature_name: str
    description: str
    requirements: list[str] = Field(default_factory=list)
    risk_level: str = Field(default="medium")


class TestPlan(BaseModel):
    """Structured test plan parsed from a feature specification."""
    title: str
    summary: str
    features: list[Feature] = Field(default_factory=list)
    test_categories: list[str] = Field(default_factory=list)
    total_estimated_tests: int = Field(default=0)
    parsed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    source_file: str = Field(default="")


# ── Parsing Functions ─────────────────────────────────────────

def parse_feature_spec(spec_text: str, source_file: str = "") -> TestPlan:
    """
    Parse a feature specification document and extract a structured test plan.
    
    Uses LLM to intelligently extract features, requirements, risk levels,
    and recommended test categories from the spec text.
    
    Args:
        spec_text: Raw text of the feature specification.
        source_file: Optional path to the source file for reference.
        
    Returns:
        TestPlan with extracted features and metadata.
    """
    logger.info(f"Parsing feature spec ({len(spec_text)} chars)")
    
    raw_plan = invoke_chain_json(
        prompt=TEST_PLAN_PARSING_PROMPT,
        variables={"spec_text": spec_text},
    )
    
    # Parse features
    features = []
    for f_data in raw_plan.get("features", []):
        try:
            features.append(Feature(**f_data))
        except Exception as e:
            logger.warning(f"Skipping malformed feature: {e}")
    
    plan = TestPlan(
        title=raw_plan.get("title", "Untitled Test Plan"),
        summary=raw_plan.get("summary", ""),
        features=features,
        test_categories=raw_plan.get("test_categories", []),
        total_estimated_tests=raw_plan.get("total_estimated_tests", 0),
        source_file=source_file,
    )
    
    logger.info(
        f"Parsed test plan: '{plan.title}' with {len(plan.features)} features, "
        f"~{plan.total_estimated_tests} estimated tests"
    )
    return plan


def load_spec_file(file_path: str | Path) -> str:
    """
    Load a feature specification from a file.
    
    Supports .txt and .md files.
    
    Args:
        file_path: Path to the spec file.
        
    Returns:
        The raw text content of the spec file.
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Spec file not found: {path}")
    
    if path.suffix.lower() not in (".txt", ".md", ".rst", ".text"):
        logger.warning(f"Unexpected file extension: {path.suffix}. Proceeding anyway.")
    
    text = path.read_text(encoding="utf-8")
    logger.info(f"Loaded spec file: {path.name} ({len(text)} chars)")
    return text


def get_all_requirements(test_plan: TestPlan) -> list[str]:
    """
    Extract all individual testable requirements from a test plan.
    
    Returns:
        Flat list of requirement strings, prefixed with their feature name.
    """
    requirements = []
    for feature in test_plan.features:
        for req in feature.requirements:
            requirements.append(f"[{feature.feature_name}] {req}")
    return requirements
