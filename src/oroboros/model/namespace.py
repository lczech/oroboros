from __future__ import annotations

"""Namespace semantic model objects."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .comment import CppDoc, PyDoc
from .element import CppElement
from .location import CppLocationInfo

if TYPE_CHECKING:
    from .alias import CppAliasInfo
    from .class_ import CppClass, CppClassBindFacet
    from .enum import CppEnum, CppEnumBindFacet
    from .function import CppFunction, CppFunctionBindFacet
    from .template_ import CppClassTemplate, CppFunctionTemplate


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
    aliases: list["CppAliasInfo"] = field(default_factory=list)


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
    function: "CppFunctionBindFacet" = field(default_factory=lambda: _make_function_bind_facet())
    enum: "CppEnumBindFacet" = field(default_factory=lambda: _make_enum_bind_facet())


def _make_class_bind_facet() -> "CppClassBindFacet":
    """Create one class-bind facet without import cycles at module import time."""

    from .class_ import CppClassBindFacet

    return CppClassBindFacet()


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
    # Nested namespaces declared inside this namespace.
    namespaces: list["CppNamespace"] = field(default_factory=list)
    # Top-level classes declared directly inside this namespace.
    classes: list["CppClass"] = field(default_factory=list)
    # Class template families declared directly inside this namespace.
    class_templates: list["CppClassTemplate"] = field(default_factory=list)
    # Free functions declared directly inside this namespace.
    functions: list["CppFunction"] = field(default_factory=list)
    # Function template families declared directly inside this namespace.
    function_templates: list["CppFunctionTemplate"] = field(default_factory=list)
    # Enums declared directly inside this namespace.
    enums: list["CppEnum"] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Adopt all typed child declaration collections."""

        self._adopt_children(self.namespaces)
        self._adopt_children(self.classes)
        self._adopt_children(self.class_templates)
        self._adopt_children(self.functions)
        self._adopt_children(self.function_templates)
        self._adopt_children(self.enums)

    def add_namespace(self, namespace: "CppNamespace") -> "CppNamespace":
        """Attach one nested namespace to this namespace."""

        return self._append_child(self.namespaces, namespace)

    def add_class(self, class_: "CppClass") -> "CppClass":
        """Attach one class declared directly in this namespace."""

        return self._append_child(self.classes, class_)

    def add_class_template(self, template: "CppClassTemplate") -> "CppClassTemplate":
        """Attach one class template family declared directly in this namespace."""

        return self._append_child(self.class_templates, template)

    def add_function(self, function: "CppFunction") -> "CppFunction":
        """Attach one free function declared directly in this namespace."""

        return self._append_child(self.functions, function)

    def add_function_template(self, template: "CppFunctionTemplate") -> "CppFunctionTemplate":
        """Attach one function template family declared directly in this namespace."""

        return self._append_child(self.function_templates, template)

    def add_enum(self, enum: "CppEnum") -> "CppEnum":
        """Attach one enum declared directly in this namespace."""

        return self._append_child(self.enums, enum)
