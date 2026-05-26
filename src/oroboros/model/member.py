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

    special_member_kind: Literal["copy_assignment", "move_assignment"] | None = None
    ref_qualifier: str | None = None
    is_const: bool = False
    is_static: bool = False
    is_virtual: bool = False
    is_pure_virtual: bool = False
    is_defaulted: bool = False
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
    location: CppLocationInfo = field(default_factory=CppLocationInfo)
    comment: str | None = None
    doc: CppDoc | None = None
    availability: CppAvailability | None = None
    overload_index: int | None = None
    template_parameters: list["CppTemplateParameter"] = field(default_factory=list)
    is_explicit: bool = False
    is_noexcept: bool = False
    is_deleted: bool = False
    is_defaulted: bool = False
    special_member_kind: Literal["default_constructor", "copy_constructor", "move_constructor"] | None = None
    is_converting_constructor: bool = False
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

    original_name: str | None = None
    location: CppLocationInfo = field(default_factory=CppLocationInfo)
    comment: str | None = None
    doc: CppDoc | None = None
    availability: CppAvailability | None = None
    is_virtual: bool = False
    is_pure_virtual: bool = False
    is_deleted: bool = False
    is_defaulted: bool = False
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
