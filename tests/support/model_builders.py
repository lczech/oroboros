from __future__ import annotations

from oroboros.model import CppClass, CppClassDeclarations, CppClassTemplateDeclaration, CppModule, CppNamespace, CppScopeDeclarations


def make_class(*, declarations: CppClassDeclarations | None = None, **kwargs) -> CppClass:
    """Build one class while allowing direct declaration-list keyword arguments in tests."""

    declaration_kwargs = {}
    for key in (
        "classes",
        "constructors",
        "destructor",
        "methods",
        "variables",
        "static_variables",
        "aliases",
        "alias_templates",
        "enums",
        "class_templates",
        "function_templates",
    ):
        if key in kwargs:
            declaration_kwargs[key] = kwargs.pop(key)

    declaration_container = declarations if declarations is not None else CppClassDeclarations()
    for key, value in declaration_kwargs.items():
        if key == "destructor":
            setattr(declaration_container, key, value)
            continue
        setattr(declaration_container, key, list(value))

    return CppClass(declarations=declaration_container, **kwargs)


def make_class_template_declaration(
    *,
    declarations: CppClassDeclarations | None = None,
    **kwargs,
) -> CppClassTemplateDeclaration:
    """Build one class-template declaration with direct declaration-list keyword arguments."""

    declaration_kwargs = {}
    for key in (
        "classes",
        "constructors",
        "destructor",
        "methods",
        "variables",
        "static_variables",
        "aliases",
        "alias_templates",
        "enums",
        "class_templates",
        "function_templates",
    ):
        if key in kwargs:
            declaration_kwargs[key] = kwargs.pop(key)

    declaration_container = declarations if declarations is not None else CppClassDeclarations()
    for key, value in declaration_kwargs.items():
        if key == "destructor":
            setattr(declaration_container, key, value)
            continue
        setattr(declaration_container, key, list(value))

    return CppClassTemplateDeclaration(declarations=declaration_container, **kwargs)


def make_namespace(*, declarations: CppScopeDeclarations | None = None, **kwargs) -> CppNamespace:
    """Build one namespace while allowing direct declaration-list keyword arguments in tests."""

    declaration_kwargs = {}
    for key in (
        "namespaces",
        "classes",
        "alias_templates",
        "class_templates",
        "functions",
        "function_templates",
        "variables",
        "enums",
        "aliases",
    ):
        if key in kwargs:
            declaration_kwargs[key] = kwargs.pop(key)

    declaration_container = declarations if declarations is not None else CppScopeDeclarations()
    for key, value in declaration_kwargs.items():
        setattr(declaration_container, key, list(value))

    return CppNamespace(declarations=declaration_container, **kwargs)


def make_module(*, declarations: CppScopeDeclarations | None = None, **kwargs) -> CppModule:
    """Build one module while allowing direct declaration-list keyword arguments in tests."""

    declaration_kwargs = {}
    for key in (
        "namespaces",
        "classes",
        "alias_templates",
        "class_templates",
        "functions",
        "function_templates",
        "variables",
        "enums",
        "aliases",
    ):
        if key in kwargs:
            declaration_kwargs[key] = kwargs.pop(key)

    declaration_container = declarations if declarations is not None else CppScopeDeclarations()
    for key, value in declaration_kwargs.items():
        setattr(declaration_container, key, list(value))

    return CppModule(declarations=declaration_container, **kwargs)
