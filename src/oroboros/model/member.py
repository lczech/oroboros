from __future__ import annotations

"""Class-member callable semantic model objects."""

from dataclasses import dataclass, field

from .comment import CppDoc, PyDoc
from .element import CppElement
from .function import CppFunctionBindFacet, CppParameter
from .location import SourceLocation
from .operator_ import CppOperator
from .type import CppType
from .visibility import CppVisibility


# ==================================================================================================
#     Facets
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Method Facets
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppMethodCppFacet:
    """Store parsed C++ details for one class method."""

    original_name: str | None = None
    qualified_name: str | None = None
    operator: CppOperator | None = None
    return_type: CppType | None = None
    location: SourceLocation | None = None
    comment: str | None = None
    doc: CppDoc | None = None
    overload_index: int | None = None
    is_const: bool = False
    is_static: bool = False
    is_virtual: bool = False
    is_pure_virtual: bool = False
    is_noexcept: bool = False
    visibility: CppVisibility | None = None


@dataclass(slots=True)
class CppMethodPyFacet:
    """Store Python-facing choices for one class method."""

    name: str | None = None
    doc: PyDoc | None = None


# ------------------------------------------------------------------------------
#     Constructor Facets
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppConstructorCppFacet:
    """Store parsed C++ details for one constructor."""

    original_name: str | None = None
    qualified_name: str | None = None
    location: SourceLocation | None = None
    comment: str | None = None
    doc: CppDoc | None = None
    overload_index: int | None = None
    is_explicit: bool = False
    is_noexcept: bool = False
    visibility: CppVisibility | None = None


@dataclass(slots=True)
class CppConstructorPyFacet:
    """Store Python-facing choices for one constructor."""

    doc: PyDoc | None = None


# ==================================================================================================
#     Elements
# ==================================================================================================


@dataclass(slots=True)
class CppMethod(CppElement):
    """Represent one method owned by a class."""

    cpp: CppMethodCppFacet = field(default_factory=CppMethodCppFacet)
    bind: CppFunctionBindFacet = field(default_factory=CppFunctionBindFacet)
    py: CppMethodPyFacet = field(default_factory=CppMethodPyFacet)
    parameters: list[CppParameter] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Adopt the owned parameter nodes."""

        self.adopt_children(self.parameters)


@dataclass(slots=True)
class CppConstructor(CppElement):
    """Represent one constructor owned by a class."""

    cpp: CppConstructorCppFacet = field(default_factory=CppConstructorCppFacet)
    bind: CppFunctionBindFacet = field(default_factory=CppFunctionBindFacet)
    py: CppConstructorPyFacet = field(default_factory=CppConstructorPyFacet)
    parameters: list[CppParameter] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Adopt the owned parameter nodes."""

        self.adopt_children(self.parameters)
