from __future__ import annotations

"""Public parse-stage entrypoints."""

from pathlib import Path
from typing import Sequence

from .config import ParserConfig
from .decls import build_module_from_translation_unit
from .driver import parse_translation_unit
from .result import ParseResult


def parse_headers(
    headers: Sequence[Path],
    config: ParserConfig,
) -> ParseResult:
    """Parse one ordered active-header list into the semantic model."""

    normalized_headers = [Path(header).resolve() for header in headers]

    if not normalized_headers:
        return ParseResult()

    driver_result = parse_translation_unit(normalized_headers, config)
    module = build_module_from_translation_unit(
        driver_result.translation_unit,
        normalized_headers,
    )

    if config.validate_model:
        module.validate_tree()
        module.validate_semantics()

    return ParseResult(
        module=module,
        diagnostics=driver_result.diagnostics,
        headers=normalized_headers,
    )
