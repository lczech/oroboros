from __future__ import annotations

"""Enum semantic model objects."""

from dataclasses import dataclass, field

from .availability import CppAvailability
from .comment import CppDoc, PyDoc
from .element import CppElement
from .lookup import make_named_child_view
from .location import CppLocationInfo
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

    # Spelling written in the C++ source, before any Python-facing renaming.
    original_name: str | None = None
    # Enumerator value spelling as written in the declaration.
    value_spelling: str | None = None
    # Source location where this enumerator was declared.
    location: CppLocationInfo = field(default_factory=CppLocationInfo)
    # Parser-selected comment text attached to this enumerator declaration.
    attached_comment: str | None = None
    # Raw comment text reported by clang for provenance and debugging.
    clang_raw_comment: str | None = None
    # Normalized structured documentation parsed from `attached_comment`.
    doc: CppDoc | None = None
    # Availability annotations such as deprecation attached to this enumerator.
    availability: CppAvailability | None = None


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

    # Spelling written in the C++ source, before any Python-facing renaming.
    original_name: str | None = None
    # Structured parsed underlying integer type, when explicitly declared.
    underlying_type: CppType | None = None
    # Source locations where this enum was declared or defined.
    location: CppLocationInfo = field(default_factory=CppLocationInfo)
    # Parser-selected comment text attached to this enum declaration.
    attached_comment: str | None = None
    # Raw comment text reported by clang for provenance and debugging.
    clang_raw_comment: str | None = None
    # Normalized structured documentation parsed from `attached_comment`.
    doc: CppDoc | None = None
    # Availability annotations such as deprecation attached to this enum.
    availability: CppAvailability | None = None
    # Whether this enum was declared as a scoped enum class/struct.
    is_scoped: bool = False
    # Declared member visibility when clang exposes it.
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

    @property
    def enumerator(self):
        """Return a name-indexed view over this enum's enumerators."""

        return make_named_child_view(self, self, "enumerators")
