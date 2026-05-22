from __future__ import annotations

"""Namespace semantic model objects."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .comment import CppDoc, PyDoc
from .element import CppElement
from .lookup import make_named_child_view
from .location import CppLocationInfo

if TYPE_CHECKING:
    from .alias import CppAlias
    from .class_ import CppClass, CppClassBindFacet
    from .enum import CppEnum, CppEnumBindFacet
    from .function import CppFunction, CppFunctionBindFacet
    from .template_ import CppClassTemplate, CppFunctionTemplate, CppTemplateBindFacet


# ==================================================================================================
#     Facets
# ==================================================================================================


@dataclass(slots=True)
class CppNamespaceCppFacet:
    """Store parsed C++ details for one namespace."""

    original_name: str | None = None
    location: CppLocationInfo = field(default_factory=CppLocationInfo)
    comment: str | None = None
    doc: CppDoc | None = None
    is_inline: bool = False


@dataclass(slots=True)
class CppNamespaceBindFacet:
    """Store binding settings for one namespace."""

    active: bool | None = None
    hooks: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CppNamespacePyFacet:
    """Store Python-facing choices for one namespace."""

    name: str | None = None
    submodule: str | None = None
    doc: PyDoc | None = None


@dataclass(slots=True)
class CppNamespaceDefaults:
    """Store descendant defaults for one namespace scope."""

    namespace: CppNamespaceBindFacet = field(default_factory=CppNamespaceBindFacet)
    class_: "CppClassBindFacet" = field(default_factory=lambda: _make_class_bind_facet())
    class_template: "CppTemplateBindFacet" = field(default_factory=lambda: _make_template_bind_facet())
    function: "CppFunctionBindFacet" = field(default_factory=lambda: _make_function_bind_facet())
    function_template: "CppTemplateBindFacet" = field(default_factory=lambda: _make_template_bind_facet())
    enum: "CppEnumBindFacet" = field(default_factory=lambda: _make_enum_bind_facet())


def _make_class_bind_facet() -> "CppClassBindFacet":
    """Create one class-bind facet without import cycles at module import time."""

    from .class_ import CppClassBindFacet

    return CppClassBindFacet()


def _make_function_bind_facet() -> "CppFunctionBindFacet":
    """Create one function-bind facet without import cycles at module import time."""

    from .function import CppFunctionBindFacet

    return CppFunctionBindFacet()


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
class CppScopeDeclarations:
    """Store direct declarations owned by one module-like or namespace-like scope."""

    _is_child_container = True

    # Nested namespaces declared directly inside this scope.
    namespaces: list["CppNamespace"] = field(default_factory=list)
    # Non-template classes declared directly inside this scope.
    classes: list["CppClass"] = field(default_factory=list)
    # Class template families declared directly inside this scope.
    class_templates: list["CppClassTemplate"] = field(default_factory=list)
    # Free functions declared directly inside this scope.
    functions: list["CppFunction"] = field(default_factory=list)
    # Function template families declared directly inside this scope.
    function_templates: list["CppFunctionTemplate"] = field(default_factory=list)
    # Enums declared directly inside this scope.
    enums: list["CppEnum"] = field(default_factory=list)
    # Aliases declared directly inside this scope.
    aliases: list["CppAlias"] = field(default_factory=list)


# ==================================================================================================
#     Elements
# ==================================================================================================


@dataclass(slots=True)
class CppNamespace(CppElement):
    """Represent one namespace scope in the semantic model."""

    # Parsed C++ details for this namespace.
    cpp: CppNamespaceCppFacet = field(default_factory=CppNamespaceCppFacet)
    # Binding settings for this namespace itself.
    bind: CppNamespaceBindFacet = field(default_factory=CppNamespaceBindFacet)
    # Python-facing choices for this namespace.
    py: CppNamespacePyFacet = field(default_factory=CppNamespacePyFacet)
    # Inherited defaults applied to declarations inside this namespace.
    defaults: CppNamespaceDefaults = field(default_factory=CppNamespaceDefaults)
    # Direct declarations owned by this namespace scope.
    declarations: CppScopeDeclarations = field(default_factory=CppScopeDeclarations)

    def __post_init__(self) -> None:
        """Adopt all typed child declaration collections."""

        for declaration_list in (
            self.declarations.namespaces,
            self.declarations.classes,
            self.declarations.class_templates,
            self.declarations.functions,
            self.declarations.function_templates,
            self.declarations.enums,
            self.declarations.aliases,
        ):
            self._adopt_children(declaration_list)

    def add_namespace(self, namespace: "CppNamespace") -> "CppNamespace":
        """Attach one nested namespace to this namespace."""

        return self._append_child(self.declarations.namespaces, namespace)

    def add_class(self, class_: "CppClass") -> "CppClass":
        """Attach one class declared directly in this namespace."""

        return self._append_child(self.declarations.classes, class_)

    def add_class_template(self, template: "CppClassTemplate") -> "CppClassTemplate":
        """Attach one class template family declared directly in this namespace."""

        return self._append_child(self.declarations.class_templates, template)

    def add_function(self, function: "CppFunction") -> "CppFunction":
        """Attach one free function declared directly in this namespace."""

        return self._append_child(self.declarations.functions, function)

    def add_function_template(self, template: "CppFunctionTemplate") -> "CppFunctionTemplate":
        """Attach one function template family declared directly in this namespace."""

        return self._append_child(self.declarations.function_templates, template)

    def add_enum(self, enum: "CppEnum") -> "CppEnum":
        """Attach one enum declared directly in this namespace."""

        return self._append_child(self.declarations.enums, enum)

    def add_alias(self, alias: "CppAlias") -> "CppAlias":
        """Attach one alias declared directly in this namespace."""

        return self._append_child(self.declarations.aliases, alias)

    @property
    def namespace(self):
        """Return a name-indexed view over nested namespaces."""

        return make_named_child_view(self, self.declarations, "namespaces")

    @property
    def class_(self):
        """Return a name-indexed view over classes declared in this namespace."""

        return make_named_child_view(self, self.declarations, "classes")

    @property
    def class_template(self):
        """Return a name-indexed view over class templates declared in this namespace."""

        return make_named_child_view(self, self.declarations, "class_templates")

    @property
    def function(self):
        """Return a name-indexed view over free functions declared in this namespace."""

        return make_named_child_view(self, self.declarations, "functions", return_many=True)

    @property
    def function_template(self):
        """Return a name-indexed view over function templates declared in this namespace."""

        return make_named_child_view(self, self.declarations, "function_templates", return_many=True)

    @property
    def enum(self):
        """Return a name-indexed view over enums declared in this namespace."""

        return make_named_child_view(self, self.declarations, "enums")

    @property
    def alias(self):
        """Return a name-indexed view over aliases declared in this namespace."""

        return make_named_child_view(self, self.declarations, "aliases")
