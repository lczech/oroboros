from __future__ import annotations

"""Module-root semantic model objects."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .comment import CppDoc, PyDoc
from .element import CppElement
from .lookup import make_named_child_view
from .namespace import CppScopeDeclarations

if TYPE_CHECKING:
    from .alias import CppAlias
    from .alias_template import CppAliasTemplate
    from .class_ import CppClass, CppClassBindFacet
    from .enum import CppEnum, CppEnumBindFacet
    from .function import CppFunction, CppFunctionBindFacet
    from .namespace import CppNamespace, CppNamespaceBindFacet
    from .template_ import CppClassTemplate, CppFunctionTemplate, CppTemplateBindFacet
    from .variable import CppVariable, CppVariableBindFacet


# ==================================================================================================
#     Facets
# ==================================================================================================


@dataclass(slots=True)
class CppModuleCppFacet:
    """Store parsed C++ details attached to the semantic module root."""

    header_files: list[Path] = field(default_factory=list)
    comment: str | None = None
    doc: CppDoc | None = None


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

    namespace: "CppNamespaceBindFacet" = field(
        default_factory=lambda: _make_namespace_bind_facet()
    )
    class_: "CppClassBindFacet" = field(
        default_factory=lambda: _make_class_bind_facet()
    )
    class_template: "CppTemplateBindFacet" = field(
        default_factory=lambda: _make_template_bind_facet()
    )
    function: "CppFunctionBindFacet" = field(
        default_factory=lambda: _make_function_bind_facet()
    )
    function_template: "CppTemplateBindFacet" = field(
        default_factory=lambda: _make_template_bind_facet()
    )
    variable: "CppVariableBindFacet" = field(
        default_factory=lambda: _make_variable_bind_facet()
    )
    enum: "CppEnumBindFacet" = field(
        default_factory=lambda: _make_enum_bind_facet()
    )
    alias_template: "CppTemplateBindFacet" = field(
        default_factory=lambda: _make_template_bind_facet()
    )


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


def _make_template_bind_facet() -> "CppTemplateBindFacet":
    """Create one template-bind facet without import cycles at module import time."""

    from .template_ import CppTemplateBindFacet

    return CppTemplateBindFacet()


def _make_enum_bind_facet() -> "CppEnumBindFacet":
    """Create one enum-bind facet without import cycles at module import time."""

    from .enum import CppEnumBindFacet

    return CppEnumBindFacet()


def _make_variable_bind_facet() -> "CppVariableBindFacet":
    """Create one variable-bind facet without import cycles at module import time."""

    from .variable import CppVariableBindFacet

    return CppVariableBindFacet()


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
    # Direct top-level declarations owned by this semantic module root.
    declarations: CppScopeDeclarations = field(default_factory=CppScopeDeclarations)

    @property
    def scope_name(self) -> str | None:
        """Keep the semantic root out of C++ qualified names."""

        return None

    def __post_init__(self) -> None:
        """Adopt all typed top-level declaration collections."""

        for declaration_list in (
            self.declarations.namespaces,
            self.declarations.classes,
            self.declarations.class_templates,
            self.declarations.alias_templates,
            self.declarations.functions,
            self.declarations.function_templates,
            self.declarations.variables,
            self.declarations.enums,
            self.declarations.aliases,
        ):
            self._adopt_children(declaration_list)

    def add_namespace(self, namespace: "CppNamespace") -> "CppNamespace":
        """Attach one top-level namespace to this semantic module."""

        return self._append_child(self.declarations.namespaces, namespace)

    def add_class(self, class_: "CppClass") -> "CppClass":
        """Attach one top-level class to this semantic module."""

        return self._append_child(self.declarations.classes, class_)

    def add_class_template(self, template: "CppClassTemplate") -> "CppClassTemplate":
        """Attach one top-level class template family to this semantic module."""

        return self._append_child(self.declarations.class_templates, template)

    def add_alias_template(self, template: "CppAliasTemplate") -> "CppAliasTemplate":
        """Attach one top-level alias template family to this semantic module."""

        return self._append_child(self.declarations.alias_templates, template)

    def add_function(self, function: "CppFunction") -> "CppFunction":
        """Attach one top-level free function to this semantic module."""

        return self._append_child(self.declarations.functions, function)

    def add_function_template(self, template: "CppFunctionTemplate") -> "CppFunctionTemplate":
        """Attach one top-level function template family to this semantic module."""

        return self._append_child(self.declarations.function_templates, template)

    def add_variable(self, variable: "CppVariable") -> "CppVariable":
        """Attach one top-level variable to this semantic module."""

        return self._append_child(self.declarations.variables, variable)

    def add_enum(self, enum: "CppEnum") -> "CppEnum":
        """Attach one top-level enum to this semantic module."""

        return self._append_child(self.declarations.enums, enum)

    def add_alias(self, alias: "CppAlias") -> "CppAlias":
        """Attach one top-level alias to this semantic module."""

        return self._append_child(self.declarations.aliases, alias)

    @property
    def namespace(self):
        """Return a name-indexed view over top-level namespaces."""

        return make_named_child_view(self, self.declarations, "namespaces")

    @property
    def class_(self):
        """Return a name-indexed view over top-level classes."""

        return make_named_child_view(self, self.declarations, "classes")

    @property
    def class_template(self):
        """Return a name-indexed view over top-level class templates."""

        return make_named_child_view(self, self.declarations, "class_templates")

    @property
    def alias_template(self):
        """Return a name-indexed view over top-level alias templates."""

        return make_named_child_view(self, self.declarations, "alias_templates")

    @property
    def function(self):
        """Return a name-indexed view over top-level free functions."""

        return make_named_child_view(self, self.declarations, "functions", return_many=True)

    @property
    def function_template(self):
        """Return a name-indexed view over top-level function templates."""

        return make_named_child_view(self, self.declarations, "function_templates", return_many=True)

    @property
    def variable(self):
        """Return a name-indexed view over top-level variables."""

        return make_named_child_view(self, self.declarations, "variables")

    @property
    def enum(self):
        """Return a name-indexed view over top-level enums."""

        return make_named_child_view(self, self.declarations, "enums")

    @property
    def alias(self):
        """Return a name-indexed view over top-level aliases."""

        return make_named_child_view(self, self.declarations, "aliases")
