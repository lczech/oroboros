from __future__ import annotations

"""Documentation objects shared by parsed and Python-facing facets."""

from dataclasses import dataclass, field


# ==================================================================================================
#     Documentation
# ==================================================================================================


@dataclass(slots=True)
class CppDoc:
    """Store normalized documentation parsed from a C++ comment."""

    brief: str | None = None
    description: str | None = None
    parameters: dict[str, str] = field(default_factory=dict)
    returns: str | None = None
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    see_also: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PyDoc:
    """Store Python-facing documentation for one exposed element."""

    summary: str | None = None
    description: str | None = None
    parameters: dict[str, str] = field(default_factory=dict)
    returns: str | None = None
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    see_also: list[str] = field(default_factory=list)


def build_py_doc_from_cpp_doc(cpp_doc: CppDoc | None) -> PyDoc | None:
    """Translate normalized C++ documentation into the default Python form."""

    if cpp_doc is None:
        return None

    return PyDoc(
        summary=cpp_doc.brief,
        description=cpp_doc.description,
        parameters=dict(cpp_doc.parameters),
        returns=cpp_doc.returns,
        notes=list(cpp_doc.notes),
        warnings=list(cpp_doc.warnings),
        see_also=list(cpp_doc.see_also),
    )
