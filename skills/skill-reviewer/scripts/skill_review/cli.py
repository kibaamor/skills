"""Command-line interface for the deterministic skill reviewer.

Imported by scripts/review_skill.py; run that entry point with --help for
command-line usage.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

from .aggregate import aggregate
from .fs_safety import is_reparse_stat
from .output import write_aggregate_output
from .report import render_text
from .static_review import static_review
from .validate_evals import validate_evals
from .validate_triggers import validate_triggers

EXIT_CODES = (
    "Exit codes: 0 completed without error findings; 1 completed with error "
    "findings; 2 fatal CLI, filesystem, JSON parse, or output failure."
)


def write_result(result: dict[str, Any], args: argparse.Namespace) -> None:
    if args.format == "text":
        rendered = render_text(result) + "\n"
    else:
        rendered = (
            json.dumps(
                result,
                indent=2 if args.pretty else None,
                ensure_ascii=False,
                sort_keys=False,
            )
            + "\n"
        )
    output = getattr(args, "output", None)
    if output and output != "-":
        iteration = getattr(args, "iteration", None)
        if iteration is None:
            raise ValueError("File output is supported only for aggregate results.")
        resolved_iteration = Path(
            getattr(args, "_resolved_iteration", result["subject"])
        )
        write_aggregate_output(
            iteration,
            output,
            rendered,
            force=bool(getattr(args, "force", False)),
            resolved_iteration=resolved_iteration,
            expected_root_info=getattr(args, "_iteration_root_info", None),
        )
    sys.stdout.write(rendered)


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def add_output_options(
    parser: argparse.ArgumentParser, allow_output: bool = False
) -> None:
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument(
        "--max-findings",
        type=positive_int,
        default=100,
        help="Maximum findings returned; summary counts remain complete (default: 100).",
    )
    if allow_output:
        parser.add_argument(
            "--output",
            metavar="FILE",
            help=(
                "Also write the rendered result atomically to FILE inside the "
                "iteration; existing entries require --force and findings remain "
                "subject to --max-findings. Use - for stdout only."
            ),
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Safely replace an existing ordinary output file; links are rejected.",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministic, non-executing checks for Agent Skill reviews.",
        epilog=EXIT_CODES,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    static_parser = subparsers.add_parser(
        "static", help="Inspect a skill without executing its scripts.", epilog=EXIT_CODES
    )
    static_parser.add_argument("target", help="Path to the target skill directory.")
    add_output_options(static_parser)

    evals_parser = subparsers.add_parser(
        "validate-evals",
        help="Validate an evals/evals.json definition and fixture paths.",
        epilog=EXIT_CODES,
    )
    evals_parser.add_argument("evals_json", help="Path to evals/evals.json.")
    add_output_options(evals_parser)

    triggers_parser = subparsers.add_parser(
        "validate-triggers",
        help="Validate a trigger query JSON definition and its coverage.",
        epilog=EXIT_CODES,
    )
    triggers_parser.add_argument(
        "trigger_queries_json", help="Path to evals/trigger_queries.json."
    )
    add_output_options(triggers_parser)

    aggregate_parser = subparsers.add_parser(
        "aggregate",
        help="Aggregate paired grading.json and timing.json run data.",
        epilog=EXIT_CODES,
    )
    aggregate_parser.add_argument(
        "iteration", help="Path containing eval-* run directories."
    )
    aggregate_parser.add_argument(
        "--candidate",
        default="with_skill",
        help="Candidate configuration name (default: with_skill).",
    )
    aggregate_parser.add_argument(
        "--baseline",
        default="without_skill",
        help="Baseline configuration name (default: without_skill).",
    )
    add_output_options(aggregate_parser, allow_output=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "static":
            result, status = static_review(Path(args.target), args.max_findings)
        elif args.command == "validate-evals":
            result, status = validate_evals(Path(args.evals_json), args.max_findings)
        elif args.command == "validate-triggers":
            result, status = validate_triggers(
                Path(args.trigger_queries_json), args.max_findings
            )
        else:
            resolved_iteration = Path(args.iteration).resolve(strict=True)
            iteration_root_info = os.lstat(resolved_iteration)
            if not stat.S_ISDIR(iteration_root_info.st_mode) or is_reparse_stat(
                iteration_root_info
            ):
                raise ValueError(
                    "Resolved iteration root must be an ordinary directory."
                )
            args._resolved_iteration = resolved_iteration
            args._iteration_root_info = iteration_root_info
            result, status = aggregate(
                resolved_iteration,
                args.candidate,
                args.baseline,
                args.max_findings,
            )
        write_result(result, args)
        return status
    except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
        sys.stderr.write(f"Error: {exc}\n")
        sys.stderr.write(f"Try: {Path(sys.argv[0]).name} {args.command} --help\n")
        return 2
