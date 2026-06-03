from __future__ import annotations

from pathlib import Path
import unittest

from oroboros.model import *
from tests.support.model_builders import make_class, make_class_template_declaration, make_module, make_namespace


class ModelTemplateTest(unittest.TestCase):
    def test_manual_alias_template_instance_creation_uses_template_wrappers(self) -> None:
        alias_template = CppAliasTemplate(name="Vec")
        alias_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        alias_template.declaration.cpp.target = TemplateInstanceCppType(
            template_name="std::vector",
            arguments=[CppTypeTemplateArgument(type=NamedCppType(name="T"))],
        )
        namespace = make_namespace(
            name="demo",
            alias_templates=[alias_template],
        )

        alias_instance = add_alias_template_instance(
            alias_template,
            [CppTypeTemplateArgument(type=NamedCppType(name="int"))],
        )

        self.assertIs(alias_template.owner, namespace)
        self.assertIs(alias_template.declaration.owner, alias_template)
        self.assertIs(alias_instance.owner, alias_template)
        self.assertEqual(alias_template.qualified_name, "demo::Vec")
        self.assertEqual(alias_template.declaration.qualified_name, "demo::Vec")
        self.assertEqual(alias_instance.qualified_name, "demo::Vec")
        self.assertIs(
            namespace.find_one_by_qualified_name("demo::Vec", types=CppAliasTemplate),
            alias_template,
        )
        self.assertIsInstance(alias_template.declaration.cpp.target, TemplateInstanceCppType)
        self.assertEqual(alias_template.declaration.cpp.target.template_name, "std::vector")

    def test_manual_template_instance_creation_uses_template_wrappers(self) -> None:
        class_template = CppClassTemplate(name="Vector")
        function_template = CppFunctionTemplate(name="make_value")
        method_template = CppMethodTemplate(name="convert")
        class_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        function_template.declaration.cpp.template_parameters.append(
            CppNonTypeTemplateParameter(name="N")
        )
        method_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="U")
        )
        namespace = make_namespace(
            name="demo",
            class_templates=[class_template],
            function_templates=[function_template],
            classes=[make_class(name="Widget", method_templates=[method_template])],
        )
        module = make_module(name="bindings", namespaces=[namespace])

        class_instance = add_class_template_instance(
            class_template,
            [CppTypeTemplateArgument(type=NamedCppType(name="int"))],
        )
        function_instance = add_template_instance(
            function_template,
            [CppNonTypeTemplateArgument(value="4")],
        )

        self.assertIs(class_template.owner, namespace)
        self.assertIs(function_template.owner, namespace)
        self.assertIs(class_template.declaration.owner, class_template)
        self.assertIs(function_template.declaration.owner, function_template)
        self.assertIs(class_instance.owner, class_template)
        self.assertIs(function_instance.owner, function_template)
        self.assertEqual(class_template.qualified_name, "demo::Vector")
        self.assertEqual(function_template.qualified_name, "demo::make_value")
        self.assertEqual(method_template.qualified_name, "demo::Widget::convert")
        self.assertEqual(class_template.declaration.qualified_name, "demo::Vector")
        self.assertEqual(function_template.declaration.qualified_name, "demo::make_value")
        self.assertEqual(method_template.declaration.qualified_name, "demo::Widget::convert")
        self.assertEqual(class_instance.qualified_name, "demo::Vector")
        self.assertEqual(function_instance.qualified_name, "demo::make_value")
        self.assertIs(module.find_one_by_qualified_name("demo::Vector", types=CppClassTemplate), class_template)
        self.assertIs(
            module.find_one_by_qualified_name("demo::make_value", types=CppFunctionTemplate),
            function_template,
        )
        self.assertIs(
            module.find_one_by_qualified_name("demo::Widget::convert", types=CppMethodTemplate),
            method_template,
        )
        self.assertIs(module.declarations.namespaces[0], namespace)

    def test_template_observation_hints_keep_normalized_spelling_and_locations(self) -> None:
        class_template = CppClassTemplate(name="Vector")
        first_location = SourceLocation(file=Path("api/demo.hpp"), line=12, column=7)
        second_location = SourceLocation(file=Path("api/demo.hpp"), line=20, column=3)
        class_template.declaration.cpp.template_observation_hints.append(
            CppTemplateObservationHint(
                spelling="demo::Vector<int>",
                locations=[first_location, second_location],
            )
        )

        self.assertEqual(len(class_template.declaration.cpp.template_observation_hints), 1)
        hint = class_template.declaration.cpp.template_observation_hints[0]
        self.assertEqual(hint.spelling, "demo::Vector<int>")
        self.assertEqual(hint.locations, [first_location, second_location])

    def test_template_observation_hints_exist_on_all_template_declaration_kinds(self) -> None:
        alias_template = CppAliasTemplate(name="Alias")
        class_template = CppClassTemplate(name="Vector")
        function_template = CppFunctionTemplate(name="make_value")
        method_template = CppMethodTemplate(name="convert")

        for template in [alias_template, class_template, function_template, method_template]:
            with self.subTest(template=type(template).__name__):
                self.assertEqual(template.declaration.cpp.template_observation_hints, [])

    def test_template_instance_validation_rejects_wrong_argument_kind(self) -> None:
        class_template = CppClassTemplate(name="Vector")
        class_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )

        with self.assertRaisesRegex(ValueError, "expects a type argument"):
            add_class_template_instance(
                class_template,
                [CppNonTypeTemplateArgument(value="4")],
            )

    def test_alias_template_instance_validation_rejects_wrong_argument_kind(self) -> None:
        alias_template = CppAliasTemplate(name="Alias")
        alias_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )

        with self.assertRaisesRegex(ValueError, "expects a type argument"):
            add_alias_template_instance(
                alias_template,
                [CppNonTypeTemplateArgument(value="4")],
            )

    def test_add_template_instance_rejects_unsupported_template_family_types(self) -> None:
        with self.assertRaisesRegex(TypeError, "Unsupported template family type"):
            add_template_instance(CppFunction(name="make_value"), [])

    def test_manual_method_template_instance_creation_uses_method_template_wrapper(self) -> None:
        method_template = CppMethodTemplate(name="convert")
        method_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        owner = make_class(name="Widget", method_templates=[method_template])
        namespace = make_namespace(name="demo", classes=[owner])

        instance = add_method_template_instance(
            method_template,
            [CppTypeTemplateArgument(type=NamedCppType(name="int"))],
        )

        self.assertIs(method_template.owner, owner)
        self.assertIs(method_template.declaration.owner, method_template)
        self.assertIs(instance.owner, method_template)
        self.assertEqual(method_template.qualified_name, "demo::Widget::convert")
        self.assertEqual(method_template.declaration.qualified_name, "demo::Widget::convert")
        self.assertEqual(instance.qualified_name, "demo::Widget::convert")

    def test_template_instance_validation_allows_omitting_defaulted_arguments(self) -> None:
        function_template = CppFunctionTemplate(name="make_value")
        function_template.declaration.cpp.template_parameters.extend(
            [
                CppTypeTemplateParameter(name="T"),
                CppNonTypeTemplateParameter(
                    name="N",
                    default=CppNonTypeTemplateArgument(value="4"),
                ),
            ]
        )

        instance = add_function_template_instance(
            function_template,
            [CppTypeTemplateArgument(type=NamedCppType(name="int"))],
        )

        self.assertEqual(len(instance.cpp.template_arguments), 1)
        self.assertIsInstance(instance.cpp.template_arguments[0], CppTypeTemplateArgument)
        self.assertEqual(instance.cpp.template_arguments[0].type.name, "int")

    def test_template_instance_deduplication_uses_structural_argument_identity(self) -> None:
        function_template = CppFunctionTemplate(name="make_value")
        function_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )

        first_instance = add_function_template_instance(
            function_template,
            [
                CppTypeTemplateArgument(
                    type=NamedCppType(
                        name="uint64_t",
                        canonical=BuiltinCppType(kind="unsigned_long"),
                    )
                )
            ],
        )
        second_instance = add_function_template_instance(
            function_template,
            [CppTypeTemplateArgument(type=BuiltinCppType(kind="unsigned_long"))],
        )

        self.assertIs(first_instance, second_instance)
        self.assertEqual(len(function_template.instances), 1)

    def test_class_template_instances_do_not_copy_generic_alias_children(self) -> None:
        class_template = CppClassTemplate(name="Box")
        class_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        class_template.declaration.add_alias(CppAlias(name="Value")).cpp.target = NamedCppType(name="T")

        instance = add_class_template_instance(
            class_template,
            [CppTypeTemplateArgument(type=NamedCppType(name="int"))],
        )

        self.assertEqual(instance.qualified_name, "Box")
        self.assertEqual(len(instance.cpp.template_arguments), 1)
        self.assertFalse(hasattr(instance, "aliases"))

    def test_template_instance_validation_rejects_missing_required_arguments(self) -> None:
        function_template = CppFunctionTemplate(name="make_value")
        function_template.declaration.cpp.template_parameters.extend(
            [
                CppTypeTemplateParameter(name="T"),
                CppNonTypeTemplateParameter(name="N"),
            ]
        )

        with self.assertRaisesRegex(ValueError, "missing a template argument"):
            add_function_template_instance(
                function_template,
                [CppTypeTemplateArgument(type=NamedCppType(name="int"))],
            )

    def test_template_instance_validation_checks_nested_template_template_shape(self) -> None:
        allocator_parameter = CppTemplateTemplateParameter(
            name="Alloc",
            parameters=[CppTypeTemplateParameter(name="T")],
        )
        class_template = CppClassTemplate(name="Vector")
        class_template.declaration.cpp.template_parameters.append(allocator_parameter)

        invalid_argument = CppTemplateTemplateArgument(
            name="BadAlloc",
            parameters=[CppNonTypeTemplateParameter(name="N")],
        )

        with self.assertRaisesRegex(ValueError, "wrong kind"):
            add_class_template_instance(
                class_template,
                [invalid_argument],
            )

    def test_recursive_template_template_parameters_are_supported(self) -> None:
        innermost_parameter = CppTypeTemplateParameter(name="T")
        middle_parameter = CppTemplateTemplateParameter(
            name="Alloc",
            parameters=[innermost_parameter],
        )
        outer_parameter = CppTemplateTemplateParameter(
            name="Container",
            parameters=[middle_parameter],
        )

        self.assertEqual(outer_parameter.name, "Container")
        self.assertEqual(len(outer_parameter.parameters), 1)
        self.assertIsInstance(outer_parameter.parameters[0], CppTemplateTemplateParameter)
        self.assertEqual(outer_parameter.parameters[0].name, "Alloc")
        self.assertEqual(len(outer_parameter.parameters[0].parameters), 1)
        self.assertIsInstance(
            outer_parameter.parameters[0].parameters[0],
            CppTypeTemplateParameter,
        )
        self.assertEqual(
            outer_parameter.parameters[0].parameters[0].keyword,
            "typename",
        )
        self.assertEqual(outer_parameter.parameters[0].parameters[0].name, "T")
