from __future__ import annotations

"""Example Oroboros driver for the bundled cosmos library."""

from pathlib import Path
import sys

from oroboros import (
    HeaderFile,
    ParserConfig,
    find_included_headers,
    parse_headers,
    print_update_report,
    update_activation_header,
)
from oroboros.parse.inspect import format_parse_result


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

    repo_root = Path(__file__).resolve().parents[2]
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

    try:
        parser_config = ParserConfig(
            include_dirs=[header_dir],
            cxx_standard="c++20",
            auto_detect_toolchain=True,
        )
        parse_result = parse_headers(
            active_headers,
            parser_config,
        )
    except RuntimeError as error:
        print(f"Parser setup error: {error}", file=sys.stderr)
        return 1

    print(format_parse_result(parse_result))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
