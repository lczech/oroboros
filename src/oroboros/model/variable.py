from __future__ import annotations

"""Variable semantic model objects."""

from dataclasses import dataclass, field
from typing import Literal

from .availability import CppAvailability
from .comment import CppDoc, PyDoc
from .element import CppElement
from .location import CppLocationInfo
from .type import CppType
from .visibility import CppVisibility


@dataclass(slots=True)
class CppVariableCppFacet:
    """Store parsed C++ details for one variable declaration."""

    # Spelling written in the C++ source, before any Python-facing renaming.
    original_name: str | None = None
    # Structured parsed C++ variable type.
    type: CppType | None = None
    # Whether the variable type was declared const-qualified.
    is_const: bool = False
    # Source locations where this variable was declared or defined.
    location: CppLocationInfo = field(default_factory=CppLocationInfo)
    # Parser-selected comment text attached to this variable declaration.
    attached_comment: str | None = None
    # Raw comment text reported by clang for provenance and debugging.
    clang_raw_comment: str | None = None
    # Normalized structured documentation parsed from `attached_comment`.
    doc: CppDoc | None = None
    # Availability annotations such as deprecation attached to this variable.
    availability: CppAvailability | None = None
    # Declared member visibility when clang exposes it.
    visibility: CppVisibility | None = None
    # Variable role within the semantic model.
    kind: Literal["variable", "member_variable", "static_member_variable"] = "variable"
    # Storage-class spelling as exposed by clang.
    storage_class: str | None = None
    # Linkage kind as exposed by clang.
    linkage: str | None = None
    # Thread-local storage kind as exposed by clang.
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
