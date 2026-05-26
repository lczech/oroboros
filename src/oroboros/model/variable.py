from __future__ import annotations

"""Variable semantic model objects."""

from dataclasses import dataclass, field
from typing import Literal

from .comment import CppDoc, PyDoc
from .element import CppElement
from .location import CppLocationInfo
from .type import CppType
from .visibility import CppVisibility


@dataclass(slots=True)
class CppVariableCppFacet:
    """Store parsed C++ details for one variable declaration."""

    original_name: str | None = None
    type: CppType | None = None
    is_const: bool = False
    location: CppLocationInfo = field(default_factory=CppLocationInfo)
    comment: str | None = None
    doc: CppDoc | None = None
    visibility: CppVisibility | None = None
    kind: Literal["variable", "member_variable", "static_member_variable"] = "variable"
    storage_class: str | None = None
    linkage: str | None = None
    tls_kind: str | None = None
    # Whether this field declaration uses bitfield syntax such as `unsigned mode : 3`.
    is_bitfield: bool = False
    # Declared bitfield width when clang exposes one.
    bitfield_width: int | None = None
    # Whether this field declaration uses the `mutable` specifier.
    is_mutable: bool = False


@dataclass(slots=True)
class CppVariableBindFacet:
    """Store binding settings for one variable or property."""

    active: bool | None = None
    read_only: bool | None = None
    getter: str | None = None
    setter: str | None = None


@dataclass(slots=True)
class CppVariablePyFacet:
    """Store Python-facing choices for one variable."""

    name: str | None = None
    doc: PyDoc | None = None


@dataclass(slots=True)
class CppVariable(CppElement):
    """Represent one variable declaration in the semantic model."""

    cpp: CppVariableCppFacet = field(default_factory=CppVariableCppFacet)
    bind: CppVariableBindFacet = field(default_factory=CppVariableBindFacet)
    py: CppVariablePyFacet = field(default_factory=CppVariablePyFacet)
