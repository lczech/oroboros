from __future__ import annotations

"""Class and field semantic model objects."""

from dataclasses import dataclass, field as dataclass_field
from typing import TYPE_CHECKING, Literal

from .comment import CppDoc, PyDoc
from .element import CppElement
from .lookup import make_named_child_view
from .location import CppLocationInfo
from .type import CppType
from .visibility import CppVisibility

if TYPE_CHECKING:
    from .alias import CppAliasInfo
    from .enum import CppEnum, CppEnumBindFacet
    from .member import CppConstructor, CppConstructorBindFacet, CppMethod, CppMethodBindFacet
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
    visibility: CppVisibility | None = None
    is_virtual: bool = False


@dataclass(slots=True)
class CppClassCppFacet:
    """Store parsed C++ details for one class or struct."""

    original_name: str | None = None
    location: CppLocationInfo = dataclass_field(default_factory=CppLocationInfo)
    comment: str | None = None
    doc: CppDoc | None = None
    kind: Literal["class", "struct"] = "class"
    visibility: CppVisibility | None = None
    aliases: list["CppAliasInfo"] = dataclass_field(default_factory=list)
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
    location: CppLocationInfo = dataclass_field(default_factory=CppLocationInfo)
    comment: str | None = None
    doc: CppDoc | None = None
    is_static: bool = False
    visibility: CppVisibility | None = None


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
    method: "CppMethodBindFacet" = dataclass_field(default_factory=lambda: _make_method_bind_facet())
    constructor: "CppConstructorBindFacet" = dataclass_field(default_factory=lambda: _make_constructor_bind_facet())
    field: CppFieldBindFacet = dataclass_field(default_factory=CppFieldBindFacet)
    enum: "CppEnumBindFacet" = dataclass_field(default_factory=lambda: _make_enum_bind_facet())


def _make_method_bind_facet() -> "CppMethodBindFacet":
    """Create one method-bind facet without import cycles at module import time."""

    from .member import CppMethodBindFacet

    return CppMethodBindFacet()


def _make_constructor_bind_facet() -> "CppConstructorBindFacet":
    """Create one constructor-bind facet without import cycles at module import time."""

    from .member import CppConstructorBindFacet

    return CppConstructorBindFacet()


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

        self._adopt_children(self.classes)
        self._adopt_children(self.constructors)
        self._adopt_children(self.methods)
        self._adopt_children(self.fields)
        self._adopt_children(self.enums)
        self._adopt_children(self.class_templates)
        self._adopt_children(self.function_templates)

    def add_class(self, class_: "CppClass") -> "CppClass":
        """Attach one nested class to this class scope."""

        return self._append_child(self.classes, class_)

    def add_constructor(self, constructor: "CppConstructor") -> "CppConstructor":
        """Attach one constructor to this class scope."""

        return self._append_child(self.constructors, constructor)

    def add_method(self, method: "CppMethod") -> "CppMethod":
        """Attach one method to this class scope."""

        return self._append_child(self.methods, method)

    def add_field(self, field: "CppField") -> "CppField":
        """Attach one field to this class scope."""

        return self._append_child(self.fields, field)

    def add_enum(self, enum: "CppEnum") -> "CppEnum":
        """Attach one nested enum to this class scope."""

        return self._append_child(self.enums, enum)

    def add_class_template(self, template: "CppClassTemplate") -> "CppClassTemplate":
        """Attach one nested class template family to this class scope."""

        return self._append_child(self.class_templates, template)

    def add_function_template(self, template: "CppFunctionTemplate") -> "CppFunctionTemplate":
        """Attach one nested function template family to this class scope."""

        return self._append_child(self.function_templates, template)

    @property
    def class_(self):
        """Return a name-indexed view over nested classes."""

        return make_named_child_view(self, "classes")

    @property
    def constructor(self):
        """Return a name-indexed view over constructors declared in this class."""

        return make_named_child_view(self, "constructors", return_many=True)

    @property
    def method(self):
        """Return a name-indexed view over methods declared in this class."""

        return make_named_child_view(self, "methods", return_many=True)

    @property
    def field(self):
        """Return a name-indexed view over fields declared in this class."""

        return make_named_child_view(self, "fields")

    @property
    def enum(self):
        """Return a name-indexed view over nested enums declared in this class."""

        return make_named_child_view(self, "enums")

    @property
    def class_template(self):
        """Return a name-indexed view over nested class templates."""

        return make_named_child_view(self, "class_templates")

    @property
    def function_template(self):
        """Return a name-indexed view over nested function templates."""

        return make_named_child_view(self, "function_templates", return_many=True)


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
