"""
AI-Powered Test Case Generation & Automation Framework
======================================================

Main application entry point and CLI orchestrator.
Parses feature specifications, generates test cases via LLM,
runs them with Pytest, and produces root-cause analysis reports.

Tech Stack: Python, LangChain, Gemini API, Pytest, GitHub Actions

Usage:
    python App.py --spec <spec_file>          Generate & run tests from spec
    python App.py --requirement "<text>"      Generate tests from inline text
    python App.py --run-only [dir]            Run existing tests only
    python App.py --analyze <results.json>    Analyze past failures
    python App.py --help                      Show help
"""

import argparse
import sys
import json
import time
from pathlib import Path
from datetime import datetime

# ── Framework Imports ──────────────────────────────────────────
import config
from runner.logger import setup_logging, get_logger
from core.test_plan_parser import parse_feature_spec, load_spec_file, get_all_requirements
from core.test_generator import generate_test_cases, generate_pytest_file, save_test_suite_json
from core.root_cause_analyzer import (
    analyze_failures,
    format_report_text,
    TestFailure,
)
from runner.test_runner import run_tests
from runner.result_aggregator import aggregate_results, format_summary_text, save_summary_json


# ── Constants ──────────────────────────────────────────────────

BANNER = r"""
╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║     █████╗ ██╗    ████████╗███████╗███████╗████████╗                 ║
║    ██╔══██╗██║    ╚══██╔══╝██╔════╝██╔════╝╚══██╔══╝                ║
║    ███████║██║       ██║   █████╗  ███████╗   ██║                    ║
║    ██╔══██║██║       ██║   ██╔══╝  ╚════██║   ██║                   ║
║    ██║  ██║██║       ██║   ███████╗███████║   ██║                    ║
║    ╚═╝  ╚═╝╚═╝       ╚═╝   ╚══════╝╚══════╝   ╚═╝                    ║
║                                                                      ║
║    AI-Powered Test Case Generation & Automation Framework            ║
║    Targeting NVIDIA GPU Driver & Simulation QA Pipelines             ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""


def print_banner():
    """Display the application banner."""
    print(BANNER)


def print_config_info(logger):
    """Log the current configuration."""
    cfg = config.get_config_summary()
    logger.info("Configuration:")
    for key, value in cfg.items():
        logger.info(f"  {key}: {value}")


# ── CLI Argument Parser ───────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="AI Test Framework",
        description=(
            "AI-Powered Test Case Generation & Automation Framework. "
            "Generates test cases from natural language specs using LLM, "
            "runs them with Pytest, and provides root-cause analysis."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python App.py --spec sample_specs/gpu_driver_spec.txt\n"
            "  python App.py --requirement \"User login must validate email format\"\n"
            "  python App.py --run-only generated_tests/\n"
            "  python App.py --spec sample_specs/gpu_driver_spec.txt --generate-only\n"
        ),
    )
    
    # Input sources (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "--spec", "-s",
        type=str,
        help="Path to a feature specification file (.txt or .md)",
    )
    input_group.add_argument(
        "--requirement", "-r",
        type=str,
        help="Inline natural language requirement text",
    )
    input_group.add_argument(
        "--run-only",
        type=str,
        nargs="?",
        const=str(config.GENERATED_TESTS_DIR),
        help="Run existing tests only (skip generation). Optionally specify test dir.",
    )
    
    # Options
    parser.add_argument(
        "--generate-only", "-g",
        action="store_true",
        help="Generate test cases without running them",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Output directory for generated tests",
    )
    parser.add_argument(
        "--no-rca",
        action="store_true",
        help="Skip root-cause analysis on failures",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )

    
    return parser


# ── Workflow Steps ────────────────────────────────────────────

def step_parse_spec(spec_path: str, logger) -> list[str]:
    """Step 1: Parse feature spec into requirements."""
    logger.info(f"📄 Loading feature specification: {spec_path}")
    spec_text = load_spec_file(spec_path)
    
    logger.info("🔍 Parsing specification with LLM...")
    test_plan = parse_feature_spec(spec_text, source_file=spec_path)
    
    logger.info(f"📋 Test Plan: {test_plan.title}")
    logger.info(f"   Features: {len(test_plan.features)}")
    logger.info(f"   Estimated tests: {test_plan.total_estimated_tests}")
    
    for feature in test_plan.features:
        logger.info(f"   • {feature.feature_name} (risk: {feature.risk_level})")
    
    requirements = get_all_requirements(test_plan)
    logger.info(f"   Extracted {len(requirements)} testable requirements")
    
    return requirements


def step_generate_tests(requirements: list[str], output_dir: Path | None, logger) -> list[Path]:
    """Step 2: Generate test cases from requirements."""
    generated_files = []
    
    for i, req in enumerate(requirements, 1):
        logger.info(f"🧪 Generating tests for requirement {i}/{len(requirements)}")
        logger.info(f"   Requirement: {req[:80]}...")
        
        try:
            # Generate structured test cases
            suite = generate_test_cases(req)
            logger.info(f"   Generated {suite.total_count} test cases")
            
            # Save JSON record
            save_test_suite_json(suite)
            
            # Generate executable Pytest file
            if output_dir:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_path = output_dir / f"test_req_{i}_{timestamp}.py"
            else:
                out_path = None
            
            pytest_file = generate_pytest_file(suite, out_path)
            generated_files.append(pytest_file)
            logger.info(f"   ✅ Pytest file: {pytest_file.name}")
            
        except Exception as e:
            logger.error(f"   ❌ Failed to generate tests for requirement {i}: {e}")
    
    return generated_files


def step_run_tests(test_dir: str | Path | None, logger):
    """Step 3: Run generated tests."""
    logger.info("🚀 Running generated tests with Pytest...")
    
    results = run_tests(test_dir)
    summary = aggregate_results(results)
    
    # Display summary
    print(format_summary_text(summary))
    
    # Save summary
    save_summary_json(summary)
    
    return results, summary


def step_root_cause_analysis(results, logger):
    """Step 4: Analyze failures with LLM."""
    failures = [
        TestFailure(
            test_name=r.test_name,
            error_message=r.error_message or r.outcome,
            traceback=r.traceback,
            duration=r.duration,
        )
        for r in results.results
        if r.outcome in ("failed", "error")
    ]
    
    if not failures:
        logger.info("🎉 No failures to analyze!")
        return None
    
    logger.info(f"🔬 Analyzing {len(failures)} failure(s) with LLM...")
    report = analyze_failures(failures)
    
    # Display report
    print(format_report_text(report))
    
    return report


# ── Main Entry Point ──────────────────────────────────────────

def main():
    """Main application entry point."""
    # Ensure UTF-8 output on Windows terminals
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    
    parser = build_parser()
    args = parser.parse_args()
    
    # Show help if no arguments
    if len(sys.argv) == 1:
        print_banner()
        parser.print_help()
        sys.exit(0)
    
    # Setup
    log_level = "DEBUG" if args.verbose else None
    setup_logging(log_level)
    logger = get_logger("app")
    

    
    print_banner()
    print_config_info(logger)
    
    start_time = time.time()
    
    # ── Handle --run-only mode ─────────────────────────────
    if args.run_only:
        results, summary = step_run_tests(args.run_only, logger)
        
        if results.has_failures and not args.no_rca:
            step_root_cause_analysis(results, logger)
        
        elapsed = time.time() - start_time
        logger.info(f"⏱️  Total time: {elapsed:.2f}s")
        sys.exit(results.exit_code)
    
    # ── Parse requirements ─────────────────────────────────
    requirements = []
    
    if args.spec:
        requirements = step_parse_spec(args.spec, logger)
    elif args.requirement:
        requirements = [args.requirement]
    else:
        logger.error("No input provided. Use --spec or --requirement.")
        parser.print_help()
        sys.exit(1)
    
    # ── Generate tests ─────────────────────────────────────
    output_dir = Path(args.output) if args.output else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
    
    generated_files = step_generate_tests(requirements, output_dir, logger)
    
    if not generated_files:
        logger.error("No test files were generated.")
        sys.exit(1)
    
    logger.info(f"📁 Generated {len(generated_files)} test file(s)")
    
    # ── Stop here if --generate-only ───────────────────────
    if args.generate_only:
        logger.info("✅ Generation complete (--generate-only mode)")
        elapsed = time.time() - start_time
        logger.info(f"⏱️  Total time: {elapsed:.2f}s")
        sys.exit(0)
    
    # ── Run tests ──────────────────────────────────────────
    test_dir = output_dir or config.GENERATED_TESTS_DIR
    results, summary = step_run_tests(test_dir, logger)
    
    # ── Root-cause analysis ────────────────────────────────
    if results.has_failures and not args.no_rca:
        step_root_cause_analysis(results, logger)
    
    # ── Done ───────────────────────────────────────────────
    elapsed = time.time() - start_time
    logger.info(f"⏱️  Total time: {elapsed:.2f}s")
    logger.info("🏁 Framework execution complete.")
    
    sys.exit(results.exit_code)


if __name__ == "__main__":
    main()
