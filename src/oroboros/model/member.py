from __future__ import annotations

"""Class-member callable semantic model objects."""

from dataclasses import dataclass, field
from typing import Literal

from .availability import CppAvailability
from .comment import CppDoc, PyDoc
from .element import CppElement
from .function import CppFunctionBindFacet, CppFunctionCppFacet, CppFunctionPyFacet, CppParameter
from .lookup import make_named_child_view
from .location import CppLocationInfo
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

    # Special-member classification for assignment operators, when applicable.
    special_member_kind: Literal["copy_assignment", "move_assignment"] | None = None
    # Ref-qualifier spelling such as `&` or `&&`.
    ref_qualifier: str | None = None
    # Whether this method was declared `const`.
    is_const: bool = False
    # Whether this method was declared `static`.
    is_static: bool = False
    # Whether this method was declared `virtual`.
    is_virtual: bool = False
    # Whether this method is pure virtual.
    is_pure_virtual: bool = False
    # Whether this method was explicitly declared `= default`.
    is_defaulted: bool = False
    # Declared member visibility when clang exposes it.
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

    # Spelling written in the C++ source, before any Python-facing renaming.
    original_name: str | None = None
    # Source locations where this constructor was declared or defined.
    location: CppLocationInfo = field(default_factory=CppLocationInfo)
    # Parser-selected comment text attached to this constructor declaration.
    attached_comment: str | None = None
    # Raw comment text reported by clang for provenance and debugging.
    clang_raw_comment: str | None = None
    # Normalized structured documentation parsed from `attached_comment`.
    doc: CppDoc | None = None
    # Availability annotations such as deprecation attached to this constructor.
    availability: CppAvailability | None = None
    # Parser-assigned index among constructor overloads.
    overload_index: int | None = None
    # Parsed template parameters for constructor templates.
    template_parameters: list["CppTemplateParameter"] = field(default_factory=list)
    # Whether this constructor was declared `explicit`.
    is_explicit: bool = False
    # Whether this constructor was declared `noexcept`.
    is_noexcept: bool = False
    # Whether this constructor was explicitly declared deleted.
    is_deleted: bool = False
    # Whether this constructor was explicitly declared `= default`.
    is_defaulted: bool = False
    # Special-member classification, when this constructor is one.
    special_member_kind: Literal["default_constructor", "copy_constructor", "move_constructor"] | None = None
    # Whether this constructor can act as an implicit conversion constructor.
    is_converting_constructor: bool = False
    # Declared member visibility when clang exposes it.
    visibility: CppVisibility | None = None


@dataclass(slots=True)
class CppConstructorBindFacet(CppFunctionBindFacet):
    """Store binding settings for one constructor."""


@dataclass(slots=True)
class CppConstructorPyFacet:
    """Store Python-facing choices for one constructor."""

    doc: PyDoc | None = None
    sig: str | None = None


# ------------------------------------------------------------------------------
#     Destructor Facets
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppDestructorCppFacet:
    """Store parsed C++ details for one destructor."""

    # Spelling written in the C++ source, before any Python-facing renaming.
    original_name: str | None = None
    # Source locations where this destructor was declared or defined.
    location: CppLocationInfo = field(default_factory=CppLocationInfo)
    # Parser-selected comment text attached to this destructor declaration.
    attached_comment: str | None = None
    # Raw comment text reported by clang for provenance and debugging.
    clang_raw_comment: str | None = None
    # Normalized structured documentation parsed from `attached_comment`.
    doc: CppDoc | None = None
    # Availability annotations such as deprecation attached to this destructor.
    availability: CppAvailability | None = None
    # Whether this destructor was declared `virtual`.
    is_virtual: bool = False
    # Whether this destructor is pure virtual.
    is_pure_virtual: bool = False
    # Whether this destructor was explicitly declared deleted.
    is_deleted: bool = False
    # Whether this destructor was explicitly declared `= default`.
    is_defaulted: bool = False
    # Declared member visibility when clang exposes it.
    visibility: CppVisibility | None = None


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

        self._adopt_children(self.parameters)

    def add_parameter(self, parameter: CppParameter) -> CppParameter:
        """Attach one parameter to this method."""

        return self._append_child(self.parameters, parameter)

    @property
    def parameter(self):
        """Return a name-indexed view over this method's parameters."""

        return make_named_child_view(self, self, "parameters")


@dataclass(slots=True)
class CppConstructor(CppElement):
    """Represent one constructor owned by a class."""

    cpp: CppConstructorCppFacet = field(default_factory=CppConstructorCppFacet)
    bind: CppConstructorBindFacet = field(default_factory=CppConstructorBindFacet)
    py: CppConstructorPyFacet = field(default_factory=CppConstructorPyFacet)
    parameters: list[CppParameter] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Adopt the owned parameter nodes."""

        self._adopt_children(self.parameters)

    def add_parameter(self, parameter: CppParameter) -> CppParameter:
        """Attach one parameter to this constructor."""

        return self._append_child(self.parameters, parameter)

    @property
    def parameter(self):
        """Return a name-indexed view over this constructor's parameters."""

        return make_named_child_view(self, self, "parameters")


@dataclass(slots=True)
class CppDestructor(CppElement):
    """Represent one destructor owned by a class."""

    cpp: CppDestructorCppFacet = field(default_factory=CppDestructorCppFacet)
