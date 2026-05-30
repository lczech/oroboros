from __future__ import annotations

"""Class semantic model objects."""

from dataclasses import dataclass, field as dataclass_field
from typing import TYPE_CHECKING, Literal

from .availability import CppAvailability
from .documentation import CppDocumentation, PyDoc
from .element import CppElement
from .lookup import make_named_child_view
from .location import CppLocationInfo
from .type import CppType
from .variable import CppVariable, CppVariableBindFacet
from .visibility import CppVisibility

if TYPE_CHECKING:
    from .alias import CppAlias
    from .alias_template import CppAliasTemplate
    from .enum import CppEnum, CppEnumBindFacet
    from .method_template import CppMethodTemplate
    from .member import (
        CppConstructor,
        CppConstructorBindFacet,
        CppDestructor,
        CppMethod,
        CppMethodBindFacet,
    )
    from .template_ import CppClassTemplate, CppTemplateBindFacet


# ==================================================================================================
#     Facets
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Class Facets
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppClassBase:
    """Store one base-class relationship of a class or struct."""

    # Structured parsed type of the base class as written at the use site.
    type: CppType
    # Access level of the inheritance declaration, when clang exposes it.
    visibility: CppVisibility | None = None
    # Whether this base is inherited virtually.
    is_virtual: bool = False


@dataclass(slots=True)
class CppClassCppFacet:
    """Store parsed C++ details for one class or struct."""

    # Spelling written in the C++ source, before any Python-facing renaming.
    original_name: str | None = None
    # Source locations where this class was declared or defined.
    location: CppLocationInfo = dataclass_field(default_factory=CppLocationInfo)
    # Attached-comment provenance plus normalized parsed documentation for this class.
    doc: CppDocumentation | None = None
    # Availability annotations such as deprecation attached to this class.
    availability: CppAvailability | None = None
    # Whether the class is abstract according to clang.
    is_abstract: bool = False
    # Record kind as spelled in C++: class, struct, or union.
    kind: Literal["class", "struct", "union"] = "class"
    # Declared class visibility when nested in another class.
    visibility: CppVisibility | None = None
    # Direct base-class relationships declared on this class.
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
#     Defaults
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppClassDefaults:
    """Store descendant defaults for one class scope."""

    class_: CppClassBindFacet = dataclass_field(
        default_factory=CppClassBindFacet
    )
    class_template: "CppTemplateBindFacet" = dataclass_field(
        default_factory=lambda: _make_template_bind_facet()
    )
    constructor: "CppConstructorBindFacet" = dataclass_field(
        default_factory=lambda: _make_constructor_bind_facet()
    )
    method: "CppMethodBindFacet" = dataclass_field(
        default_factory=lambda: _make_method_bind_facet()
    )
    method_template: "CppTemplateBindFacet" = dataclass_field(
        default_factory=lambda: _make_template_bind_facet()
    )
    variable: CppVariableBindFacet = dataclass_field(
        default_factory=CppVariableBindFacet
    )
    static_variable: CppVariableBindFacet = dataclass_field(
        default_factory=CppVariableBindFacet
    )
    enum: "CppEnumBindFacet" = dataclass_field(
        default_factory=lambda: _make_enum_bind_facet()
    )
    alias_template: "CppTemplateBindFacet" = dataclass_field(
        default_factory=lambda: _make_template_bind_facet()
    )


def _make_method_bind_facet() -> "CppMethodBindFacet":
    """Create one method-bind facet without import cycles at module import time."""

    from .member import CppMethodBindFacet

    return CppMethodBindFacet()


def _make_constructor_bind_facet() -> "CppConstructorBindFacet":
    """Create one constructor-bind facet without import cycles at module import time."""

    from .member import CppConstructorBindFacet

    return CppConstructorBindFacet()


def _make_template_bind_facet() -> "CppTemplateBindFacet":
    """Create one template-bind facet without import cycles at module import time."""

    from .template_ import CppTemplateBindFacet

    return CppTemplateBindFacet()


def _make_enum_bind_facet() -> "CppEnumBindFacet":
    """Create one enum-bind facet without import cycles at module import time."""

    from .enum import CppEnumBindFacet

    return CppEnumBindFacet()


# ==================================================================================================
#     Declarations
# ==================================================================================================


@dataclass(slots=True)
class CppClassDeclarations:
    """Store direct declarations owned by one class-like scope."""

    _is_child_container = True

    # Nested non-template classes declared inside this class scope.
    classes: list["CppClass"] = dataclass_field(default_factory=list)
    # Constructors declared directly inside this class scope.
    constructors: list["CppConstructor"] = dataclass_field(default_factory=list)
    # Destructor declared directly inside this class scope, when present.
    destructor: "CppDestructor | None" = None
    # Methods declared directly inside this class scope.
    methods: list["CppMethod"] = dataclass_field(default_factory=list)
    # Non-static instance variables declared directly inside this class scope.
    variables: list["CppVariable"] = dataclass_field(default_factory=list)
    # Static variables declared directly inside this class scope.
    static_variables: list["CppVariable"] = dataclass_field(default_factory=list)
    # Enums declared directly inside this class scope.
    enums: list["CppEnum"] = dataclass_field(default_factory=list)
    # Aliases declared directly inside this class scope.
    aliases: list["CppAlias"] = dataclass_field(default_factory=list)
    # Alias template families declared directly inside this class scope.
    alias_templates: list["CppAliasTemplate"] = dataclass_field(default_factory=list)
    # Nested class template families declared inside this class scope.
    class_templates: list["CppClassTemplate"] = dataclass_field(default_factory=list)
    # Method template families declared directly inside this class scope.
    method_templates: list["CppMethodTemplate"] = dataclass_field(default_factory=list)


# ==================================================================================================
#     Elements
# ==================================================================================================


@dataclass(slots=True)
class CppClassMembers(CppElement):
    """Share class-like declaration storage and helpers between class scopes."""

    # Direct declarations owned by this class-like scope.
    declarations: CppClassDeclarations = dataclass_field(default_factory=CppClassDeclarations)

    def __post_init__(self) -> None:
        """Adopt all typed child declaration collections."""

        for declaration_list in (
            self.declarations.classes,
            self.declarations.constructors,
            self.declarations.methods,
            self.declarations.variables,
            self.declarations.static_variables,
            self.declarations.aliases,
            self.declarations.alias_templates,
            self.declarations.enums,
            self.declarations.class_templates,
            self.declarations.method_templates,
        ):
            self._adopt_children(declaration_list)
        if self.declarations.destructor is not None:
            self._adopt_child(self.declarations.destructor)

    def add_class(self, class_: "CppClass") -> "CppClass":
        """Attach one nested class to this class scope."""

        return self._append_child(self.declarations.classes, class_)

    def add_constructor(self, constructor: "CppConstructor") -> "CppConstructor":
        """Attach one constructor to this class scope."""

        return self._append_child(self.declarations.constructors, constructor)

    def add_destructor(self, destructor: "CppDestructor") -> "CppDestructor":
        """Attach one destructor to this class scope."""

        existing = self.declarations.destructor
        if existing is not None and existing is not destructor:
            raise ValueError(
                f"{self._describe_element()} already has a destructor named {existing.name!r}."
            )
        self._adopt_child(destructor)
        self.declarations.destructor = destructor
        return destructor

    def add_method(self, method: "CppMethod") -> "CppMethod":
        """Attach one method to this class scope."""

        return self._append_child(self.declarations.methods, method)

    def add_variable(self, variable: "CppVariable") -> "CppVariable":
        """Attach one instance variable to this class scope."""

        return self._append_child(self.declarations.variables, variable)

    def add_static_variable(self, variable: "CppVariable") -> "CppVariable":
        """Attach one static variable to this class scope."""

        return self._append_child(self.declarations.static_variables, variable)

    def add_alias(self, alias: "CppAlias") -> "CppAlias":
        """Attach one alias to this class scope."""

        return self._append_child(self.declarations.aliases, alias)

    def add_alias_template(self, template: "CppAliasTemplate") -> "CppAliasTemplate":
        """Attach one alias template family to this class scope."""

        return self._append_child(self.declarations.alias_templates, template)

    def add_enum(self, enum: "CppEnum") -> "CppEnum":
        """Attach one nested enum to this class scope."""

        return self._append_child(self.declarations.enums, enum)

    def add_class_template(self, template: "CppClassTemplate") -> "CppClassTemplate":
        """Attach one nested class template family to this class scope."""

        return self._append_child(self.declarations.class_templates, template)

    def add_method_template(self, template: "CppMethodTemplate") -> "CppMethodTemplate":
        """Attach one method template family to this class scope."""

        return self._append_child(self.declarations.method_templates, template)

    @property
    def class_(self):
        """Return a name-indexed view over nested classes."""

        return make_named_child_view(self, self.declarations, "classes")

    @property
    def constructor(self):
        """Return a name-indexed view over constructors declared in this class."""

        return make_named_child_view(self, self.declarations, "constructors", return_many=True)

    @property
    def destructor(self):
        """Return the destructor declared in this class, when present."""

        return self.declarations.destructor

    @property
    def method(self):
        """Return a name-indexed view over methods declared in this class."""

        return make_named_child_view(self, self.declarations, "methods", return_many=True)

    @property
    def variable(self):
        """Return a name-indexed view over instance variables declared in this class."""

        return make_named_child_view(self, self.declarations, "variables")

    @property
    def static_variable(self):
        """Return a name-indexed view over static variables declared in this class."""

        return make_named_child_view(self, self.declarations, "static_variables")

    @property
    def alias(self):
        """Return a name-indexed view over aliases declared in this class."""

        return make_named_child_view(self, self.declarations, "aliases")

    @property
    def alias_template(self):
        """Return a name-indexed view over alias templates declared in this class."""

        return make_named_child_view(self, self.declarations, "alias_templates")

    @property
    def enum(self):
        """Return a name-indexed view over nested enums declared in this class."""

        return make_named_child_view(self, self.declarations, "enums")

    @property
    def class_template(self):
        """Return a name-indexed view over nested class templates."""

        return make_named_child_view(self, self.declarations, "class_templates")

    @property
    def method_template(self):
        """Return a name-indexed view over method templates."""

        return make_named_child_view(self, self.declarations, "method_templates", return_many=True)

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
