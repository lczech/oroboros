from __future__ import annotations

"""Structured recursive C++ type objects for semantic declarations."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .element import CppElement
    from .template_ import CppTemplateArgument


# ==================================================================================================
#     Types
# ==================================================================================================


@dataclass(slots=True)
class CppType:
    """Represent one recursive C++ type expression.

    Plain value and builtin types are the leaves. Pointer, reference, and
    template-instantiated types wrap other ``CppType`` objects recursively.
    """

    # Whether this type value carries one top-level `const` qualifier.
    is_const: bool = False

    def render(self) -> str:
        """Render the type back into C++ spelling."""

        raise NotImplementedError


# ------------------------------------------------------------------------------
#     Named Types
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class NamedCppType(CppType):
    """Represent a plain named C++ type such as ``Widget`` or ``std::string``.

    The optional ``declaration`` links this leaf type back to the semantic
    declaration element it names when that element is known in the model. The
    optional ``canonical`` stores a resolved underlying type for reasoning,
    while ``name`` remains the original spelling used for rendering and emission.
    """

    # Original source-spelled name preserved for diagnostics and default emission.
    name: str = ""
    # Semantic declaration element this name refers to when the target is known.
    declaration: CppElement | None = None
    # Canonicalized underlying type used for semantic reasoning when available.
    canonical: CppType | None = None

    def render(self) -> str:
        qualifier = "const " if self.is_const else ""
        return f"{qualifier}{self.name}"


@dataclass(slots=True)
class PointerCppType(CppType):
    """Represent a pointer type that wraps one pointee ``CppType``."""

    # Type value referenced through this pointer.
    pointee: CppType | None = None

    def render(self) -> str:
        if isinstance(self.pointee, FunctionCppType):
            return self.pointee.render_with_declarator("*", is_const=self.is_const)
        qualifier = "const " if self.is_const else ""
        pointee = self.pointee.render() if self.pointee is not None else ""
        return f"{qualifier}{pointee}*"


@dataclass(slots=True)
class LValueReferenceCppType(CppType):
    """Represent an lvalue reference type that wraps one referred ``CppType``."""

    # Type value referred to by this lvalue reference.
    referred: CppType | None = None

    def render(self) -> str:
        if isinstance(self.referred, FunctionCppType):
            return self.referred.render_with_declarator("&", is_const=self.is_const)
        qualifier = "const " if self.is_const else ""
        referred = self.referred.render() if self.referred is not None else ""
        return f"{qualifier}{referred}&"


@dataclass(slots=True)
class RValueReferenceCppType(CppType):
    """Represent an rvalue reference type that wraps one referred ``CppType``."""

    # Type value referred to by this rvalue reference.
    referred: CppType | None = None

    def render(self) -> str:
        if isinstance(self.referred, FunctionCppType):
            return self.referred.render_with_declarator("&&", is_const=self.is_const)
        qualifier = "const " if self.is_const else ""
        referred = self.referred.render() if self.referred is not None else ""
        return f"{qualifier}{referred}&&"


@dataclass(slots=True)
class ArrayCppType(CppType):
    """Represent an array type that wraps one element ``CppType`` recursively."""

    # Element type stored in each array slot.
    element_type: CppType | None = None
    # Rendered array extent spelling when clang exposes one.
    extent: str | None = None

    def render(self) -> str:
        qualifier = "const " if self.is_const else ""
        element_type = self.element_type.render() if self.element_type is not None else ""
        extent = self.extent if self.extent is not None else ""
        return f"{qualifier}{element_type}[{extent}]"


@dataclass(slots=True)
class FunctionCppType(CppType):
    """Represent a function type with recursive return and parameter types."""

    # Return type produced by this function type.
    return_type: CppType | None = None
    # Parameter type values in declared order.
    parameters: list[CppType] = field(default_factory=list)
    # Whether this function type ends with a C-style variadic parameter pack.
    is_variadic: bool = False

    def render(self) -> str:
        return self.render_with_declarator()

    def render_with_declarator(self, declarator: str = "", *, is_const: bool | None = None) -> str:
        """Render the function type, optionally inserting a pointer/ref declarator."""

        effective_const = self.is_const if is_const is None else is_const
        qualifier = "const " if effective_const else ""
        return_type = self.return_type.render() if self.return_type is not None else ""
        rendered_parameters = [parameter.render() for parameter in self.parameters]
        if self.is_variadic:
            rendered_parameters.append("...")
        parameters = ", ".join(rendered_parameters)
        if declarator:
            return f"{qualifier}{return_type} ({declarator})({parameters})"
        return f"{qualifier}{return_type} ({parameters})"


@dataclass(slots=True)
class TemplateInstanceCppType(CppType):
    """Represent one template-instantiated type with structured arguments."""

    # Source-spelled template family name such as `std::vector`.
    template_name: str = ""
    # Structured template arguments in declared order.
    arguments: list["CppTemplateArgument"] = field(default_factory=list)

    def render(self) -> str:
        qualifier = "const " if self.is_const else ""
        rendered_arguments = ", ".join(_render_template_argument(argument) for argument in self.arguments)
        return f"{qualifier}{self.template_name}<{rendered_arguments}>"


# ------------------------------------------------------------------------------
#     Builtin Types
# ------------------------------------------------------------------------------


@dataclass(slots=True)
class BuiltinCppType(CppType):
    """Represent one C++ language builtin value type such as ``int`` or ``bool``."""

    # Semantic builtin category independent of exact source spelling.
    kind: Literal[
        "void",
        "nullptr_t",
        "bool",
        "char",
        "signed_char",
        "unsigned_char",
        "wchar_t",
        "char8_t",
        "char16_t",
        "char32_t",
        "short",
        "unsigned_short",
        "int",
        "unsigned_int",
        "long",
        "unsigned_long",
        "long_long",
        "unsigned_long_long",
        "float",
        "double",
        "long_double",
    ] = "int"

    def render(self) -> str:
        qualifier = "const " if self.is_const else ""
        return f"{qualifier}{cpp_builtin_type_spelling(self.kind)}"


_BUILTIN_CPP_TYPE_SPELLINGS: dict[str, str] = {
    "void": "void",
    "nullptr_t": "std::nullptr_t",
    "bool": "bool",
    "char": "char",
    "signed_char": "signed char",
    "unsigned_char": "unsigned char",
    "wchar_t": "wchar_t",
    "char8_t": "char8_t",
    "char16_t": "char16_t",
    "char32_t": "char32_t",
    "short": "short",
    "unsigned_short": "unsigned short",
    "int": "int",
    "unsigned_int": "unsigned int",
    "long": "long",
    "unsigned_long": "unsigned long",
    "long_long": "long long",
    "unsigned_long_long": "unsigned long long",
    "float": "float",
    "double": "double",
    "long_double": "long double",
}

_BUILTIN_CPP_KIND_BY_SPELLING: dict[str, str] = {
    spelling: kind
    for kind, spelling in _BUILTIN_CPP_TYPE_SPELLINGS.items()
}


def cpp_builtin_type_spelling(kind: str) -> str:
    """Return the canonical C++ spelling of one semantic builtin kind."""

    return _BUILTIN_CPP_TYPE_SPELLINGS[kind]


def cpp_builtin_kind_from_spelling(spelling: str) -> str | None:
    """Return the semantic builtin kind for one canonical C++ spelling."""

    return _BUILTIN_CPP_KIND_BY_SPELLING.get(spelling)


# ==================================================================================================
#     Type Comparison
# ==================================================================================================


def cpp_type_key(cpp_type: CppType | None) -> tuple[object, ...]:
    """Build one semantic structural key for a C++ type value."""

    if cpp_type is None:
        return ("none",)

    if isinstance(cpp_type, NamedCppType):
        declaration = cpp_type.declaration
        from .alias import CppAlias

        if isinstance(declaration, CppAlias) and cpp_type.canonical is not None:
            return _with_top_level_const(
                cpp_type_key(cpp_type.canonical),
                cpp_type.is_const,
            )
        if declaration is not None:
            return ("named_decl", cpp_type.is_const, declaration.qualified_name)
        if cpp_type.canonical is not None:
            return _with_top_level_const(
                cpp_type_key(cpp_type.canonical),
                cpp_type.is_const,
            )
        return ("named_spelling", cpp_type.is_const, cpp_type.name)

    if isinstance(cpp_type, PointerCppType):
        return ("pointer", cpp_type.is_const, cpp_type_key(cpp_type.pointee))

    if isinstance(cpp_type, LValueReferenceCppType):
        return ("lvalue_reference", cpp_type.is_const, cpp_type_key(cpp_type.referred))

    if isinstance(cpp_type, RValueReferenceCppType):
        return ("rvalue_reference", cpp_type.is_const, cpp_type_key(cpp_type.referred))

    if isinstance(cpp_type, ArrayCppType):
        return (
            "array",
            cpp_type.is_const,
            cpp_type.extent,
            cpp_type_key(cpp_type.element_type),
        )

    if isinstance(cpp_type, FunctionCppType):
        return (
            "function",
            cpp_type.is_const,
            cpp_type_key(cpp_type.return_type),
            tuple(cpp_type_key(parameter) for parameter in cpp_type.parameters),
            cpp_type.is_variadic,
        )

    if isinstance(cpp_type, TemplateInstanceCppType):
        from .template_ import _single_template_argument_key

        return (
            "template_instance",
            cpp_type.is_const,
            cpp_type.template_name,
            tuple(_single_template_argument_key(argument) for argument in cpp_type.arguments),
        )

    if isinstance(cpp_type, BuiltinCppType):
        return ("builtin", cpp_type.is_const, cpp_type.kind)

    raise TypeError(f"Unsupported C++ type for structural key: {type(cpp_type)!r}")


def cpp_types_equivalent(left: CppType | None, right: CppType | None) -> bool:
    """Check whether two C++ type values are semantically equivalent."""

    return cpp_type_key(left) == cpp_type_key(right)


def _with_top_level_const(
    type_key: tuple[object, ...],
    is_const: bool,
) -> tuple[object, ...]:
    """Overlay one top-level const qualifier onto a structural type key."""

    if not is_const or type_key == ("none",):
        return type_key
    return (type_key[0], True, *type_key[2:])


def _render_template_argument(argument: "CppTemplateArgument") -> str:
    """Render one structured template argument back into C++ spelling."""

    from .template_ import (
        CppNonTypeTemplateArgument,
        CppTemplateTemplateArgument,
        CppTypeTemplateArgument,
    )

    if isinstance(argument, CppTypeTemplateArgument):
        return argument.type.render() if argument.type is not None else ""

    if isinstance(argument, CppNonTypeTemplateArgument):
        return argument.value

    if isinstance(argument, CppTemplateTemplateArgument):
        return argument.name

    raise TypeError(f"Unsupported template argument for rendering: {type(argument)!r}")
