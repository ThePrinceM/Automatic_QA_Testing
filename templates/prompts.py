"""
LangChain LLM prompt templates for test case generation, 
test plan parsing, and failure root-cause analysis.
"""

from langchain_core.prompts import ChatPromptTemplate

# ═══════════════════════════════════════════════════════════════
# Test Case Generation Prompt
# ═══════════════════════════════════════════════════════════════
TEST_CASE_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert QA engineer specializing in GPU driver testing, 
simulation pipelines, and hardware/software integration testing at NVIDIA.

Your task is to generate comprehensive, structured test cases from a natural language 
software requirement description. Target test categories commonly found in GPU driver 
and simulation testing pipelines.

Output ONLY valid JSON — no markdown, no commentary. Return a JSON array of test case 
objects. Each object must have exactly these fields:

- "test_id": string (e.g. "TC_001")
- "test_name": string (snake_case function name, e.g. "test_driver_initialization")
- "description": string (what this test validates)
- "category": string (one of: "functional", "performance", "edge_case", "integration", "regression", "stress")
- "priority": string (one of: "critical", "high", "medium", "low")
- "preconditions": list of strings
- "steps": list of strings (concrete test steps)
- "expected_result": string
- "tags": list of strings (e.g. ["gpu", "driver", "memory"])
"""),
    ("human", """Generate test cases for the following software requirement:

--- REQUIREMENT ---
{requirement}
--- END REQUIREMENT ---

Generate between 5 and 10 thorough test cases covering functional, edge-case, 
performance, and integration scenarios. Return ONLY the JSON array."""),
])


# ═══════════════════════════════════════════════════════════════
# Feature Spec → Test Plan Parsing Prompt
# ═══════════════════════════════════════════════════════════════
TEST_PLAN_PARSING_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a senior QA architect at NVIDIA. Your role is to parse a 
feature specification document and extract a structured test plan.

Output ONLY valid JSON with this structure:
{{
    "title": "Test plan title",
    "summary": "Brief summary of what is being tested",
    "features": [
        {{
            "feature_name": "Name of the feature",
            "description": "What the feature does",
            "requirements": [
                "Specific testable requirement 1",
                "Specific testable requirement 2"
            ],
            "risk_level": "high" | "medium" | "low"
        }}
    ],
    "test_categories": ["functional", "performance", ...],
    "total_estimated_tests": integer
}}
"""),
    ("human", """Parse the following feature specification and extract a structured test plan:

--- FEATURE SPECIFICATION ---
{spec_text}
--- END SPECIFICATION ---

Return ONLY the JSON object."""),
])


# ═══════════════════════════════════════════════════════════════
# Failure Root-Cause Analysis Prompt
# ═══════════════════════════════════════════════════════════════
ROOT_CAUSE_ANALYSIS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert debugging engineer at NVIDIA specializing in 
root-cause analysis of test failures in GPU drivers and simulation pipelines.

Analyze the provided test failure data and produce a structured root-cause report.

Output ONLY valid JSON with this structure:
{{
    "summary": "One-line summary of the overall failure pattern",
    "total_failures": integer,
    "failure_analyses": [
        {{
            "test_name": "Name of the failed test",
            "error_type": "Type of error (e.g. AssertionError, TimeoutError, etc.)",
            "probable_cause": "Most likely root cause",
            "severity": "critical" | "high" | "medium" | "low",
            "suggested_fix": "Recommended action to fix",
            "related_component": "Which component/module is likely affected"
        }}
    ],
    "common_patterns": ["Pattern 1", "Pattern 2"],
    "recommendations": ["Overall recommendation 1", "Overall recommendation 2"]
}}
"""),
    ("human", """Analyze the following test failure data and provide root-cause analysis:

--- TEST FAILURES ---
{failures}
--- END FAILURES ---

Return ONLY the JSON object."""),
])


# ═══════════════════════════════════════════════════════════════
# Pytest Code Generation Prompt
# ═══════════════════════════════════════════════════════════════
PYTEST_CODE_GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert Python test engineer. Convert structured test case 
definitions into executable Pytest test functions.

Rules:
- Import pytest at the top
- Each test case becomes a function named with the test_name field
- Include the description as a docstring
- Use pytest assertions
- Add pytest.mark decorators for category and priority
- Include TODO comments where real implementation calls should go
- Make tests realistic but use mock/placeholder assertions where actual 
  system calls would be needed
- Add proper setup/teardown if preconditions mention it

Return ONLY valid Python code — no markdown fences, no explanation."""),
    ("human", """Convert these test cases into executable Pytest code:

--- TEST CASES (JSON) ---
{test_cases_json}
--- END TEST CASES ---

Generate complete, runnable Pytest code."""),
])
