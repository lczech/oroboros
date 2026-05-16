from __future__ import annotations

"""Class and field semantic model objects."""

from dataclasses import dataclass, field as dataclass_field
from typing import TYPE_CHECKING, Literal

from .comment import CppDoc, PyDoc
from .element import CppElement
from .location import SourceLocation
from .type import CppType

if TYPE_CHECKING:
    from .enum import CppEnum, CppEnumBindFacet
    from .function import CppFunctionBindFacet
    from .member import CppConstructor, CppMethod
    from .template_ import CppClassTemplate, CppFunctionTemplate


# ==================================================================================================
#     Facets
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Class Facets
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppClassBase:
    """Store one base-class relationship of a class or struct."""

    type: CppType
    access: Literal["public", "protected", "private"] | None = None
    is_virtual: bool = False


@dataclass(slots=True)
class CppClassCppFacet:
    """Store parsed C++ details for one class or struct."""

    original_name: str | None = None
    qualified_name: str | None = None
    location: SourceLocation | None = None
    comment: str | None = None
    doc: CppDoc | None = None
    kind: Literal["class", "struct"] = "class"
    bases: list[CppClassBase] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class CppClassBindFacet:
    """Store binding settings for one class or struct."""

    active: bool | None = None
    holder_type: str | None = None
    trampoline_type: str | None = None
    expose_copy: bool | None = None
    expose_move: bool | None = None
    hooks: list[str] = dataclass_field(default_factory=list)


@dataclass(slots=True)
class CppClassPyFacet:
    """Store Python-facing choices for one class or struct."""

    name: str | None = None
    doc: PyDoc | None = None


# ------------------------------------------------------------------------------
#     Field Facets
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppFieldCppFacet:
    """Store parsed C++ details for one field."""

    original_name: str | None = None
    type: CppType | None = None
    location: SourceLocation | None = None
    comment: str | None = None
    doc: CppDoc | None = None
    is_static: bool = False


@dataclass(slots=True)
class CppFieldBindFacet:
    """Store binding settings for one field or property."""

    active: bool | None = None
    read_only: bool | None = None
    getter: str | None = None
    setter: str | None = None


@dataclass(slots=True)
class CppFieldPyFacet:
    """Store Python-facing choices for one field."""

    name: str | None = None
    doc: PyDoc | None = None


# ------------------------------------------------------------------------------
#     Defaults
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppClassDefaults:
    """Store descendant defaults for one class scope."""

    class_: CppClassBindFacet = dataclass_field(default_factory=CppClassBindFacet)
    method: "CppFunctionBindFacet" = dataclass_field(default_factory=lambda: _make_function_bind_facet())
    constructor: "CppFunctionBindFacet" = dataclass_field(default_factory=lambda: _make_function_bind_facet())
    field: CppFieldBindFacet = dataclass_field(default_factory=CppFieldBindFacet)
    enum: "CppEnumBindFacet" = dataclass_field(default_factory=lambda: _make_enum_bind_facet())


def _make_function_bind_facet() -> "CppFunctionBindFacet":
    """Create one function-bind facet without import cycles at module import time."""

    from .function import CppFunctionBindFacet

    return CppFunctionBindFacet()


def _make_enum_bind_facet() -> "CppEnumBindFacet":
    """Create one enum-bind facet without import cycles at module import time."""

    from .enum import CppEnumBindFacet

    return CppEnumBindFacet()


# ==================================================================================================
#     Elements
# ==================================================================================================


@dataclass(slots=True)
class CppClassMembers(CppElement):
    """Share class member collections between concrete and template declarations."""

    # Nested non-template classes declared inside this class scope.
    classes: list["CppClass"] = dataclass_field(default_factory=list)
    # Constructors declared directly inside this class scope.
    constructors: list["CppConstructor"] = dataclass_field(default_factory=list)
    # Methods declared directly inside this class scope.
    methods: list["CppMethod"] = dataclass_field(default_factory=list)
    # Fields declared directly inside this class scope.
    fields: list["CppField"] = dataclass_field(default_factory=list)
    # Enums declared directly inside this class scope.
    enums: list["CppEnum"] = dataclass_field(default_factory=list)
    # Nested class template families declared inside this class scope.
    class_templates: list["CppClassTemplate"] = dataclass_field(default_factory=list)
    # Nested function template families declared inside this class scope.
    function_templates: list["CppFunctionTemplate"] = dataclass_field(default_factory=list)

    def __post_init__(self) -> None:
        """Adopt all typed child declaration collections."""

        self.adopt_children(self.classes)
        self.adopt_children(self.constructors)
        self.adopt_children(self.methods)
        self.adopt_children(self.fields)
        self.adopt_children(self.enums)
        self.adopt_children(self.class_templates)
        self.adopt_children(self.function_templates)


@dataclass(slots=True)
class CppField(CppElement):
    """Represent one field owned by a class."""

    cpp: CppFieldCppFacet = dataclass_field(default_factory=CppFieldCppFacet)
    bind: CppFieldBindFacet = dataclass_field(default_factory=CppFieldBindFacet)
    py: CppFieldPyFacet = dataclass_field(default_factory=CppFieldPyFacet)


@dataclass(slots=True)
class CppClass(CppClassMembers):
    """Represent one concrete class or struct scope in the semantic model."""

    # Parsed C++ details for this concrete class or struct.
    cpp: CppClassCppFacet = dataclass_field(default_factory=CppClassCppFacet)
    # Binding settings for this class or struct itself.
    bind: CppClassBindFacet = dataclass_field(default_factory=CppClassBindFacet)
    # Python-facing choices for this class or struct.
    py: CppClassPyFacet = dataclass_field(default_factory=CppClassPyFacet)
    # Inherited defaults applied to descendants of this class scope.
    defaults: CppClassDefaults = dataclass_field(default_factory=CppClassDefaults)
