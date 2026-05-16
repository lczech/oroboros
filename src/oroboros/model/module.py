from __future__ import annotations

"""Module-root semantic model objects."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .comment import CppDoc, PyDoc
from .element import CppElement

if TYPE_CHECKING:
    from .class_ import CppClass, CppClassBindFacet
    from .enum import CppEnum, CppEnumBindFacet
    from .function import CppFunction, CppFunctionBindFacet
    from .namespace import CppNamespace, CppNamespaceBindFacet


# ==================================================================================================
#     Facets
# ==================================================================================================


@dataclass(slots=True)
class CppModuleCppFacet:
    """Store parsed C++ facts attached to the semantic module root."""

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

    cpp: CppModuleCppFacet = field(default_factory=CppModuleCppFacet)
    bind: CppModuleBindFacet = field(default_factory=CppModuleBindFacet)
    py: CppModulePyFacet = field(default_factory=CppModulePyFacet)
    defaults: CppModuleDefaults = field(default_factory=CppModuleDefaults)
    namespaces: list["CppNamespace"] = field(default_factory=list)
    classes: list["CppClass"] = field(default_factory=list)
    functions: list["CppFunction"] = field(default_factory=list)
    enums: list["CppEnum"] = field(default_factory=list)

    @property
    def scope_name(self) -> str | None:
        """Keep the semantic root out of C++ qualified names."""

        return None

    def __post_init__(self) -> None:
        """Adopt all typed top-level declaration collections."""

        self.adopt_children(self.namespaces)
        self.adopt_children(self.classes)
        self.adopt_children(self.functions)
        self.adopt_children(self.enums)
