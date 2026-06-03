from __future__ import annotations

from pathlib import Path
import unittest

from oroboros.model import *
from tests.support.model_builders import make_class, make_class_template_declaration, make_module, make_namespace


class ModelTemplateTest(unittest.TestCase):
    def _assert_observed_materialized_instance(
        self,
        instance: CppElement,
        *,
        spellings: list[str],
        locations: list[SourceLocation] | None = None,
    ) -> None:
        self.assertEqual(instance.cpp.instance_origin, "observed")
        self.assertEqual(instance.cpp.template_arguments, [])
        self.assertEqual(instance.cpp.observed_argument_spellings, spellings)
        if locations is not None:
            self.assertEqual(instance.cpp.observed_locations, locations)

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

    def test_observed_template_instances_materialize_recursively_in_subtrees(self) -> None:
        alias_template = CppAliasTemplate(name="Alias")
        alias_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        alias_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["short"])
        )
        inner_method_template = CppMethodTemplate(name="make_inner")
        inner_method_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        inner_method_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["double"])
        )
        class_template = CppClassTemplate(
            name="Vector",
            declaration=make_class_template_declaration(
                name="Vector",
                method_templates=[inner_method_template],
            ),
        )
        class_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        class_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["int"])
        )
        namespace = make_namespace(
            name="demo",
            alias_templates=[alias_template],
            class_templates=[class_template],
        )

        created_instances = add_observed_template_instances(namespace)

        self.assertEqual(len(created_instances), 3)
        self.assertEqual(len(alias_template.instances), 1)
        self.assertEqual(len(class_template.instances), 1)
        self.assertEqual(len(inner_method_template.instances), 1)
        self.assertIsInstance(alias_template.instances[0], CppAliasTemplateInstance)
        self.assertIsInstance(class_template.instances[0], CppClassTemplateInstance)
        self.assertIsInstance(
            inner_method_template.instances[0],
            CppMethodTemplateInstance,
        )
        self._assert_observed_materialized_instance(
            alias_template.instances[0],
            spellings=["short"],
        )
        self._assert_observed_materialized_instance(
            class_template.instances[0],
            spellings=["int"],
        )
        self._assert_observed_materialized_instance(
            inner_method_template.instances[0],
            spellings=["double"],
        )

    def test_template_family_add_observed_instances_materializes_only_that_family(self) -> None:
        alias_template = CppAliasTemplate(name="Alias")
        alias_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        alias_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["short"])
        )
        class_template = CppClassTemplate(name="Vector")
        class_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        class_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["int"])
        )
        function_template = CppFunctionTemplate(name="make_value")
        method_template = CppMethodTemplate(name="convert")
        function_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        function_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["double"])
        )
        method_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        method_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["char"])
        )

        created_alias_instances = alias_template.add_observed_instances()
        created_class_instances = class_template.add_observed_instances()
        created_function_instances = function_template.add_observed_instances()
        created_method_instances = method_template.add_observed_instances()

        self.assertEqual(len(created_alias_instances), 1)
        self.assertEqual(len(created_class_instances), 1)
        self.assertEqual(len(created_function_instances), 1)
        self.assertEqual(len(created_method_instances), 1)
        self.assertIs(created_alias_instances[0], alias_template.instances[0])
        self.assertIs(created_class_instances[0], class_template.instances[0])
        self.assertIs(created_function_instances[0], function_template.instances[0])
        self.assertIs(created_method_instances[0], method_template.instances[0])
        self._assert_observed_materialized_instance(alias_template.instances[0], spellings=["short"])
        self._assert_observed_materialized_instance(class_template.instances[0], spellings=["int"])
        self._assert_observed_materialized_instance(function_template.instances[0], spellings=["double"])
        self._assert_observed_materialized_instance(method_template.instances[0], spellings=["char"])

    def test_observed_materialization_reuses_manual_instance_and_attaches_observation_metadata(self) -> None:
        class_template = CppClassTemplate(name="Vector")
        class_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        observed_location = SourceLocation(file=Path("api/demo.hpp"), line=12, column=7)
        class_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(
                instantiation_spelling="Vector<int>",
                argument_spellings=["int"],
                locations=[observed_location],
            )
        )

        manual_instance = add_class_template_instance(
            class_template,
            [CppTypeTemplateArgument(type=NamedCppType(name="int"))],
        )
        created_instances = class_template.add_observed_instances()

        self.assertEqual(len(created_instances), 1)
        self.assertIs(created_instances[0], manual_instance)
        self.assertEqual(manual_instance.cpp.instance_origin, "manual")
        self.assertEqual(manual_instance.cpp.observed_argument_spellings, ["int"])
        self.assertEqual(manual_instance.cpp.observed_instantiation_spelling, "Vector<int>")
        self.assertEqual(manual_instance.cpp.observed_locations, [observed_location])
        self.assertEqual(len(manual_instance.cpp.template_arguments), 1)

    def test_manual_instance_creation_reuses_existing_observed_materialized_instance(self) -> None:
        class_template = CppClassTemplate(name="Vector")
        class_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        observed_location = SourceLocation(file=Path("api/demo.hpp"), line=18, column=5)
        class_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(
                instantiation_spelling="Vector<int>",
                argument_spellings=["int"],
                locations=[observed_location],
            )
        )

        observed_instance = class_template.add_observed_instances()[0]
        manual_instance = add_class_template_instance(
            class_template,
            [CppTypeTemplateArgument(type=NamedCppType(name="int"))],
        )

        self.assertIs(manual_instance, observed_instance)
        self.assertEqual(manual_instance.cpp.instance_origin, "manual")
        self.assertEqual(len(manual_instance.cpp.template_arguments), 1)
        self.assertEqual(manual_instance.cpp.observed_argument_spellings, ["int"])
        self.assertEqual(manual_instance.cpp.observed_locations, [observed_location])

    def test_observed_template_instance_materialization_can_filter_alias_templates(self) -> None:
        alias_template = CppAliasTemplate(name="Alias")
        alias_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        alias_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["int"])
        )
        namespace = make_namespace(
            name="demo",
            alias_templates=[alias_template],
        )

        created_instances = add_observed_template_instances(
            namespace,
            include_alias_templates=False,
        )

        self.assertEqual(created_instances, [])
        self.assertEqual(alias_template.instances, [])

    def test_observed_template_instance_materialization_can_filter_function_templates(self) -> None:
        function_template = CppFunctionTemplate(name="make_value")
        function_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        function_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["int"])
        )
        namespace = make_namespace(
            name="demo",
            function_templates=[function_template],
        )

        created_instances = add_observed_template_instances(
            namespace,
            include_function_templates=False,
        )

        self.assertEqual(created_instances, [])
        self.assertEqual(function_template.instances, [])

    def test_observed_template_instance_materialization_can_filter_method_templates(self) -> None:
        method_template = CppMethodTemplate(name="convert")
        method_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        method_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["int"])
        )
        owner = make_class(name="Widget", method_templates=[method_template])
        namespace = make_namespace(
            name="demo",
            classes=[owner],
        )

        created_instances = add_observed_template_instances(
            namespace,
            include_method_templates=False,
        )

        self.assertEqual(created_instances, [])
        self.assertEqual(method_template.instances, [])

    def test_enabled_observed_template_instance_materialization_uses_inherited_defaults(self) -> None:
        alias_template = CppAliasTemplate(name="Alias")
        alias_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        alias_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["short"])
        )
        class_template = CppClassTemplate(name="Vector")
        class_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        class_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["int"])
        )
        function_template = CppFunctionTemplate(name="make_value")
        method_template = CppMethodTemplate(name="convert")
        function_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        function_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["double"])
        )
        method_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        method_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["char"])
        )
        owner = make_class(name="Widget", method_templates=[method_template])
        namespace = make_namespace(
            name="demo",
            alias_templates=[alias_template],
            class_templates=[class_template],
            function_templates=[function_template],
            classes=[owner],
        )
        module = make_module(name="bindings", namespaces=[namespace])
        module.defaults.alias_template.materialize_observed_instances = True
        module.defaults.class_template.materialize_observed_instances = True
        module.defaults.function_template.materialize_observed_instances = False
        module.defaults.class_.active = None
        function_template.bind.materialize_observed_instances = True
        owner.defaults.method_template.materialize_observed_instances = True

        created_instances = add_enabled_observed_template_instances(module)

        self.assertEqual(len(created_instances), 4)
        self.assertEqual(len(alias_template.instances), 1)
        self.assertEqual(len(class_template.instances), 1)
        self.assertEqual(len(function_template.instances), 1)
        self.assertEqual(len(method_template.instances), 1)
        self._assert_observed_materialized_instance(alias_template.instances[0], spellings=["short"])
        self._assert_observed_materialized_instance(class_template.instances[0], spellings=["int"])
        self._assert_observed_materialized_instance(function_template.instances[0], spellings=["double"])
        self._assert_observed_materialized_instance(method_template.instances[0], spellings=["char"])

    def test_enabled_observed_template_instance_materialization_respects_override_precedence(self) -> None:
        module_alias_template = CppAliasTemplate(name="ModuleAlias")
        module_alias_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        module_alias_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["int"])
        )
        module_template = CppClassTemplate(name="ModuleVector")
        module_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        module_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["int"])
        )
        namespace_template = CppClassTemplate(name="NamespaceVector")
        namespace_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        namespace_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["double"])
        )
        direct_template = CppClassTemplate(name="DirectVector")
        direct_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        direct_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(argument_spellings=["char"])
        )
        owner = make_class(
            name="Owner",
            class_templates=[direct_template],
        )
        namespace = make_namespace(
            name="demo",
            alias_templates=[module_alias_template],
            class_templates=[module_template, namespace_template],
            classes=[owner],
        )
        module = make_module(name="bindings", namespaces=[namespace])
        module.defaults.alias_template.materialize_observed_instances = False
        module.defaults.class_template.materialize_observed_instances = True
        namespace.defaults.class_template.materialize_observed_instances = False
        owner.defaults.class_template.materialize_observed_instances = True
        module_alias_template.bind.materialize_observed_instances = True
        direct_template.bind.materialize_observed_instances = False

        created_instances = add_enabled_observed_template_instances(module)

        self.assertEqual(len(created_instances), 1)
        self.assertEqual(len(module_alias_template.instances), 1)
        self.assertEqual(module_template.instances, [])
        self.assertEqual(namespace_template.instances, [])
        self.assertEqual(direct_template.instances, [])

        direct_template.bind.materialize_observed_instances = True

        created_instances = add_enabled_observed_template_instances(module)

        self.assertEqual(len(created_instances), 2)
        self.assertEqual(module_template.instances, [])
        self.assertEqual(namespace_template.instances, [])
        self.assertEqual(len(direct_template.instances), 1)
        self._assert_observed_materialized_instance(
            direct_template.instances[0],
            spellings=["char"],
        )

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

    def test_observed_template_instance_materialization_rejects_unsupported_scope_types(self) -> None:
        function = CppFunction(name="make_value")

        with self.assertRaisesRegex(TypeError, "Unsupported template scope type"):
            add_observed_template_instances(function)

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
