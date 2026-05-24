from __future__ import annotations

from pathlib import Path
import tempfile
from textwrap import dedent

from oroboros.headers import HeaderFile, HeaderSelection
from oroboros.parse import ParserConfig, parse_header_selection


def parse_headers_from_sources(
    sources: dict[str, str],
    *,
    header_order: list[str] | None = None,
    parser_config: ParserConfig | None = None,
    known_project_header_names: list[str] | None = None,
):
    """Parse one small temporary header set with the real libclang pipeline."""

    ordered_names = header_order or list(sources)
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        headers: list[Path] = []
        for name in ordered_names:
            header = temp_path / name
            header.write_text(dedent(sources[name]))
            headers.append(header)

        known_project_headers = None
        if known_project_header_names is not None:
            known_project_headers = [temp_path / name for name in known_project_header_names]

        header_files = [
            HeaderFile(
                full_path=header,
                relative_path=header.relative_to(temp_path),
                active=True,
            )
            for header in headers
        ]
        if known_project_headers is not None:
            known_header_paths = {header.resolve() for header in known_project_headers}
            header_files.extend(
                HeaderFile(
                    full_path=header.resolve(),
                    relative_path=header.resolve().relative_to(temp_path),
                    active=False,
                )
                for header in known_project_headers
                if header.resolve() not in {active_header.full_path.resolve() for active_header in header_files}
            )

        return parse_header_selection(
            HeaderSelection(header_files=header_files),
            parser_config
            or ParserConfig(
                auto_detect_toolchain=False,
                cxx_standard="c++20",
            ),
        )
