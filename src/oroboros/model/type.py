from __future__ import annotations

"""Structured C++ type objects for semantic declarations."""

from dataclasses import dataclass, field


# ==================================================================================================
#     Types
# ==================================================================================================


@dataclass(slots=True)
class CppType:
    """Represent a structured C++ type."""

    is_const: bool = False

    def render(self) -> str:
        """Render the type back into C++ spelling."""

        raise NotImplementedError


@dataclass(slots=True)
class NamedCppType(CppType):
    """Represent a plain named C++ type."""

    name: str = ""

    def render(self) -> str:
        qualifier = "const " if self.is_const else ""
        return f"{qualifier}{self.name}"


@dataclass(slots=True)
class PointerCppType(CppType):
    """Represent a pointer C++ type."""

    pointee: CppType | None = None

    def render(self) -> str:
        qualifier = "const " if self.is_const else ""
        pointee = self.pointee.render() if self.pointee is not None else ""
        return f"{qualifier}{pointee}*"


@dataclass(slots=True)
class LValueReferenceCppType(CppType):
    """Represent an lvalue reference C++ type."""

    referred: CppType | None = None

    def render(self) -> str:
        qualifier = "const " if self.is_const else ""
        referred = self.referred.render() if self.referred is not None else ""
        return f"{qualifier}{referred}&"


@dataclass(slots=True)
class RValueReferenceCppType(CppType):
    """Represent an rvalue reference C++ type."""

    referred: CppType | None = None

    def render(self) -> str:
        qualifier = "const " if self.is_const else ""
        referred = self.referred.render() if self.referred is not None else ""
        return f"{qualifier}{referred}&&"


@dataclass(slots=True)
class TemplateInstanceCppType(CppType):
    """Represent one template-instantiated C++ type."""

    template_name: str = ""
    arguments: list[CppType] = field(default_factory=list)

    def render(self) -> str:
        qualifier = "const " if self.is_const else ""
        rendered_arguments = ", ".join(argument.render() for argument in self.arguments)
        return f"{qualifier}{self.template_name}<{rendered_arguments}>"
