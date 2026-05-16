from __future__ import annotations

import unittest

from oroboros.model import (
    ArrayCppType,
    BuiltinCppType,
    CppAliasInfo,
    CppClass,
    CppClassBase,
    CppClassBindFacet,
    CppClassDefaults,
    CppClassTemplate,
    CppClassTemplateDecl,
    CppClassTemplateDefaults,
    CppClassTemplateInstance,
    CppConstructor,
    CppDoc,
    CppEnum,
    CppEnumBindFacet,
    CppEnumerator,
    CppField,
    CppFieldBindFacet,
    CppFunction,
    CppFunctionBindFacet,
    CppFunctionTemplate,
    FunctionCppType,
    CppMethod,
    CppModule,
    CppModuleDefaults,
    CppNamespace,
    CppNamespaceBindFacet,
    CppNamespaceDefaults,
    CppNonTypeTemplateArgument,
    CppObservedTemplateInstance,
    CppOperator,
    CppOperatorBind,
    CppParameter,
    CppFunctionTemplateDecl,
    CppFunctionTemplateDefaults,
    CppNonTypeTemplateParameter,
    CppTemplateTemplateArgument,
    CppTemplateTemplateParameter,
    CppTypeTemplateArgument,
    CppTypeTemplateParameter,
    CppFunctionTemplateInstance,
    CppVisibility,
    add_template_instance,
    find_aliases,
    NamedCppType,
    PointerCppType,
    add_class_template_instance,
    add_function_template_instance,
    add_observed_template_instances,
    build_py_doc_from_cpp_doc,
)


class ModelScaffoldTest(unittest.TestCase):
    def test_model_nodes_adopt_children_and_compute_qualified_names(self) -> None:
        parameter = CppParameter(name="value")
        constructor = CppConstructor(name="Widget", parameters=[CppParameter(name="seed")])
        method = CppMethod(name="size", parameters=[parameter])
        enum_ = CppEnum(name="Kind", enumerators=[CppEnumerator(name="primary")])
        cls = CppClass(
            name="Widget",
            constructors=[constructor],
            methods=[method],
            enums=[enum_],
        )
        cls.cpp.aliases.append(
            CppAliasInfo(
                name="SizeType",
                qualified_name="demo::Widget::SizeType",
                target=NamedCppType(name="std::size_t"),
            )
        )
        namespace = CppNamespace(name="demo", classes=[cls])
        module = CppModule(name="bindings", namespaces=[namespace])

        self.assertIs(namespace.owner, module)
        self.assertIs(cls.owner, namespace)
        self.assertIs(constructor.owner, cls)
        self.assertIs(method.owner, cls)
        self.assertIs(parameter.owner, method)
        self.assertIs(enum_.owner, cls)
        self.assertIs(enum_.enumerators[0].owner, enum_)
        self.assertEqual(namespace.qualified_name, "demo")
        self.assertEqual(cls.qualified_name, "demo::Widget")
        self.assertEqual(method.qualified_name, "demo::Widget::size")
        self.assertEqual(parameter.qualified_name, "demo::Widget::size::value")
        self.assertEqual(cls.cpp.aliases[0].qualified_name, "demo::Widget::SizeType")

    def test_aliases_preserve_target_type_and_can_be_found_in_scope_metadata(self) -> None:
        namespace = CppNamespace(name="demo")
        namespace.cpp.aliases.append(
            CppAliasInfo(
                name="Index",
                qualified_name="demo::Index",
                target=NamedCppType(name="std::size_t"),
                kind="using",
            )
        )

        self.assertEqual(namespace.cpp.aliases[0].qualified_name, "demo::Index")
        self.assertEqual(namespace.cpp.aliases[0].target.render(), "std::size_t")
        self.assertEqual(namespace.cpp.aliases[0].kind, "using")

    def test_find_aliases_discovers_class_aliases_across_subtrees(self) -> None:
        cls = CppClass(name="Widget")
        cls.cpp.qualified_name = "demo::Widget"
        namespace = CppNamespace(name="demo", classes=[cls])
        namespace.cpp.aliases.extend(
            [
                CppAliasInfo(
                    name="WidgetAlias",
                    qualified_name="demo::WidgetAlias",
                    target=NamedCppType(name="demo::Widget"),
                ),
                CppAliasInfo(
                    name="SizeType",
                    qualified_name="demo::SizeType",
                    target=NamedCppType(name="std::size_t"),
                ),
            ]
        )
        nested = CppNamespace(name="detail")
        nested.cpp.aliases.append(
            CppAliasInfo(
                name="WidgetHandle",
                qualified_name="demo::detail::WidgetHandle",
                target=NamedCppType(name="demo::Widget"),
            )
        )
        namespace.namespaces.append(nested)
        namespace.adopt_children(namespace.namespaces)

        aliases = find_aliases(namespace, cls)

        self.assertEqual(
            [alias.name for alias in aliases],
            ["WidgetAlias", "WidgetHandle"],
        )

    def test_parse_stage_starts_with_default_bind_and_default_py_facets(self) -> None:
        parameter = CppParameter(name="value")
        constructor = CppConstructor(name="Widget")
        method = CppMethod(name="size", parameters=[parameter])
        function = CppFunction(name="make_widget", parameters=[CppParameter(name="seed")])
        enum_ = CppEnum(name="Kind", enumerators=[CppEnumerator(name="primary")])
        field = CppField(name="size")
        cls = CppClass(
            name="Widget",
            constructors=[constructor],
            methods=[method],
            fields=[field],
            enums=[enum_],
        )
        namespace = CppNamespace(name="demo", classes=[cls], functions=[function])
        module = CppModule(name="bindings", namespaces=[namespace])

        self.assertIsNotNone(module.py)
        self.assertIsNotNone(namespace.py)
        self.assertIsNotNone(cls.py)
        self.assertIsNotNone(function.py)
        self.assertIsNotNone(method.py)
        self.assertIsNotNone(constructor.py)
        self.assertIsNotNone(parameter.py)
        self.assertIsNotNone(enum_.py)
        self.assertIsNotNone(enum_.enumerators[0].py)
        self.assertIsNotNone(field.py)
        self.assertIsNone(module.py.module_name)
        self.assertIsNone(namespace.py.name)
        self.assertIsNone(cls.py.name)
        self.assertIsNone(function.py.name)
        self.assertIsNone(method.py.name)
        self.assertIsNone(parameter.py.name)
        self.assertIsNone(enum_.py.name)
        self.assertIsNone(enum_.enumerators[0].py.name)
        self.assertIsNone(field.py.name)
        self.assertIsNone(namespace.bind.active)
        self.assertIsNone(cls.bind.active)
        self.assertIsNone(function.bind.active)
        self.assertIsNone(method.bind.active)
        self.assertIsNone(constructor.bind.active)
        self.assertIsNone(field.bind.active)
        self.assertIsNone(enum_.bind.active)
        self.assertIsNone(enum_.enumerators[0].bind.active)

    def test_operator_metadata_lives_in_cpp_and_bind_facets(self) -> None:
        free_operator = CppFunction(name="operator+")
        free_operator.cpp.operator = CppOperator(kind="punctuation", symbol="+")
        free_operator.bind.operator = CppOperatorBind(mode="named")

        method_operator = CppMethod(name="operator[]")
        method_operator.cpp.operator = CppOperator(kind="punctuation", symbol="[]")
        method_operator.bind.operator = CppOperatorBind(mode="dunder")

        conversion_operator = CppMethod(name="operator bool")
        conversion_operator.cpp.operator = CppOperator(
            kind="conversion",
            conversion_type=NamedCppType(name="bool"),
        )

        self.assertEqual(free_operator.cpp.operator.symbol, "+")
        self.assertEqual(free_operator.bind.operator.mode, "named")
        self.assertEqual(method_operator.cpp.operator.symbol, "[]")
        self.assertEqual(method_operator.bind.operator.mode, "dunder")
        self.assertEqual(conversion_operator.cpp.operator.kind, "conversion")
        self.assertEqual(
            conversion_operator.cpp.operator.conversion_type.render(),
            "bool",
        )

    def test_defaults_reuse_bind_facet_types(self) -> None:
        module_defaults = CppModuleDefaults()
        namespace_defaults = CppNamespaceDefaults()
        class_defaults = CppClassDefaults()
        class_template_defaults = CppClassTemplateDefaults()
        function_template_defaults = CppFunctionTemplateDefaults()

        self.assertIsInstance(module_defaults.namespace, CppNamespaceBindFacet)
        self.assertIsInstance(module_defaults.class_, CppClassBindFacet)
        self.assertIsInstance(module_defaults.function, CppFunctionBindFacet)
        self.assertIsInstance(module_defaults.enum, CppEnumBindFacet)
        self.assertIsInstance(namespace_defaults.namespace, CppNamespaceBindFacet)
        self.assertIsInstance(namespace_defaults.class_, CppClassBindFacet)
        self.assertIsInstance(namespace_defaults.function, CppFunctionBindFacet)
        self.assertIsInstance(namespace_defaults.enum, CppEnumBindFacet)
        self.assertIsInstance(class_defaults.class_, CppClassBindFacet)
        self.assertIsInstance(class_defaults.method, CppFunctionBindFacet)
        self.assertIsInstance(class_defaults.constructor, CppFunctionBindFacet)
        self.assertIsInstance(class_defaults.field, CppFieldBindFacet)
        self.assertIsInstance(class_defaults.enum, CppEnumBindFacet)
        self.assertIsInstance(class_template_defaults.instance, CppClassBindFacet)
        self.assertIsInstance(class_template_defaults.class_, CppClassBindFacet)
        self.assertIsInstance(class_template_defaults.method, CppFunctionBindFacet)
        self.assertIsInstance(class_template_defaults.constructor, CppFunctionBindFacet)
        self.assertIsInstance(class_template_defaults.field, CppFieldBindFacet)
        self.assertIsInstance(class_template_defaults.enum, CppEnumBindFacet)
        self.assertIsInstance(function_template_defaults.instance, CppFunctionBindFacet)

    def test_class_cpp_facet_uses_cpp_class_base_objects(self) -> None:
        base = CppClassBase(type=NamedCppType(name="Base"), visibility=CppVisibility.PUBLIC)
        cls = CppClass(name="Derived")
        cls.cpp.bases.append(base)
        cls.cpp.visibility = CppVisibility.PRIVATE

        self.assertIs(cls.cpp.bases[0], base)
        self.assertEqual(cls.cpp.bases[0].visibility, CppVisibility.PUBLIC)
        self.assertEqual(cls.cpp.visibility, CppVisibility.PRIVATE)

    def test_active_flag_lives_in_bind_facets(self) -> None:
        namespace = CppNamespace(name="demo")
        cls = CppClass(name="Widget")
        function = CppFunction(name="make_widget")
        method = CppMethod(name="size")
        field = CppField(name="size")
        enum_ = CppEnum(name="Kind")
        enumerator = CppEnumerator(name="primary")

        namespace.bind.active = False
        cls.bind.active = True
        function.bind.active = False
        method.bind.active = True
        field.bind.active = False
        enum_.bind.active = True
        enumerator.bind.active = False

        self.assertFalse(namespace.bind.active)
        self.assertTrue(cls.bind.active)
        self.assertFalse(function.bind.active)
        self.assertTrue(method.bind.active)
        self.assertFalse(field.bind.active)
        self.assertTrue(enum_.bind.active)
        self.assertFalse(enumerator.bind.active)

    def test_manual_template_instance_creation_uses_template_wrappers(self) -> None:
        class_template = CppClassTemplate(name="Vector")
        function_template = CppFunctionTemplate(name="make_value")
        class_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        function_template.declaration.cpp.template_parameters.append(
            CppNonTypeTemplateParameter(name="N")
        )
        namespace = CppNamespace(
            name="demo",
            class_templates=[class_template],
            function_templates=[function_template],
        )
        module = CppModule(name="bindings", namespaces=[namespace])

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
        self.assertEqual(class_template.qualified_name, "demo")
        self.assertEqual(function_template.qualified_name, "demo")
        self.assertEqual(class_template.declaration.qualified_name, "demo::Vector")
        self.assertEqual(function_template.declaration.qualified_name, "demo::make_value")
        self.assertEqual(class_instance.qualified_name, "demo::Vector")
        self.assertEqual(function_instance.qualified_name, "demo::make_value")
        self.assertIs(module.namespaces[0], namespace)

    def test_observed_template_instances_materialize_recursively_in_subtrees(self) -> None:
        inner_function_template = CppFunctionTemplate(name="make_inner")
        inner_function_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        inner_function_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(
                arguments=[CppTypeTemplateArgument(type=NamedCppType(name="double"))],
            )
        )
        class_template = CppClassTemplate(
            name="Vector",
            declaration=CppClassTemplateDecl(
                name="Vector",
                function_templates=[inner_function_template],
            ),
        )
        class_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        class_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(
                arguments=[CppTypeTemplateArgument(type=NamedCppType(name="int"))],
            )
        )
        namespace = CppNamespace(
            name="demo",
            class_templates=[class_template],
        )

        created_instances = add_observed_template_instances(namespace)

        self.assertEqual(len(created_instances), 2)
        self.assertEqual(len(class_template.instances), 1)
        self.assertEqual(len(inner_function_template.instances), 1)
        self.assertIsInstance(class_template.instances[0], CppClassTemplateInstance)
        self.assertIsInstance(
            inner_function_template.instances[0],
            CppFunctionTemplateInstance,
        )
        self.assertEqual(
            class_template.instances[0].cpp.template_arguments[0].render(),
            "int",
        )
        self.assertEqual(
            inner_function_template.instances[0].cpp.template_arguments[0].render(),
            "double",
        )

    def test_observed_template_instance_materialization_can_filter_function_templates(self) -> None:
        function_template = CppFunctionTemplate(name="make_value")
        function_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        function_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(
                arguments=[CppTypeTemplateArgument(type=NamedCppType(name="int"))],
            )
        )
        namespace = CppNamespace(
            name="demo",
            function_templates=[function_template],
        )

        created_instances = add_observed_template_instances(
            namespace,
            include_function_templates=False,
        )

        self.assertEqual(created_instances, [])
        self.assertEqual(function_template.instances, [])

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
        self.assertEqual(instance.cpp.template_arguments[0].render(), "int")

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

        self.assertEqual(
            outer_parameter.render(),
            "template <template <typename T> class Alloc> class Container",
        )

    def test_build_py_doc_from_cpp_doc_copies_nested_data(self) -> None:
        cpp_doc = CppDoc(
            brief="Create a widget.",
            description="Build a widget from one integer seed.",
            parameters={"seed": "Seed value used by the constructor."},
            returns="A new widget instance.",
            notes=["This is only an example."],
            warnings=["Do not pass negative values."],
            see_also=["demo::Widget"],
        )

        py_doc = build_py_doc_from_cpp_doc(cpp_doc)

        self.assertIsNotNone(py_doc)
        self.assertEqual(py_doc.summary, "Create a widget.")
        self.assertEqual(py_doc.parameters["seed"], "Seed value used by the constructor.")

        cpp_doc.parameters["seed"] = "Changed"
        cpp_doc.notes.append("Changed")
        self.assertEqual(py_doc.parameters["seed"], "Seed value used by the constructor.")
        self.assertEqual(py_doc.notes, ["This is only an example."])

    def test_named_cpp_type_renders_const_qualified_names(self) -> None:
        cls = CppClass(name="Widget")
        cpp_type = NamedCppType(name="std::string", is_const=True, declaration=cls)

        self.assertEqual(cpp_type.render(), "const std::string")
        self.assertIs(cpp_type.declaration, cls)

    def test_named_cpp_type_preserves_original_name_when_canonical_is_present(self) -> None:
        cpp_type = NamedCppType(
            name="uint64_t",
            canonical=BuiltinCppType(kind="unsigned_long"),
        )

        self.assertEqual(cpp_type.render(), "uint64_t")
        self.assertEqual(cpp_type.canonical.render(), "unsigned long")

    def test_builtin_cpp_type_renders_language_builtin_names(self) -> None:
        cpp_type = BuiltinCppType(kind="int", is_const=True)

        self.assertEqual(cpp_type.render(), "const int")

    def test_builtin_cpp_type_renders_nullptr_type(self) -> None:
        cpp_type = BuiltinCppType(kind="nullptr_t")

        self.assertEqual(cpp_type.render(), "std::nullptr_t")

    def test_array_cpp_type_renders_fixed_extent_arrays(self) -> None:
        cpp_type = ArrayCppType(
            element_type=BuiltinCppType(kind="int"),
            extent="4",
        )

        self.assertEqual(cpp_type.render(), "int[4]")

    def test_array_cpp_type_renders_nested_arrays_recursively(self) -> None:
        cpp_type = ArrayCppType(
            element_type=ArrayCppType(
                element_type=NamedCppType(name="Widget"),
                extent="4",
            ),
            extent="3",
        )

        self.assertEqual(cpp_type.render(), "Widget[4][3]")

    def test_function_cpp_type_renders_plain_function_types(self) -> None:
        cpp_type = FunctionCppType(
            return_type=BuiltinCppType(kind="void"),
            parameters=[
                BuiltinCppType(kind="int"),
                NamedCppType(name="Widget"),
            ],
        )

        self.assertEqual(cpp_type.render(), "void (int, Widget)")

    def test_pointer_cpp_type_can_wrap_function_cpp_type(self) -> None:
        cpp_type = PointerCppType(
            pointee=FunctionCppType(
                return_type=BuiltinCppType(kind="void"),
                parameters=[BuiltinCppType(kind="int")],
            )
        )

        self.assertEqual(cpp_type.render(), "void (*)(int)")

    def test_named_and_builtin_cpp_types_cover_different_use_cases(self) -> None:
        builtin_type = BuiltinCppType(kind="int")
        named_type = NamedCppType(name="demo::Widget")

        self.assertEqual(builtin_type.render(), "int")
        self.assertEqual(named_type.render(), "demo::Widget")


if __name__ == "__main__":
    unittest.main()
