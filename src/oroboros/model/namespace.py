from __future__ import annotations

"""Namespace semantic model objects."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .comment import CppDoc, PyDoc
from .element import CppElement
from .location import SourceLocation

if TYPE_CHECKING:
    from .class_ import CppClass, CppClassBindFacet
    from .enum import CppEnum, CppEnumBindFacet
    from .function import CppFunction, CppFunctionBindFacet


# ==================================================================================================
#     Facets
# ==================================================================================================


@dataclass(slots=True)
class CppNamespaceCppFacet:
    """Store parsed C++ facts for one namespace."""

    original_name: str | None = None
    qualified_name: str | None = None
    location: SourceLocation | None = None
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

    cpp: CppNamespaceCppFacet = field(default_factory=CppNamespaceCppFacet)
    bind: CppNamespaceBindFacet = field(default_factory=CppNamespaceBindFacet)
    py: CppNamespacePyFacet = field(default_factory=CppNamespacePyFacet)
    defaults: CppNamespaceDefaults = field(default_factory=CppNamespaceDefaults)
    namespaces: list["CppNamespace"] = field(default_factory=list)
    classes: list["CppClass"] = field(default_factory=list)
    functions: list["CppFunction"] = field(default_factory=list)
    enums: list["CppEnum"] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Adopt all typed child declaration collections."""

        self.adopt_children(self.namespaces)
        self.adopt_children(self.classes)
        self.adopt_children(self.functions)
        self.adopt_children(self.enums)
