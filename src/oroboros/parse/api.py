from __future__ import annotations

"""Public parse-stage entrypoints."""

from pathlib import Path
from typing import Sequence

from .config import ParserConfig
from .build_model import build_module_from_clang
from .clang_driver import parse_with_clang
from .result import ParseResult


def parse_headers(
    headers: Sequence[Path],
    config: ParserConfig,
) -> ParseResult:
    """Parse one ordered active-header list into the semantic model."""

    normalized_headers = [Path(header).resolve() for header in headers]

    if not normalized_headers:
        return ParseResult()

    driver_result = parse_with_clang(normalized_headers, config)
    build_result = build_module_from_clang(
        driver_result.translation_unit,
        normalized_headers,
    )

    if config.validate_model:
        build_result.module.validate_tree()
        build_result.module.validate_semantics()

    return ParseResult(
        module=build_result.module,
        diagnostics=driver_result.diagnostics,
        warnings=build_result.warnings,
        skipped_kind_counts=build_result.skipped_kind_counts,
        headers=normalized_headers,
    )
