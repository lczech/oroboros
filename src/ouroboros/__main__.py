from __future__ import annotations

import argparse
from typing import Sequence

from .find_headers import HeaderFile, find_all_headers, find_included_headers


def _format_header_file(header_file: HeaderFile) -> str:
    return f"{header_file.relative_path}\t{header_file.full_path}"


def _run_find_headers(args: argparse.Namespace) -> int:
    if args.header_file is None:
        header_files = find_all_headers(args.header_dir)
    else:
        header_files = find_included_headers(args.header_dir, args.header_file)

    for header_file in header_files:
        print(_format_header_file(header_file))

    return 0


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ouroboros command line interface.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    find_headers_parser = subparsers.add_parser(
        "find-headers",
        help="List project headers or included project headers.",
    )
    find_headers_parser.add_argument(
        "--header-dir",
        required=True,
        help="Base directory that contains project header files. All headers in that directory and its subdirectories will be considered project headers for which bindings will be generated.",
    )
    find_headers_parser.add_argument(
        "--header-file",
        help="Optional root header file used to collect recursively included project headers. If given, only project headers that are included (directly or indirectly) from the specified root header will be listed. The path should be relative to the header directory.",
    )
    find_headers_parser.set_defaults(handler=_run_find_headers)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the project-wide Ouroboros command line interface."""

    parser = _build_argument_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
