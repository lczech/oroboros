from __future__ import annotations

"""Free-function and parameter semantic model objects."""

from dataclasses import dataclass, field

from .comment import CppDoc, PyDoc
from .element import CppElement
from .lookup import make_named_child_view
from .location import CppLocationInfo
from .operator_ import CppOperator, CppOperatorBind
from .type import CppType


# ==================================================================================================
#     Facets
# ==================================================================================================


# ------------------------------------------------------------------------------
#     Parameter Facets
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppParameterCppFacet:
    """Store parsed C++ details for one function parameter."""

    original_name: str | None = None
    type: CppType | None = None
    default_value: str | None = None
    location: CppLocationInfo = field(default_factory=CppLocationInfo)
    doc: str | None = None


@dataclass(slots=True)
class CppParameterBindFacet:
    """Store binding settings for one function parameter."""

    none_accepted: bool | None = None
    no_convert: bool | None = None


@dataclass(slots=True)
class CppParameterPyFacet:
    """Store Python-facing choices for one function parameter."""

    name: str | None = None
    doc: str | None = None
    sig: str | None = None


# ------------------------------------------------------------------------------
#     Function Facets
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class CppFunctionCppFacet:
    """Store parsed C++ details for one free function."""

    original_name: str | None = None
    operator: CppOperator | None = None
    return_type: CppType | None = None
    location: CppLocationInfo = field(default_factory=CppLocationInfo)
    comment: str | None = None
    doc: CppDoc | None = None
    overload_index: int | None = None
    is_noexcept: bool = False


@dataclass(slots=True)
class CppFunctionBindFacet:
    """Store binding settings for one function-like declaration."""

    active: bool | None = None
    operator: CppOperatorBind | None = None
    return_value_policy: str | None = None
    keep_alive: tuple[int, int] | None = None
    call_guards: list[str] = field(default_factory=list)
    hooks: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CppFunctionPyFacet:
    """Store Python-facing choices for one free function."""

    name: str | None = None
    doc: PyDoc | None = None
    sig: str | None = None


# ==================================================================================================
#     Elements
# ==================================================================================================


@dataclass(slots=True)
class CppParameter(CppElement):
    """Represent one parameter owned by a function-like declaration."""

    cpp: CppParameterCppFacet = field(default_factory=CppParameterCppFacet)
    bind: CppParameterBindFacet = field(default_factory=CppParameterBindFacet)
    py: CppParameterPyFacet = field(default_factory=CppParameterPyFacet)


@dataclass(slots=True)
class CppFunction(CppElement):
    """Represent one free function in the semantic model."""

    # Parsed C++ details for this free function.
    cpp: CppFunctionCppFacet = field(default_factory=CppFunctionCppFacet)
    # Binding settings for this free function itself.
    bind: CppFunctionBindFacet = field(default_factory=CppFunctionBindFacet)
    # Python-facing choices for this free function.
    py: CppFunctionPyFacet = field(default_factory=CppFunctionPyFacet)
    # Parameters declared directly on this free function.
    parameters: list[CppParameter] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Adopt the owned parameter nodes."""

        self._adopt_children(self.parameters)

    def add_parameter(self, parameter: CppParameter) -> CppParameter:
        """Attach one parameter to this free function."""

        return self._append_child(self.parameters, parameter)

    @property
    def parameter(self):
        """Return a name-indexed view over this function's parameters."""

        return make_named_child_view(self, self, "parameters")
