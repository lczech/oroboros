from __future__ import annotations

from pathlib import Path
import unittest

from oroboros.model import (
    ArrayCppType,
    BuiltinCppType,
    CppAlias,
    CppClass,
    CppClassBase,
    CppClassBindFacet,
    CppClassDefaults,
    CppClassTemplate,
    CppClassTemplateDecl,
    CppClassTemplateDefaults,
    CppClassTemplateInstance,
    CppConstructor,
    CppConstructorBindFacet,
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
    CppMethodBindFacet,
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
    CppLocationInfo,
    CppParameterCppFacet,
    CppNonTypeTemplateParameter,
    CppTemplateTemplateArgument,
    CppTemplateTemplateParameter,
    CppTypeTemplateArgument,
    CppTypeTemplateParameter,
    CppFunctionTemplateInstance,
    ModelLookupError,
    ModelSemanticValidationError,
    CppVisibility,
    ModelValidationError,
    add_template_instance,
    find_aliases,
    NamedCppType,
    PointerCppType,
    SourceLocation,
    TemplateInstanceCppType,
    add_class_template_instance,
    add_function_template_instance,
    add_observed_template_instances,
    build_py_doc_from_cpp_doc,
    cpp_types_equivalent,
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
        cls.add_alias(CppAlias(name="SizeType")).cpp.target = NamedCppType(name="std::size_t")
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
        self.assertEqual(cls.aliases[0].qualified_name, "demo::Widget::SizeType")

    def test_aliases_preserve_target_type_and_can_be_found_in_scope_tree(self) -> None:
        namespace = CppNamespace(name="demo")
        namespace.add_alias(CppAlias(name="Index")).cpp.target = NamedCppType(name="std::size_t")
        namespace.aliases[0].cpp.kind = "using"

        self.assertEqual(namespace.aliases[0].qualified_name, "demo::Index")
        self.assertEqual(namespace.aliases[0].cpp.target.render(), "std::size_t")
        self.assertEqual(namespace.aliases[0].cpp.kind, "using")

    def test_find_aliases_discovers_class_aliases_across_subtrees(self) -> None:
        cls = CppClass(name="Widget")
        namespace = CppNamespace(name="demo", classes=[cls])
        namespace.add_alias(CppAlias(name="WidgetAlias")).cpp.target = NamedCppType(name="demo::Widget")
        namespace.add_alias(CppAlias(name="SizeType")).cpp.target = NamedCppType(name="std::size_t")
        nested = CppNamespace(name="detail")
        nested.add_alias(CppAlias(name="WidgetHandle")).cpp.target = NamedCppType(name="demo::Widget")
        namespace.add_namespace(nested)

        aliases = find_aliases(namespace, cls)

        self.assertCountEqual(
            [alias.name for alias in aliases],
            ["WidgetAlias", "WidgetHandle"],
        )

    def test_find_aliases_matches_class_targets_via_declaration_links_with_qualifiers(self) -> None:
        cls = CppClass(name="Widget")
        namespace = CppNamespace(name="demo", classes=[cls])
        namespace.add_alias(CppAlias(name="WidgetAlias")).cpp.target = NamedCppType(
            name="Widget",
            declaration=cls,
            is_const=True,
        )

        aliases = find_aliases(namespace, cls)

        self.assertEqual([alias.name for alias in aliases], ["WidgetAlias"])

    def test_find_aliases_matches_type_targets_via_canonical_structure(self) -> None:
        namespace = CppNamespace(name="demo")
        namespace.add_alias(CppAlias(name="Index")).cpp.target = NamedCppType(
            name="uint64_t",
            canonical=BuiltinCppType(kind="unsigned_long"),
        )

        aliases = find_aliases(namespace, BuiltinCppType(kind="unsigned_long"))

        self.assertEqual([alias.name for alias in aliases], ["Index"])

    def test_find_aliases_follows_alias_chains_to_the_underlying_class(self) -> None:
        widget = CppClass(name="Widget")
        namespace = CppNamespace(name="demo", classes=[widget])
        first = namespace.add_alias(CppAlias(name="A"))
        first.cpp.target = NamedCppType(name="Widget", declaration=widget)
        second = namespace.add_alias(CppAlias(name="B"))
        second.cpp.target = NamedCppType(
            name="A",
            declaration=first,
            canonical=NamedCppType(name="Widget", declaration=widget),
        )

        aliases = find_aliases(namespace, widget)

        self.assertCountEqual(
            [alias.name for alias in aliases],
            ["A", "B"],
        )

    def test_lookup_helpers_find_elements_by_name_and_qualified_name(self) -> None:
        method = CppMethod(name="foo")
        cls = CppClass(name="Widget", methods=[method])
        namespace = CppNamespace(name="demo", classes=[cls])
        module = CppModule(name="bindings", namespaces=[namespace])

        self.assertIs(
            module.find_one_by_qualified_name("::demo::Widget", types=CppClass),
            cls,
        )
        self.assertEqual(
            module.find_all_by_name("foo", types=(CppMethod,)),
            [method],
        )
        self.assertIs(
            namespace.find_one_by_name("Widget", types=CppClass),
            cls,
        )

    def test_named_child_views_navigate_unique_and_overloadable_collections(self) -> None:
        method_a = CppMethod(name="foo")
        method_b = CppMethod(name="foo")
        field = CppField(name="size")
        enum_ = CppEnum(name="Kind", enumerators=[CppEnumerator(name="primary")])
        cls = CppClass(
            name="Widget",
            methods=[method_a, method_b],
            fields=[field],
            enums=[enum_],
        )
        function_a = CppFunction(name="make_widget")
        function_b = CppFunction(name="make_widget")
        namespace = CppNamespace(name="demo", classes=[cls], functions=[function_a, function_b])
        module = CppModule(name="bindings", namespaces=[namespace])

        self.assertIs(module.namespace["demo"], namespace)
        self.assertIs(namespace.class_["Widget"], cls)
        self.assertIs(cls.field["size"], field)
        self.assertIs(cls.enum["Kind"], enum_)
        self.assertIs(enum_.enumerator["primary"], enum_.enumerators[0])
        self.assertEqual(namespace.function["make_widget"], [function_a, function_b])
        self.assertEqual(cls.method["foo"], [method_a, method_b])

    def test_named_child_views_raise_on_missing_or_ambiguous_unique_names(self) -> None:
        namespace_a = CppNamespace(name="demo")
        namespace_b = CppNamespace(name="demo")
        module = CppModule(name="bindings", namespaces=[namespace_a, namespace_b])

        with self.assertRaises(ModelLookupError):
            _ = module.namespace["demo"]

        with self.assertRaises(ModelLookupError):
            _ = module.function["missing"]

    def test_generic_navigation_supports_chained_direct_child_lookup(self) -> None:
        method = CppMethod(name="size")
        cls = CppClass(name="Widget", methods=[method])
        inner = CppNamespace(name="inner", classes=[cls])
        outer = CppNamespace(name="outer", namespaces=[inner])
        module = CppModule(name="bindings", namespaces=[outer])

        self.assertIs(module["outer"], outer)
        self.assertIs(module["outer"]["inner"], inner)
        self.assertIs(module["outer"]["inner"]["Widget"], cls)
        self.assertIs(module["outer"]["inner"]["Widget"]["size"], method)

    def test_generic_navigation_returns_lists_for_overloadable_direct_children(self) -> None:
        method_a = CppMethod(name="size")
        method_b = CppMethod(name="size")
        cls = CppClass(name="Widget", methods=[method_a, method_b])

        self.assertEqual(cls["size"], [method_a, method_b])

    def test_generic_navigation_returns_mixed_callable_groups_for_functions_and_templates(self) -> None:
        function = CppFunction(name="make_widget")
        function_template = CppFunctionTemplate(name="make_widget")
        namespace = CppNamespace(
            name="demo",
            functions=[function],
            function_templates=[function_template],
        )

        self.assertEqual(namespace["make_widget"], [function, function_template])

    def test_element_names_and_generic_find_helpers_improve_discovery(self) -> None:
        method = CppMethod(name="size")
        cls = CppClass(name="Widget", methods=[method])
        namespace = CppNamespace(name="demo", classes=[cls])
        module = CppModule(name="bindings", namespaces=[namespace])

        self.assertEqual(module.element_names, ["demo"])
        self.assertEqual(namespace.element_names, ["Widget"])
        self.assertEqual(cls.element_names, ["size"])
        self.assertIs(module.find("demo::Widget"), cls)
        self.assertEqual(module.find_all("size"), [method])

    def test_lookup_helpers_raise_on_missing_or_ambiguous_matches(self) -> None:
        cls = CppClass(
            name="Widget",
            methods=[CppMethod(name="foo"), CppMethod(name="foo")],
        )
        namespace = CppNamespace(name="demo", classes=[cls])
        module = CppModule(name="bindings", namespaces=[namespace])

        self.assertEqual(
            len(module.find_all_by_qualified_name("demo::Widget::foo", types=CppMethod)),
            2,
        )

        with self.assertRaises(ModelLookupError):
            module.find_one_by_qualified_name("demo::Widget::foo", types=CppMethod)

        with self.assertRaises(ModelLookupError):
            module.find_one_by_name("foo", types=CppMethod)

        with self.assertRaises(ModelLookupError):
            module.find_one_by_qualified_name("demo::MissingNamespace")

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
        self.assertIsNone(function.py.sig)
        self.assertIsNone(method.py.name)
        self.assertIsNone(method.py.sig)
        self.assertIsNone(constructor.py.sig)
        self.assertIsNone(parameter.py.name)
        self.assertIsNone(parameter.py.sig)
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
        self.assertIsInstance(class_defaults.method, CppMethodBindFacet)
        self.assertIsInstance(class_defaults.constructor, CppConstructorBindFacet)
        self.assertIsInstance(class_defaults.field, CppFieldBindFacet)
        self.assertIsInstance(class_defaults.enum, CppEnumBindFacet)
        self.assertIsInstance(class_template_defaults.instance, CppClassBindFacet)
        self.assertIsInstance(class_template_defaults.class_, CppClassBindFacet)
        self.assertIsInstance(class_template_defaults.method, CppMethodBindFacet)
        self.assertIsInstance(class_template_defaults.constructor, CppConstructorBindFacet)
        self.assertIsInstance(class_template_defaults.field, CppFieldBindFacet)
        self.assertIsInstance(class_template_defaults.enum, CppEnumBindFacet)
        self.assertIsInstance(function_template_defaults.instance, CppFunctionBindFacet)

    def test_method_and_constructor_bind_facets_keep_semantic_distinction(self) -> None:
        method = CppMethod(name="size")
        constructor = CppConstructor(name="Widget")

        self.assertIsInstance(method.bind, CppMethodBindFacet)
        self.assertIsInstance(method.bind, CppFunctionBindFacet)
        self.assertIsInstance(constructor.bind, CppConstructorBindFacet)
        self.assertIsInstance(constructor.bind, CppFunctionBindFacet)

    def test_add_helpers_attach_children_and_return_them(self) -> None:
        module = CppModule(name="bindings")
        namespace = module.add_namespace(CppNamespace(name="demo"))
        cls = namespace.add_class(CppClass(name="Widget"))
        constructor = cls.add_constructor(CppConstructor(name="Widget"))
        method = cls.add_method(CppMethod(name="size"))
        parameter = method.add_parameter(CppParameter(name="value"))
        enum_ = cls.add_enum(CppEnum(name="Kind"))
        enumerator = enum_.add_enumerator(CppEnumerator(name="primary"))

        self.assertIs(module.namespaces[0], namespace)
        self.assertIs(namespace.owner, module)
        self.assertIs(namespace.classes[0], cls)
        self.assertIs(cls.owner, namespace)
        self.assertIs(cls.constructors[0], constructor)
        self.assertIs(constructor.owner, cls)
        self.assertIs(cls.methods[0], method)
        self.assertIs(method.owner, cls)
        self.assertIs(method.parameters[0], parameter)
        self.assertIs(parameter.owner, method)
        self.assertIs(cls.enums[0], enum_)
        self.assertIs(enum_.owner, cls)
        self.assertIs(enum_.enumerators[0], enumerator)
        self.assertIs(enumerator.owner, enum_)

    def test_validate_tree_accepts_consistent_child_owner_links(self) -> None:
        module = CppModule(name="bindings")
        namespace = module.add_namespace(CppNamespace(name="demo"))
        cls = namespace.add_class(CppClass(name="Widget"))
        method = cls.add_method(CppMethod(name="size"))
        method.add_parameter(CppParameter(name="value"))

        module.validate_tree()

    def test_validate_tree_rejects_direct_list_mutation_without_owner_update(self) -> None:
        module = CppModule(name="bindings")
        namespace = module.add_namespace(CppNamespace(name="demo"))
        namespace.classes.append(CppClass(name="Widget"))

        with self.assertRaises(ModelValidationError):
            module.validate_tree()

    def test_validate_semantics_accepts_consistent_declaration_linked_named_types(self) -> None:
        cls = CppClass(name="Widget")
        method = CppMethod(
            name="set_widget",
            parameters=[
                CppParameter(
                    name="value",
                    cpp=CppParameterCppFacet(
                        type=NamedCppType(name="Widget", declaration=cls),
                    ),
                )
            ],
        )
        cls.add_method(method)
        namespace = CppNamespace(name="demo", classes=[cls])
        module = CppModule(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_rejects_named_type_name_mismatch(self) -> None:
        cls = CppClass(name="Widget")
        function = CppFunction(
            name="take_widget",
            parameters=[
                CppParameter(
                    name="value",
                    cpp=CppParameterCppFacet(
                        type=NamedCppType(name="OtherWidget", declaration=cls),
                    ),
                )
            ],
        )
        namespace = CppNamespace(name="demo", classes=[cls], functions=[function])
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError) as context:
            module.validate_semantics()

        self.assertIn('namespaces["demo"]', str(context.exception))
        self.assertIn('functions["take_widget"]', str(context.exception))
        self.assertIn('parameters["value"]', str(context.exception))

    def test_validate_semantics_rejects_non_class_base_declarations(self) -> None:
        enum_ = CppEnum(name="Kind")
        cls = CppClass(name="Widget")
        cls.cpp.bases.append(
            CppClassBase(
                type=NamedCppType(name="Kind", declaration=enum_),
            )
        )
        namespace = CppNamespace(name="demo", classes=[cls], enums=[enum_])
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_parameters_owned_by_non_function_like_scopes(self) -> None:
        namespace = CppNamespace(name="demo")
        parameter = CppParameter(name="value")
        namespace.functions.append(parameter)
        parameter.owner = namespace
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_constructor_name_mismatches(self) -> None:
        cls = CppClass(
            name="Widget",
            constructors=[CppConstructor(name="OtherWidget")],
        )
        namespace = CppNamespace(name="demo", classes=[cls])
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_invalid_method_flag_combinations(self) -> None:
        pure_virtual_only = CppMethod(name="foo")
        pure_virtual_only.cpp.is_pure_virtual = True

        static_virtual = CppMethod(name="bar")
        static_virtual.cpp.is_static = True
        static_virtual.cpp.is_virtual = True

        cls = CppClass(
            name="Widget",
            methods=[pure_virtual_only, static_virtual],
        )
        namespace = CppNamespace(name="demo", classes=[cls])
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_cpp_original_name_mismatches(self) -> None:
        cls = CppClass(name="Widget")
        cls.cpp.original_name = "OriginalWidget"
        namespace = CppNamespace(name="demo", classes=[cls])
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_duplicate_non_overload_child_names(self) -> None:
        namespace = CppNamespace(
            name="demo",
            classes=[CppClass(name="Widget"), CppClass(name="Widget")],
        )
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_duplicate_alias_names_in_one_scope(self) -> None:
        namespace = CppNamespace(name="demo")
        namespace.add_alias(CppAlias(name="Index")).cpp.target = NamedCppType(name="std::size_t")
        namespace.add_alias(CppAlias(name="Index")).cpp.target = BuiltinCppType(kind="unsigned_long")
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_aliases_without_target_types(self) -> None:
        namespace = CppNamespace(name="demo", aliases=[CppAlias(name="Index")])
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_template_family_name_mismatches(self) -> None:
        function_template = CppFunctionTemplate(name="make_value")
        function_template.declaration.name = "other_value"
        namespace = CppNamespace(name="demo", function_templates=[function_template])
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_invalid_template_instance_arguments(self) -> None:
        function_template = CppFunctionTemplate(name="make_value")
        function_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        instance = add_function_template_instance(
            function_template,
            [CppTypeTemplateArgument(type=NamedCppType(name="int"))],
        )
        instance.cpp.template_arguments = [CppNonTypeTemplateArgument(value="4")]
        namespace = CppNamespace(name="demo", function_templates=[function_template])
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_invalid_named_type_declaration_targets(self) -> None:
        target_function = CppFunction(name="make_widget")
        using_function = CppFunction(
            name="take_widget",
            parameters=[
                CppParameter(
                    name="value",
                    cpp=CppParameterCppFacet(
                        type=NamedCppType(name="make_widget", declaration=target_function),
                    ),
                )
            ],
        )
        namespace = CppNamespace(
            name="demo",
            functions=[target_function, using_function],
        )
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_inconsistent_location_provenance(self) -> None:
        function = CppFunction(name="make_widget")
        function.cpp.location = CppLocationInfo(
            primary=SourceLocation(file=Path("api/widget.hpp"), line=10, column=5),
            declarations=[
                SourceLocation(file=Path("api/widget_fwd.hpp"), line=3, column=1),
                SourceLocation(file=Path("api/widget_fwd.hpp"), line=3, column=1),
            ],
            definition=SourceLocation(file=Path("api/widget.hpp"), line=20, column=1),
        )
        namespace = CppNamespace(name="demo", functions=[function])
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_invalid_overload_index_groups(self) -> None:
        first = CppMethod(name="foo")
        first.cpp.overload_index = 0
        second = CppMethod(name="foo")
        second.cpp.overload_index = 2
        cls = CppClass(name="Widget", methods=[first, second])
        namespace = CppNamespace(name="demo", classes=[cls])
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_invalid_observed_template_instances(self) -> None:
        function_template = CppFunctionTemplate(name="make_value")
        function_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        function_template.declaration.cpp.observed_instances.append(
            CppObservedTemplateInstance(
                arguments=[CppNonTypeTemplateArgument(value="4")],
            )
        )
        namespace = CppNamespace(name="demo", function_templates=[function_template])
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_free_functions_owned_by_class_like_scopes(self) -> None:
        cls = CppClass(name="Widget")
        stray_function = CppFunction(name="helper")
        cls.classes.append(stray_function)
        stray_function.owner = cls
        namespace = CppNamespace(name="demo", classes=[cls])
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_implausible_cpp_identifier_names(self) -> None:
        function = CppFunction(name="bad-name")
        namespace = CppNamespace(name="demo", functions=[function])
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_accepts_operator_names(self) -> None:
        method = CppMethod(name="operator+")
        method.cpp.operator = CppOperator(kind="punctuation", symbol="+")
        cls = CppClass(name="Widget", methods=[method])
        namespace = CppNamespace(name="demo", classes=[cls])
        module = CppModule(name="bindings", namespaces=[namespace])

        module.validate_semantics()

    def test_validate_semantics_rejects_alias_names_with_invalid_characters(self) -> None:
        namespace = CppNamespace(name="demo")
        namespace.add_alias(CppAlias(name="Index-Alias")).cpp.target = NamedCppType(name="std::size_t")
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

    def test_validate_semantics_rejects_whitespace_only_enumerator_values(self) -> None:
        enumerator = CppEnumerator(name="primary")
        enumerator.cpp.value_spelling = "   "
        enum_ = CppEnum(name="Kind", enumerators=[enumerator])
        namespace = CppNamespace(name="demo", enums=[enum_])
        module = CppModule(name="bindings", namespaces=[namespace])

        with self.assertRaises(ModelSemanticValidationError):
            module.validate_semantics()

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
        self.assertEqual(class_template.qualified_name, "demo::Vector")
        self.assertEqual(function_template.qualified_name, "demo::make_value")
        self.assertEqual(class_template.declaration.qualified_name, "demo::Vector")
        self.assertEqual(function_template.declaration.qualified_name, "demo::make_value")
        self.assertEqual(class_instance.qualified_name, "demo::Vector")
        self.assertEqual(function_instance.qualified_name, "demo::make_value")
        self.assertIs(module.find_one_by_qualified_name("demo::Vector", types=CppClassTemplate), class_template)
        self.assertIs(
            module.find_one_by_qualified_name("demo::make_value", types=CppFunctionTemplate),
            function_template,
        )
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
        self.assertIsInstance(
            class_template.instances[0].cpp.template_arguments[0],
            CppTypeTemplateArgument,
        )
        self.assertEqual(
            class_template.instances[0].cpp.template_arguments[0].type.name,
            "int",
        )
        self.assertIsInstance(
            inner_function_template.instances[0].cpp.template_arguments[0],
            CppTypeTemplateArgument,
        )
        self.assertEqual(
            inner_function_template.instances[0].cpp.template_arguments[0].type.name,
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

    def test_class_template_instances_copy_alias_children_from_the_declaration(self) -> None:
        class_template = CppClassTemplate(name="Box")
        class_template.declaration.cpp.template_parameters.append(
            CppTypeTemplateParameter(name="T")
        )
        class_template.declaration.add_alias(CppAlias(name="Value")).cpp.target = NamedCppType(name="T")

        instance = add_class_template_instance(
            class_template,
            [CppTypeTemplateArgument(type=NamedCppType(name="int"))],
        )

        self.assertEqual([alias.name for alias in instance.aliases], ["Value"])
        self.assertIsNot(instance.aliases[0], class_template.declaration.aliases[0])
        self.assertEqual(instance.aliases[0].qualified_name, "Box::Value")
        self.assertIsInstance(instance.aliases[0].cpp.target, NamedCppType)
        self.assertEqual(instance.aliases[0].cpp.target.name, "T")

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

    def test_alias_linked_named_cpp_types_still_compare_equivalent_to_their_target(self) -> None:
        widget = CppClass(name="Widget")
        alias = CppAlias(name="WidgetAlias")
        alias.cpp.target = NamedCppType(name="Widget", declaration=widget)
        alias_type = NamedCppType(
            name="WidgetAlias",
            declaration=alias,
            canonical=NamedCppType(name="Widget", declaration=widget),
        )
        widget_type = NamedCppType(name="Widget", declaration=widget)

        self.assertTrue(cpp_types_equivalent(alias_type, widget_type))

    def test_named_and_builtin_cpp_types_cover_different_use_cases(self) -> None:
        builtin_type = BuiltinCppType(kind="int")
        named_type = NamedCppType(name="demo::Widget")

        self.assertEqual(builtin_type.render(), "int")
        self.assertEqual(named_type.render(), "demo::Widget")


if __name__ == "__main__":
    unittest.main()
