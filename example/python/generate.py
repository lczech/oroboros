from __future__ import annotations

"""Example Oroboros driver for the bundled cosmos library."""

from pathlib import Path
import sys

from oroboros import (
    HeaderFile,
    HeaderSelection,
    find_included_headers,
    infer_parser_config_from_compilation_database,
    parse_header_selection,
    print_parse_result,
    print_parser_config,
    print_update_report,
    update_activation_header,
)
from oroboros.diagnostics import print_report


def _discover_parser_inventory(header_dir: Path, root_header: Path) -> list[HeaderFile]:
    """Return the concrete public headers that should currently feed the parser,
    as a temporary solution to not have the umbrella header in this example before the parser
    can handle it. Will be removed later, when duplicates from the umbrella and concrete
    headers can be merged."""

    header_files = find_included_headers(header_dir, root_header)
    return [
        header_file
        for header_file in header_files
        if header_file.relative_path != Path("cosmos/cosmos.hpp")
    ]


def main() -> int:
    """Update the activation header and run the current parser on the example."""

    # Path setup for the example.
    repo_root = Path(__file__).resolve().parents[2]
    build_dir = repo_root / "build"
    header_dir = repo_root / "example" / "inc"
    root_header = header_dir / "cosmos" / "cosmos.hpp"
    activation_header = repo_root / "example" / "python" / "active_headers.hpp"

    # Exclude the umbrella header for now: the current parser does not yet merge
    # redeclarations from both the umbrella include and the concrete headers.
    header_files = _discover_parser_inventory(header_dir, root_header)
    update_result = update_activation_header(
        header_files,
        activation_header,
        with_sections=True,
        default_active=True,
    )
    print_update_report(update_result)

    active_count = sum(1 for header_file in update_result.header_files if header_file.active)
    total_count = len(update_result.header_files)
    print(f"Active headers: {active_count}/{total_count}")
    print("")

    active_headers = [
        header_file.full_path
        for header_file in update_result.header_files
        if header_file.active
    ]

    if not active_headers:
        print("No active concrete headers selected, so the parser was not run.")
        return 0

    sys.stdout.flush()

    # Get a parser config inferred from the compilation database (CMake + clang build).
    inference_result = infer_parser_config_from_compilation_database(
        build_dir,
        source_roots=[header_dir / "genesis"],
    )
    if inference_result.report.diagnostics:
        print_report(inference_result.report, color=None)
        print("")
    if inference_result.report.has_errors():
        print("Parser config inference failed.", file=sys.stderr)
        return 1
    parser_config = inference_result.config

    # Print the inferred config, if needed.
    # print_parser_config(parser_config, color=None)
    # print("")

    # Override some config settings for this example.
    parser_config.auto_detect_toolchain = True
    parser_config.suppress_diagnostics = ["parse.merge.preferred_comments"]
    print_parser_config(parser_config, color=None, include_clang_arguments=True)
    print("")

    # Run the parser on the active headers.
    parse_result = parse_header_selection(
        HeaderSelection(update_result.header_files),
        parser_config,
    )

    # Print the parse result with diagnostics, but without the semantic tree for brevity.
    print_parse_result(parse_result, include_headers=False, include_tree=False)
    return 1 if parse_result.report.has_errors() else 0


if __name__ == "__main__":
    raise SystemExit(main())
