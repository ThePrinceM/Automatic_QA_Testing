"""
Unit tests for the AI Test Case Generation Framework.
Tests core components with mocked LLM responses.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# ── Config Tests ──────────────────────────────────────────────

class TestConfig:
    """Tests for configuration management."""
    
    def test_config_import(self):
        """Config module should import successfully."""
        import config
        assert hasattr(config, "LLM_PROVIDER")
        assert hasattr(config, "MODEL_NAME")
        assert hasattr(config, "BASE_DIR")
    
    def test_config_defaults(self):
        """Config should have sensible defaults."""
        import config
        assert config.LLM_PROVIDER == "gemini"
        assert config.LLM_TEMPERATURE >= 0
        assert config.LLM_TEMPERATURE <= 1
        assert config.LLM_MAX_RETRIES >= 1
    
    def test_config_paths_exist(self):
        """Output directories should be created."""
        import config
        assert config.BASE_DIR.exists()
        assert config.GENERATED_TESTS_DIR.exists()
        assert config.LOGS_DIR.exists()
    
    def test_config_summary(self):
        """get_config_summary should return a dict with expected keys."""
        import config
        summary = config.get_config_summary()
        assert isinstance(summary, dict)
        assert "llm_provider" in summary
        assert "model_name" in summary


# ── Prompt Template Tests ─────────────────────────────────────

class TestPrompts:
    """Tests for LangChain prompt templates."""
    
    def test_prompts_import(self):
        """All prompt templates should import successfully."""
        from templates.prompts import (
            TEST_CASE_GENERATION_PROMPT,
            TEST_PLAN_PARSING_PROMPT,
            ROOT_CAUSE_ANALYSIS_PROMPT,
            PYTEST_CODE_GENERATION_PROMPT,
        )
        assert TEST_CASE_GENERATION_PROMPT is not None
        assert TEST_PLAN_PARSING_PROMPT is not None
        assert ROOT_CAUSE_ANALYSIS_PROMPT is not None
        assert PYTEST_CODE_GENERATION_PROMPT is not None
    
    def test_test_case_generation_prompt_variables(self):
        """Test case generation prompt should accept 'requirement' variable."""
        from templates.prompts import TEST_CASE_GENERATION_PROMPT
        # Should not raise
        messages = TEST_CASE_GENERATION_PROMPT.format_messages(
            requirement="Test requirement"
        )
        assert len(messages) > 0
    
    def test_test_plan_parsing_prompt_variables(self):
        """Test plan parsing prompt should accept 'spec_text' variable."""
        from templates.prompts import TEST_PLAN_PARSING_PROMPT
        messages = TEST_PLAN_PARSING_PROMPT.format_messages(
            spec_text="Test spec"
        )
        assert len(messages) > 0
    
    def test_root_cause_prompt_variables(self):
        """Root cause prompt should accept 'failures' variable."""
        from templates.prompts import ROOT_CAUSE_ANALYSIS_PROMPT
        messages = ROOT_CAUSE_ANALYSIS_PROMPT.format_messages(
            failures="[]"
        )
        assert len(messages) > 0


# ── Pydantic Model Tests ─────────────────────────────────────

class TestModels:
    """Tests for Pydantic data models."""
    
    def test_test_case_model(self):
        """TestCase model should accept valid data."""
        from core.test_generator import TestCase
        tc = TestCase(
            test_id="TC_001",
            test_name="test_example",
            description="Test description",
            category="functional",
            priority="high",
            preconditions=["System is running"],
            steps=["Step 1", "Step 2"],
            expected_result="Should pass",
            tags=["gpu", "driver"],
        )
        assert tc.test_id == "TC_001"
        assert tc.test_name == "test_example"
        assert len(tc.steps) == 2
    
    def test_test_suite_model(self):
        """TestSuite model should track test cases."""
        from core.test_generator import TestSuite, TestCase
        tc = TestCase(
            test_id="TC_001",
            test_name="test_example",
            description="Test",
            category="functional",
            priority="high",
        )
        suite = TestSuite(
            requirement="Test req",
            test_cases=[tc],
            total_count=1,
        )
        assert suite.total_count == 1
        assert suite.requirement == "Test req"
    
    def test_test_plan_model(self):
        """TestPlan model should structure features."""
        from core.test_plan_parser import TestPlan, Feature
        feature = Feature(
            feature_name="Memory Allocation",
            description="GPU memory allocation",
            requirements=["Allocate memory", "Free memory"],
            risk_level="high",
        )
        plan = TestPlan(
            title="Test Plan",
            summary="Summary",
            features=[feature],
            test_categories=["functional"],
            total_estimated_tests=10,
        )
        assert len(plan.features) == 1
        assert plan.features[0].feature_name == "Memory Allocation"
    
    def test_root_cause_report_model(self):
        """RootCauseReport model should structure analysis."""
        from core.root_cause_analyzer import RootCauseReport, FailureAnalysis
        fa = FailureAnalysis(
            test_name="test_alloc",
            error_type="AssertionError",
            probable_cause="Memory leak",
            severity="high",
            suggested_fix="Check deallocation",
            related_component="memory_manager",
        )
        report = RootCauseReport(
            summary="1 failure",
            total_failures=1,
            failure_analyses=[fa],
            common_patterns=["Memory issues"],
            recommendations=["Review allocation code"],
        )
        assert report.total_failures == 1
        assert len(report.failure_analyses) == 1
    
    def test_test_results_model(self):
        """TestResults model should compute pass rate."""
        from runner.test_runner import TestResults
        results = TestResults(
            total=10,
            passed=8,
            failed=2,
            errors=0,
            skipped=0,
        )
        assert results.pass_rate == 80.0
        assert results.has_failures is True

    def test_test_results_no_failures(self):
        """TestResults with all passing should report no failures."""
        from runner.test_runner import TestResults
        results = TestResults(
            total=5,
            passed=5,
            failed=0,
            errors=0,
            skipped=0,
        )
        assert results.pass_rate == 100.0
        assert results.has_failures is False


# ── Result Aggregator Tests ───────────────────────────────────

class TestResultAggregator:
    """Tests for result aggregation and formatting."""
    
    def test_aggregate_results(self):
        """Should aggregate test results into a summary."""
        from runner.test_runner import TestResults, SingleTestResult
        from runner.result_aggregator import aggregate_results
        
        results = TestResults(
            total=3,
            passed=2,
            failed=1,
            results=[
                SingleTestResult(test_name="test_a", outcome="passed"),
                SingleTestResult(test_name="test_b", outcome="passed"),
                SingleTestResult(test_name="test_c", outcome="failed"),
            ],
        )
        summary = aggregate_results(results)
        assert summary.total_tests == 3
        assert summary.passed == 2
        assert summary.failed == 1
        assert "test_c" in summary.failed_tests
    
    def test_format_summary_text(self):
        """Should format summary as readable text."""
        from runner.result_aggregator import TestSummary, format_summary_text
        
        summary = TestSummary(
            total_tests=10,
            passed=10,
            pass_rate=100.0,
        )
        text = format_summary_text(summary)
        assert "ALL TESTS PASSED" in text
        assert "10" in text


# ── Spec Loader Tests ─────────────────────────────────────────

class TestSpecLoader:
    """Tests for feature spec file loading."""
    
    def test_load_spec_file(self):
        """Should load the sample spec file."""
        from core.test_plan_parser import load_spec_file
        import config
        
        spec_path = config.SAMPLE_SPECS_DIR / "gpu_driver_spec.txt"
        if spec_path.exists():
            text = load_spec_file(spec_path)
            assert len(text) > 0
            assert "GPU" in text or "memory" in text.lower()
    
    def test_load_missing_file_raises(self):
        """Should raise FileNotFoundError for missing files."""
        from core.test_plan_parser import load_spec_file
        
        with pytest.raises(FileNotFoundError):
            load_spec_file("/nonexistent/path/to/spec.txt")
    
    def test_get_all_requirements(self):
        """Should extract flat list of requirements from test plan."""
        from core.test_plan_parser import TestPlan, Feature, get_all_requirements
        
        plan = TestPlan(
            title="Test",
            summary="Test",
            features=[
                Feature(
                    feature_name="Feature A",
                    description="Desc",
                    requirements=["Req 1", "Req 2"],
                ),
                Feature(
                    feature_name="Feature B",
                    description="Desc",
                    requirements=["Req 3"],
                ),
            ],
        )
        reqs = get_all_requirements(plan)
        assert len(reqs) == 3
        assert "[Feature A]" in reqs[0]


# ── Root Cause Formatter Tests ────────────────────────────────

class TestRootCauseFormatter:
    """Tests for root cause report formatting."""
    
    def test_format_empty_report(self):
        """Should format an empty report gracefully."""
        from core.root_cause_analyzer import RootCauseReport, format_report_text
        
        report = RootCauseReport(
            summary="No failures",
            total_failures=0,
        )
        text = format_report_text(report)
        assert "ROOT CAUSE" in text
        assert "No failures" in text
    
    def test_format_report_with_failures(self):
        """Should include failure details in formatted report."""
        from core.root_cause_analyzer import (
            RootCauseReport,
            FailureAnalysis,
            format_report_text,
        )
        
        report = RootCauseReport(
            summary="Memory issues found",
            total_failures=1,
            failure_analyses=[
                FailureAnalysis(
                    test_name="test_alloc",
                    error_type="AssertionError",
                    probable_cause="Buffer overflow",
                    severity="critical",
                    suggested_fix="Check bounds",
                    related_component="allocator",
                )
            ],
            common_patterns=["Memory corruption"],
            recommendations=["Add bounds checking"],
        )
        text = format_report_text(report)
        assert "test_alloc" in text
        assert "Buffer overflow" in text
        assert "CRITICAL" in text
