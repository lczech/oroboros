from __future__ import annotations

"""Documentation objects shared by parsed and Python-facing facets.

For parsed `.cpp` facets, `CppDocumentation` groups three related views:
- `attached_comment`: Oroboros' selected local attached comment text
- `clang_raw_comment`: clang's raw comment text preserved as provenance
- `parsed`: normalized structured documentation parsed from `attached_comment`
"""

from dataclasses import dataclass, field


# ==================================================================================================
#     Documentation
# ==================================================================================================


@dataclass(slots=True)
class CppParsedDoc:
    """Store normalized documentation parsed from one C++ comment block."""

    brief: str | None = None
    description: str | None = None
    parameters: dict[str, str] = field(default_factory=dict)
    template_parameters: dict[str, str] = field(default_factory=dict)
    returns: str | None = None
    return_values: dict[str, str] = field(default_factory=dict)
    deprecated: str | None = None
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    see_also: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CppDocumentation:
    """Store raw comment provenance plus the parsed documentation derived from it."""

    attached_comment: str | None = None
    clang_raw_comment: str | None = None
    parsed: CppParsedDoc | None = None


@dataclass(slots=True)
class PyDoc:
    """Store Python-facing documentation for one exposed element."""

    summary: str | None = None
    description: str | None = None
    parameters: dict[str, str] = field(default_factory=dict)
    template_parameters: dict[str, str] = field(default_factory=dict)
    returns: str | None = None
    return_values: dict[str, str] = field(default_factory=dict)
    deprecated: str | None = None
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    see_also: list[str] = field(default_factory=list)


def build_py_doc_from_parsed_doc(parsed_doc: CppParsedDoc | None) -> PyDoc | None:
    """Translate normalized parsed C++ documentation into the default Python form."""

    if parsed_doc is None:
        return None

    return PyDoc(
        summary=parsed_doc.brief,
        description=parsed_doc.description,
        parameters=dict(parsed_doc.parameters),
        template_parameters=dict(parsed_doc.template_parameters),
        returns=parsed_doc.returns,
        return_values=dict(parsed_doc.return_values),
        deprecated=parsed_doc.deprecated,
        notes=list(parsed_doc.notes),
        warnings=list(parsed_doc.warnings),
        see_also=list(parsed_doc.see_also),
    )
