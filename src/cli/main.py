from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.cli.commands import report_command, translate_command, validate_command
from src.infra.config import load_config
from src.infra.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mdtx", description="Agent-based Markdown translation pipeline.")
    parser.add_argument("--config", help="Path to config.yaml", default=None)
    parser.add_argument("--verbose", action="store_true", help="Enable more detailed logs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    translate = subparsers.add_parser("translate", help="Translate one or more markdown files.")
    translate.add_argument("paths", nargs="+", help="Markdown files to translate.")
    translate.add_argument("--to", nargs="+", help="Target languages. Defaults to config.yaml.")
    translate.add_argument("--output", help="Explicit output file path. Only valid for one input file and one target language.")

    validate = subparsers.add_parser("validate", help="Validate a markdown file.")
    validate.add_argument("path", help="Markdown file to validate.")

    report = subparsers.add_parser("report", help="Generate a report without writing output.")
    report.add_argument("path", help="Markdown file to inspect.")
    report.add_argument("--to", required=True, help="Target language.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(logging.DEBUG if args.verbose else logging.INFO)
    config = load_config(args.config)

    if args.command == "translate":
        return translate_command(args.paths, args.to or config.target_languages, config, args.output)
    if args.command == "validate":
        return validate_command(args.path, config)
    if args.command == "report":
        return report_command(args.path, args.to, config)
    return 1


if __name__ == "__main__":
    sys.exit(main())
