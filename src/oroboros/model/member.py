from __future__ import annotations

"""Class-member callable semantic model objects."""

from dataclasses import dataclass, field

from .comment import CppDoc, PyDoc
from .element import CppElement
from .function import CppFunctionBindFacet, CppFunctionCppFacet, CppFunctionPyFacet, CppParameter
from .location import SourceLocation
from .visibility import CppVisibility


# ==================================================================================================
#     Facets
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Method Facets
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppMethodCppFacet(CppFunctionCppFacet):
    """Store parsed C++ details for one class method."""

    is_const: bool = False
    is_static: bool = False
    is_virtual: bool = False
    is_pure_virtual: bool = False
    visibility: CppVisibility | None = None


@dataclass(slots=True)
class CppMethodBindFacet(CppFunctionBindFacet):
    """Store binding settings for one class method."""


@dataclass(slots=True)
class CppMethodPyFacet(CppFunctionPyFacet):
    """Store Python-facing choices for one class method."""


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
class CppConstructorBindFacet(CppFunctionBindFacet):
    """Store binding settings for one constructor."""


@dataclass(slots=True)
class CppConstructorPyFacet:
    """Store Python-facing choices for one constructor."""

    doc: PyDoc | None = None
    sig: str | None = None


# ==================================================================================================
#     Elements
# ==================================================================================================


@dataclass(slots=True)
class CppMethod(CppElement):
    """Represent one method owned by a class."""

    cpp: CppMethodCppFacet = field(default_factory=CppMethodCppFacet)
    bind: CppMethodBindFacet = field(default_factory=CppMethodBindFacet)
    py: CppMethodPyFacet = field(default_factory=CppMethodPyFacet)
    parameters: list[CppParameter] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Adopt the owned parameter nodes."""

        self.adopt_children(self.parameters)


@dataclass(slots=True)
class CppConstructor(CppElement):
    """Represent one constructor owned by a class."""

    cpp: CppConstructorCppFacet = field(default_factory=CppConstructorCppFacet)
    bind: CppConstructorBindFacet = field(default_factory=CppConstructorBindFacet)
    py: CppConstructorPyFacet = field(default_factory=CppConstructorPyFacet)
    parameters: list[CppParameter] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Adopt the owned parameter nodes."""

        self.adopt_children(self.parameters)
