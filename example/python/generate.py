from __future__ import annotations

"""Example Oroboros driver for the bundled cosmos library."""

from pathlib import Path

from oroboros import (
    find_included_headers,
    print_update_report,
    update_activation_header,
)


def main() -> int:
    """Update the example activation header from the current example headers."""

    repo_root = Path(__file__).resolve().parents[2]
    header_dir = repo_root / "example" / "inc"
    root_header = header_dir / "cosmos" / "cosmos.hpp"
    activation_header = repo_root / "example" / "python" / "active_headers.hpp"

    header_files = find_included_headers(header_dir, root_header)
    update_result = update_activation_header(
        header_files,
        activation_header,
        with_sections=True,
        default_active=False,
    )
    print_update_report(update_result)

    active_count = sum(1 for header_file in update_result.header_files if header_file.active)
    total_count = len(update_result.header_files)
    print(f"Active headers: {active_count}/{total_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
