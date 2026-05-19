from __future__ import annotations

"""Module-root semantic model objects."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .comment import CppDoc, PyDoc
from .element import CppElement
from .lookup import make_named_child_view

if TYPE_CHECKING:
    from .alias import CppAliasInfo
    from .class_ import CppClass, CppClassBindFacet
    from .enum import CppEnum, CppEnumBindFacet
    from .function import CppFunction, CppFunctionBindFacet
    from .namespace import CppNamespace, CppNamespaceBindFacet
    from .template_ import CppClassTemplate, CppFunctionTemplate


# ==================================================================================================
#     Facets
# ==================================================================================================


@dataclass(slots=True)
class CppModuleCppFacet:
    """Store parsed C++ details attached to the semantic module root."""

    header_files: list[Path] = field(default_factory=list)
    comment: str | None = None
    doc: CppDoc | None = None
    aliases: list["CppAliasInfo"] = field(default_factory=list)


@dataclass(slots=True)
class CppModuleBindFacet:
    """Store binding settings for the semantic module root."""

    hooks: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CppModulePyFacet:
    """Store Python-facing choices attached to the semantic module root."""

    module_name: str | None = None
    doc: PyDoc | None = None


@dataclass(slots=True)
class CppModuleDefaults:
    """Store descendant defaults for the semantic module root."""

    namespace: "CppNamespaceBindFacet" = field(default_factory=lambda: _make_namespace_bind_facet())
    class_: "CppClassBindFacet" = field(default_factory=lambda: _make_class_bind_facet())
    function: "CppFunctionBindFacet" = field(default_factory=lambda: _make_function_bind_facet())
    enum: "CppEnumBindFacet" = field(default_factory=lambda: _make_enum_bind_facet())


def _make_namespace_bind_facet() -> "CppNamespaceBindFacet":
    """Create one namespace-bind facet without import cycles at module import time."""

    from .namespace import CppNamespaceBindFacet

    return CppNamespaceBindFacet()


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
class CppModule(CppElement):
    """Represent the semantic root that owns top-level declarations."""

    # Parsed C++ details attached to the semantic module root.
    cpp: CppModuleCppFacet = field(default_factory=CppModuleCppFacet)
    # Binding settings attached to the semantic module root itself.
    bind: CppModuleBindFacet = field(default_factory=CppModuleBindFacet)
    # Python-facing choices attached to the semantic module root.
    py: CppModulePyFacet = field(default_factory=CppModulePyFacet)
    # Inherited defaults applied to top-level declarations.
    defaults: CppModuleDefaults = field(default_factory=CppModuleDefaults)
    # Top-level namespaces parsed into this semantic module.
    namespaces: list["CppNamespace"] = field(default_factory=list)
    # Top-level non-template classes parsed into this semantic module.
    classes: list["CppClass"] = field(default_factory=list)
    # Top-level class template families parsed into this semantic module.
    class_templates: list["CppClassTemplate"] = field(default_factory=list)
    # Top-level free functions parsed into this semantic module.
    functions: list["CppFunction"] = field(default_factory=list)
    # Top-level function template families parsed into this semantic module.
    function_templates: list["CppFunctionTemplate"] = field(default_factory=list)
    # Top-level enums parsed into this semantic module.
    enums: list["CppEnum"] = field(default_factory=list)

    @property
    def scope_name(self) -> str | None:
        """Keep the semantic root out of C++ qualified names."""

        return None

    def __post_init__(self) -> None:
        """Adopt all typed top-level declaration collections."""

        self._adopt_children(self.namespaces)
        self._adopt_children(self.classes)
        self._adopt_children(self.class_templates)
        self._adopt_children(self.functions)
        self._adopt_children(self.function_templates)
        self._adopt_children(self.enums)

    def add_namespace(self, namespace: "CppNamespace") -> "CppNamespace":
        """Attach one top-level namespace to this semantic module."""

        return self._append_child(self.namespaces, namespace)

    def add_class(self, class_: "CppClass") -> "CppClass":
        """Attach one top-level class to this semantic module."""

        return self._append_child(self.classes, class_)

    def add_class_template(self, template: "CppClassTemplate") -> "CppClassTemplate":
        """Attach one top-level class template family to this semantic module."""

        return self._append_child(self.class_templates, template)

    def add_function(self, function: "CppFunction") -> "CppFunction":
        """Attach one top-level free function to this semantic module."""

        return self._append_child(self.functions, function)

    def add_function_template(self, template: "CppFunctionTemplate") -> "CppFunctionTemplate":
        """Attach one top-level function template family to this semantic module."""

        return self._append_child(self.function_templates, template)

    def add_enum(self, enum: "CppEnum") -> "CppEnum":
        """Attach one top-level enum to this semantic module."""

        return self._append_child(self.enums, enum)

    @property
    def namespace(self):
        """Return a name-indexed view over top-level namespaces."""

        return make_named_child_view(self, "namespaces")

    @property
    def class_(self):
        """Return a name-indexed view over top-level classes."""

        return make_named_child_view(self, "classes")

    @property
    def class_template(self):
        """Return a name-indexed view over top-level class templates."""

        return make_named_child_view(self, "class_templates")

    @property
    def function(self):
        """Return a name-indexed view over top-level free functions."""

        return make_named_child_view(self, "functions", return_many=True)

    @property
    def function_template(self):
        """Return a name-indexed view over top-level function templates."""

        return make_named_child_view(self, "function_templates", return_many=True)

    @property
    def enum(self):
        """Return a name-indexed view over top-level enums."""

        return make_named_child_view(self, "enums")
