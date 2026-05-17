from __future__ import annotations

"""Enum semantic model objects."""

from dataclasses import dataclass, field

from .comment import CppDoc, PyDoc
from .element import CppElement
from .location import SourceLocation
from .type import CppType
from .visibility import CppVisibility


# ==================================================================================================
#     Facets
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Enumerator Facets
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppEnumeratorCppFacet:
    """Store parsed C++ details for one enumerator."""

    original_name: str | None = None
    value_spelling: str | None = None
    location: SourceLocation | None = None
    comment: str | None = None
    doc: CppDoc | None = None


@dataclass(slots=True)
class CppEnumeratorBindFacet:
    """Store binding settings for one enumerator."""

    active: bool | None = None


@dataclass(slots=True)
class CppEnumeratorPyFacet:
    """Store Python-facing choices for one enumerator."""

    name: str | None = None
    doc: PyDoc | None = None


# ------------------------------------------------------------------------------
#     Enum Facets
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppEnumCppFacet:
    """Store parsed C++ details for one enum."""

    original_name: str | None = None
    qualified_name: str | None = None
    underlying_type: CppType | None = None
    location: SourceLocation | None = None
    comment: str | None = None
    doc: CppDoc | None = None
    is_scoped: bool = False
    visibility: CppVisibility | None = None


@dataclass(slots=True)
class CppEnumBindFacet:
    """Store binding settings for one enum."""

    active: bool | None = None
    export_values: bool | None = None
    expose_scoped: bool | None = None


@dataclass(slots=True)
class CppEnumPyFacet:
    """Store Python-facing choices for one enum."""

    name: str | None = None
    doc: PyDoc | None = None


# ==================================================================================================
#     Elements
# ==================================================================================================


@dataclass(slots=True)
class CppEnumerator(CppElement):
    """Represent one enumerator owned by an enum."""

    cpp: CppEnumeratorCppFacet = field(default_factory=CppEnumeratorCppFacet)
    bind: CppEnumeratorBindFacet = field(default_factory=CppEnumeratorBindFacet)
    py: CppEnumeratorPyFacet = field(default_factory=CppEnumeratorPyFacet)


@dataclass(slots=True)
class CppEnum(CppElement):
    """Represent one enum declaration in the semantic model."""

    cpp: CppEnumCppFacet = field(default_factory=CppEnumCppFacet)
    bind: CppEnumBindFacet = field(default_factory=CppEnumBindFacet)
    py: CppEnumPyFacet = field(default_factory=CppEnumPyFacet)
    enumerators: list[CppEnumerator] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Adopt the owned enumerator nodes."""

        self._adopt_children(self.enumerators)

    def add_enumerator(self, enumerator: CppEnumerator) -> CppEnumerator:
        """Attach one enumerator to this enum."""

        return self._append_child(self.enumerators, enumerator)
